"""질의응답 요청 처리. 로컬 서버와 Workers 겉껍질이 같은 함수를 부른다(research R-11)."""

from __future__ import annotations

import json
import re
import secrets
import sys
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime
from time import monotonic, time

from qello_knowledge.config.check import CheckReport
from qello_knowledge.discord.components import consent_buttons, consent_text
from qello_knowledge.discord.interactions import MAX_BODY_BYTES, notice, parse, pong, signature_headers
from qello_knowledge.discord.notices import FIXED_NOTICES, OBS_NOTICES, failure_notice
from qello_knowledge.discord.signature import verify
from qello_knowledge.discord.sources import render_sources
from qello_knowledge.domain.discord import AccessDecision, FirstResponse, InteractionKind, QueryRunLog
from qello_knowledge.domain.query_log import QueryRecord, RecordStatus

Response = tuple[int, str]


def handle(method: str, path: str, report: Callable[[], CheckReport], *, body: bytes = b"", headers=None, app=None):
    """`GET /healthz`만 처리한다. 실제 질의응답은 후속 명세(QK-BOT-001 등)가 채운다."""
    if path in ("/discord/interactions", "/discord/interactions/start"):
        if method != "POST":
            return 405, "", {}
        return app.respond(path, body, headers or {}) if app is not None else (503, "", {})
    if path != "/healthz":
        return 404, '{"error": "not found"}'
    if method != "GET":
        return 405, '{"error": "method not allowed"}'
    result = report()
    return (200 if result.ok else 503), result.to_json()


class DiscordApp:
    def __init__(
        self,
        public_key,
        jobs,
        *,
        wall_clock=time,
        access_check=lambda item: True,
        outgoing_check=lambda item: True,
        on_response=None,
        recorder=None,
        component_timeout_ms=1500,
        clock=monotonic,
    ):
        self.public_key, self.jobs, self.wall_clock = public_key, jobs, wall_clock
        self.access_check, self.outgoing_check = access_check, outgoing_check
        self.on_response = on_response
        self.recorder = recorder if recorder is not None else jobs.recorder
        self.component_timeout_ms, self.clock = component_timeout_ms, clock

    def respond(self, path, body, headers):
        started_at = self.jobs.now()
        aux_started = self.clock()
        received_utc = datetime.fromtimestamp(self.wall_clock(), UTC)
        if len(body) > MAX_BODY_BYTES:
            return 413, "", {}
        signed = signature_headers(headers)
        signature, timestamp = signed["X-Signature-Ed25519"], signed["X-Signature-Timestamp"]
        if path.endswith("/start"):
            try:
                payload = json.loads(body)
                run_id = payload.get("run_id") if isinstance(payload, dict) else None
                started = isinstance(run_id, str) and self.jobs.start(run_id, signature, timestamp)
            except (ValueError, UnicodeError, RecursionError, TypeError):
                started = False
            return (204 if started else 409), "", {}
        if not verify(self.public_key, signature, timestamp, body, self.wall_clock()):
            return 401, "", {}
        item = parse(body)
        if item.kind is InteractionKind.COMPONENT:
            return self._component_response(item, aux_started)
        if item.kind is InteractionKind.COMMAND and item.command == "sources":
            return self._sources_response(item, aux_started)
        access, status, run_id = "not_checked", "unsupported", None
        if item.kind is InteractionKind.PING:
            response = pong()
        elif item.kind is not InteractionKind.COMMAND:
            response = notice(FIXED_NOTICES["unsupported"])
        else:
            try:
                verdict = self.access_check(item)
                allowed = verdict in (True, AccessDecision.ALLOWED)
                access = verdict.value if isinstance(verdict, AccessDecision) else ("allowed" if allowed else "denied")
                if not allowed:
                    status = "access_denied"
                    response = notice(FIXED_NOTICES["access"])
                elif not self.outgoing_check(item):
                    status = "outgoing_blocked"
                    response = notice(FIXED_NOTICES["secret"])
                else:
                    response = self.jobs.reserve(item, signature, timestamp)
                    status = "duplicate" if response.data.get("content") == FIXED_NOTICES["duplicate"] else "busy"
            except Exception:
                status = "failed"
                run_id = f"q-{datetime.now(UTC):%Y%m%dT%H%M%S}-{secrets.token_hex(4)}"
                response = notice(failure_notice("unexpected", run_id))
        recording = "off"
        if (
            response.type == 4
            and item.kind is InteractionKind.COMMAND
            and item.command == "ask"
            and access == "allowed"
            and status in set(RecordStatus)
        ):
            run_id = run_id or f"q-{datetime.now(UTC):%Y%m%dT%H%M%S}-{secrets.token_hex(4)}"
            recording = self.jobs.record_immediate(
                QueryRecord(
                    run_id,
                    received_utc,
                    item.user_id,
                    item.private,
                    RecordStatus(status),
                    first_response_ms=max(0, int((self.jobs.now() - started_at) * 1000)),
                ),
                item.interaction_id,
            )
        if response.type == 4 and self.on_response is not None:
            run_id = run_id or f"q-{datetime.now(UTC):%Y%m%dT%H%M%S}-{secrets.token_hex(4)}"
            try:
                self.on_response(
                    QueryRunLog(
                        run_id,
                        access,
                        True,
                        status,
                        failure=status,
                        timings_ms={
                            "first_response": max(0, int((self.jobs.now() - started_at) * 1000)),
                            "retrieve": 0,
                            "generate": 0,
                            "deliver": 0,
                        },
                        calls={"retrieve": 0, "generate": 0, "deliver": 0},
                        record=recording,
                    )
                )
            except Exception:
                return 200, json.dumps(response.to_dict(), ensure_ascii=False), {}
        if response.run_id:
            self.jobs.record_received(response.run_id, started_at, received_utc)
            self.jobs.record_first_response(response.run_id, (self.jobs.now() - started_at) * 1000)
        return (
            200,
            json.dumps(response.to_dict(), ensure_ascii=False),
            ({"X-QK-Run": response.run_id} if response.run_id else {}),
        )

    def _sources_response(self, item, started):
        result, response = "failed", notice(OBS_NOTICES["sources_failed"])
        try:
            if self.access_check(item) not in (True, AccessDecision.ALLOWED):
                result, response = "denied", notice(OBS_NOTICES["access_sources"])
            elif self.recorder is not None:
                saved = self.recorder.front("sources", deadline=started + self.component_timeout_ms / 1000)
                if saved.status == "ok":
                    result, response = "ok", notice(render_sources(saved.value))
        except Exception:
            result = "failed"
        return self._aux_finish("sources", None, result, response, started)

    def _component_response(self, item, started):
        # BOT-001 FR-007 예외: 버튼·/sources는 첫 응답 안에서 앞 길 저장소 호출을 기다린다.
        result, response = "rejected", notice(OBS_NOTICES["missing"])
        action = item.component_action
        deadline = started + self.component_timeout_ms / 1000
        try:
            verdict = self.access_check(item)
            if verdict not in (True, AccessDecision.ALLOWED):
                response = notice(OBS_NOTICES["access_component"])
            elif (
                self.recorder is not None
                and self.recorder.enabled
                and action in ("up", "down", "keep", "skip")
                and item.user_id is not None
                and re.fullmatch(r"[0-9]{17,20}", item.user_id)
            ):
                if action in ("keep", "skip"):
                    result, response = self._consent(item, deadline)
                else:
                    saved = self.recorder.front(
                        "feedback", item.component_run_id, item.user_id, action, deadline=deadline
                    )
                    result = (
                        saved.value if saved.status == "ok" and saved.value in ("stored", "missing") else "uncertain"
                    )
                    response = notice(
                        OBS_NOTICES[
                            "feedback" if result == "stored" else ("missing" if result == "missing" else "uncertain")
                        ]
                    )
                    pending = self.jobs.pending
                    question = pending.get(item.component_run_id) if pending is not None else None
                    if (
                        result == "stored"
                        and action == "down"
                        and question is not None
                        and question.questioner_id == item.user_id
                        and question.state in ("waiting", "uncertain")
                    ):
                        response = FirstResponse(
                            4,
                            {
                                "content": consent_text(pending.retain_until.isoformat()),
                                "flags": 64,
                                "allowed_mentions": {"parse": []},
                                "components": consent_buttons(item.component_run_id),
                            },
                        )
        except Exception:
            result, response = "uncertain", notice(OBS_NOTICES["uncertain"])
        return self._aux_finish("component", action, result, response, started)

    def _consent(self, item, deadline):
        pending = self.jobs.pending
        before = pending.get(item.component_run_id) if pending is not None else None
        if before is not None and before.questioner_id != item.user_id:
            return "rejected", notice(OBS_NOTICES["missing"])
        if before is not None and before.state == "claimed":
            return "uncertain", notice(OBS_NOTICES["uncertain"])
        claim = (
            pending.claim(item.component_run_id, item.user_id)
            if before is not None and before.state in ("waiting", "uncertain")
            else None
        )
        if before is not None and before.state in ("waiting", "uncertain") and claim is None:
            return "uncertain", notice(OBS_NOTICES["uncertain"])
        # 6~13행은 선점 전 상태로 처음 맞는 행 하나만 처리한다.
        try:
            if claim is not None and item.component_action == "keep":
                if not self.outgoing_check(replace(item, question=claim.question)):
                    saved = self.recorder.front("mark_text_skipped", item.component_run_id, deadline=deadline)
                    if saved.status != "ok":
                        pending.finish(claim, uncertain=True)
                        return "uncertain", notice(OBS_NOTICES["uncertain"])
                    pending.finish(claim)
                    return "skipped", self._updated(OBS_NOTICES["secret"])
                saved = self.recorder.front(
                    "store_question", item.component_run_id, item.user_id, claim.question, deadline=deadline
                )
                if saved.status != "ok":
                    pending.finish(claim, uncertain=True)
                    return "uncertain", notice(OBS_NOTICES["uncertain"])
                if saved.value in ("stored", "exists"):
                    pending.finish(claim)
                    return "stored", self._updated(OBS_NOTICES["stored"])
                if saved.value in ("missing", "not_questioner"):
                    pending.finish(claim)
                    return "missing", notice(OBS_NOTICES["text_missing"])
                pending.finish(claim, uncertain=True)
                return "uncertain", notice(OBS_NOTICES["uncertain"])
            if claim is not None and before.state == "waiting" and item.component_action == "skip":
                pending.finish(claim)
                return "skipped", self._updated(OBS_NOTICES["skipped"])
            saved = self.recorder.front("question_status", item.component_run_id, item.user_id, deadline=deadline)
            if saved.status != "ok" or saved.value not in ("stored", "none", "missing", "not_questioner"):
                if claim is not None:
                    pending.finish(claim, uncertain=True)
                return "uncertain", notice(OBS_NOTICES["uncertain"])
            if claim is not None:
                pending.finish(claim)
            if saved.value == "stored":
                key = "exists"
            elif saved.value in ("missing", "not_questioner"):
                key = "missing"
            elif before is not None and before.state == "chosen":
                key = "chosen"
            else:
                key = "skipped" if item.component_action == "skip" else "expired"
            return saved.value, notice(OBS_NOTICES[key])
        except Exception:
            if claim is not None:
                pending.finish(claim, uncertain=True)
            return "uncertain", notice(OBS_NOTICES["uncertain"])

    @staticmethod
    def _updated(text):
        return FirstResponse(7, {"content": text, "allowed_mentions": {"parse": []}, "components": []})

    def _aux_finish(self, kind, action, result, response, started):
        log = {
            "kind": kind,
            "action": action,
            "result": result,
            "elapsed_ms": max(0, int((self.clock() - started) * 1000)),
        }
        try:
            sys.stderr.write(json.dumps(log, ensure_ascii=False, separators=(",", ":")) + "\n")
        except OSError:
            pass
        return 200, json.dumps(response.to_dict(), ensure_ascii=False), {}
