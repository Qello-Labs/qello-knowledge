"""질의 수명 자리·실행 자리·전달 권한. 모든 상태 전이는 한 잠금 아래에서 한다."""

from __future__ import annotations

import math
import re
import secrets
import threading
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import monotonic

from qello_knowledge.discord.interactions import deferred, notice
from qello_knowledge.discord.notices import FIXED_NOTICES, failure_notice
from qello_knowledge.domain.discord import (
    DedupEntry,
    DedupStage,
    Interaction,
    QueryJob,
    QueryRunLog,
    QueryStage,
    RenderedReply,
)
from qello_knowledge.domain.generation import GenerationFailure, GenerationStatus
from qello_knowledge.domain.retrieval import RetrievalFailure


def _safe_failure(value):
    allowed = {f.value for f in (*GenerationFailure, *RetrievalFailure, *QueryStage)}
    allowed.update({"deadline", "timeout", "connection", "unexpected", "http"})
    return value if isinstance(value, str) and (value in allowed or re.fullmatch(r"http_[0-9]{3}", value)) else None


def _numbers(summary):
    names = {"external_calls", "generation_calls", "neurons", "measured", "attempts"}
    return (
        {
            name: value
            for name, value in summary.items()
            if name in names and type(value) in (int, float, bool) and math.isfinite(value)
        }
        if isinstance(summary, dict)
        else {}
    )


@dataclass
class _State:
    job: QueryJob = field(repr=False)
    signature: str = field(repr=False)
    timestamp: str = field(repr=False)
    stage: QueryStage = QueryStage.AWAITING_START
    outcome: QueryStage | None = None
    claimed: bool = False


class QueryJobs:
    def __init__(
        self,
        *,
        pipeline,
        deliver,
        workers=2,
        queue_size=4,
        start_wait=5,
        min_start=15,
        deadline_seconds=55,
        notice_grace=5,
        clock=monotonic,
        executor=None,
        delivery_executor=None,
        autostart=True,
        on_finished=None,
    ):
        self.capacity = workers + queue_size
        self._workers = workers
        self._pipeline, self._deliver, self._clock = pipeline, deliver, clock
        self._on_finished = on_finished
        self._start_wait, self._min_start = start_wait, min_start
        self._deadline, self._grace = deadline_seconds, notice_grace
        self._executor = (
            executor if executor is not None else ThreadPoolExecutor(workers, thread_name_prefix="qk-query")
        )
        self._delivery_executor = (
            delivery_executor
            if delivery_executor is not None
            else ThreadPoolExecutor(self.capacity, thread_name_prefix="qk-deliver")
        )
        self._lock = threading.RLock()
        self._jobs: dict[str, _State] = {}
        self._dedup: dict[str, DedupEntry] = {}
        self._terminal: dict[str, tuple[QueryStage, QueryStage | None, float]] = {}
        self._queue = deque()
        self._running = 0
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._monitor = None
        if autostart:
            self._monitor = threading.Thread(target=self._watch, daemon=True, name="qk-query-monitor")
            self._monitor.start()

    @property
    def in_flight(self):
        with self._lock:
            return len(self._jobs)

    @property
    def running(self):
        with self._lock:
            return self._running

    @property
    def dedup(self):
        with self._lock:
            self._prune()
            return dict(self._dedup)

    def _prune(self):
        now = self._clock()
        self._dedup = {k: v for k, v in self._dedup.items() if v.expires_at > now}
        self._terminal = {k: v for k, v in self._terminal.items() if v[2] > now}

    def stage(self, run_id):
        with self._lock:
            state = self._jobs.get(run_id)
            return state.stage if state else self._terminal.get(run_id, (None, None, 0))[0]

    def outcome(self, run_id):
        with self._lock:
            state = self._jobs.get(run_id)
            return state.outcome if state else self._terminal.get(run_id, (None, None, 0))[1]

    def reserve(self, interaction: Interaction, signature: str, timestamp: str):
        with self._lock:
            self._prune()
            if interaction.interaction_id in self._dedup:
                return notice(FIXED_NOTICES["duplicate"])
            if self._stop.is_set() or len(self._jobs) >= self.capacity:
                return notice(FIXED_NOTICES["busy"])
            now = self._clock()
            run_id = f"q-{datetime.now(UTC):%Y%m%dT%H%M%S}-{secrets.token_hex(4)}"
            while run_id in self._jobs or run_id in self._terminal:
                run_id = f"q-{datetime.now(UTC):%Y%m%dT%H%M%S}-{secrets.token_hex(4)}"
            job = QueryJob(run_id, interaction, now, now + self._deadline, now + self._deadline + self._grace)
            self._jobs[run_id] = _State(job, signature, timestamp)
            self._dedup[interaction.interaction_id] = DedupEntry(
                interaction.interaction_id, DedupStage.IN_PROGRESS, now + 900
            )
            self._wake.set()
            return deferred(interaction.private, run_id)

    def start(self, run_id, signature, timestamp):
        with self._lock:
            state = self._jobs.get(run_id)
            if state is None or state.stage is not QueryStage.AWAITING_START:
                return False
            if self._clock() >= state.job.received_at + self._start_wait:
                return False
            if not secrets.compare_digest(state.signature, signature) or not secrets.compare_digest(
                state.timestamp, timestamp
            ):
                return False
            state.stage = QueryStage.QUEUED
            self._queue.append(run_id)
            self._wake.set()
            return True

    def _set_stage(self, state, stage):
        with self._lock:
            if not state.claimed:
                state.stage = stage

    def poll(self):
        with self._lock:
            if self._stop.is_set():
                return
            now = self._clock()
            for state in tuple(self._jobs.values()):
                if state.claimed:
                    continue
                if state.stage is QueryStage.AWAITING_START and now >= state.job.received_at + self._start_wait:
                    self._claim(state, self._notice(state, "not_started"), QueryStage.NOT_STARTED)
                elif now >= state.job.query_deadline:
                    self._claim(state, self._notice(state, "timed_out"), QueryStage.TIMED_OUT)
            self._dispatch()

    def _dispatch(self):
        self._queue = deque(run_id for run_id in self._queue if run_id in self._jobs and not self._jobs[run_id].claimed)
        while self._queue and self._running < self._workers and not self._stop.is_set():
            state = self._jobs.get(self._queue.popleft())
            if state is None or state.claimed:
                continue
            if state.job.query_deadline - self._clock() < self._min_start:
                self._claim(state, self._notice(state, "timed_out"), QueryStage.TIMED_OUT)
                continue
            state.stage = QueryStage.RETRIEVING
            self._running += 1
            self._executor.submit(self._run, state)

    def _notice(self, state, kind):
        return RenderedReply((failure_notice(kind, state.job.run_id),), state.job.interaction.private)

    def _run(self, state):
        try:
            reply = self._pipeline(state.job, lambda stage: self._set_stage(state, stage))
            with self._lock:
                if self._clock() >= state.job.query_deadline:
                    self._claim(state, self._notice(state, "timed_out"), QueryStage.TIMED_OUT)
                else:
                    self._claim(state, reply)
        except TimeoutError:
            with self._lock:
                self._claim(state, self._notice(state, "timed_out"), QueryStage.TIMED_OUT)
        except Exception:
            with self._lock:
                self._claim(state, self._notice(state, "unexpected"), QueryStage.FAILED)
        finally:
            with self._lock:
                self._running -= 1
                self._dispatch()

    def _claim(self, state, reply, outcome=None):
        if state.claimed:
            return
        state.claimed = True
        state.outcome = outcome
        state.stage = QueryStage.DELIVERING
        self._delivery_executor.submit(self._send, state, reply)

    def _send(self, state, reply):
        terminal = QueryStage.UNDELIVERED
        result = None
        started = self._clock()
        try:
            result = self._deliver(state.job, reply)
            terminal = result.stage
        except Exception:
            terminal = QueryStage.UNDELIVERED  # 경계 밖 전송 예외의 원문은 기록하지 않는다.
        finally:
            with self._lock:
                state.stage = terminal
                self._jobs.pop(state.job.run_id, None)
                expires = state.job.received_at + 900
                self._terminal[state.job.run_id] = (terminal, state.outcome, expires)
                self._dedup[state.job.interaction.interaction_id] = DedupEntry(
                    state.job.interaction.interaction_id, DedupStage.DONE, expires
                )
        if self._on_finished is not None:
            status = state.outcome.value if state.outcome is not None else getattr(reply, "status", "answered")
            if terminal is QueryStage.UNDELIVERED:
                status = terminal.value
            if status not in {s.value for s in (*GenerationStatus, *QueryStage)}:
                status = "failed"
            record = QueryRunLog(
                state.job.run_id,
                "allowed",
                state.job.interaction.private,
                status,
                failure=_safe_failure(state.outcome.value if state.outcome else getattr(reply, "failure", None)),
                timings_ms={"deliver": max(0, int((self._clock() - started) * 1000))},
                calls={"deliver": getattr(result, "calls", 0)},
                deliver_retries=getattr(result, "retries", 0),
                deliver_failure=_safe_failure(getattr(result, "failure", None))
                or ("connection" if terminal is QueryStage.UNDELIVERED else None),
                retrieval_summary=_numbers(getattr(reply, "retrieval_summary", {})),
                generation_summary=_numbers(getattr(reply, "generation_summary", {})),
            )
            try:
                self._on_finished(record)
            except Exception:
                return  # 기록 출력 실패도 요청 원문을 오류로 내보내지 않는다.

    def _watch(self):
        while not self._stop.is_set():
            self._wake.wait(0.05)
            self._wake.clear()
            self.poll()

    def close(self):
        self._stop.set()
        self._wake.set()
        if self._monitor is not None:
            self._monitor.join()
        self._executor.shutdown(wait=False, cancel_futures=True)
        self._delivery_executor.shutdown(wait=False, cancel_futures=True)
