"""질의 역할의 좁은 함수만 호출하는 자동 커밋 어댑터."""

from collections.abc import Mapping
from dataclasses import fields
from datetime import datetime
from threading import Event, Timer
from time import monotonic

import psycopg
from psycopg.types.json import Jsonb

from qello_knowledge.domain.query_log import SourceSummary, SourcesView


class QueryLogError(RuntimeError):
    def __init__(self, kind):
        self.kind = kind
        super().__init__(kind)


def _payload(item):
    result = {}
    for f in fields(item):
        value = getattr(item, f.name)
        if isinstance(value, datetime):
            value = value.isoformat()
        elif isinstance(value, Mapping):
            value = dict(value)
        result[f.name] = value
    return Jsonb(result)


class PostgresQueryLog:
    def __init__(self, url, *, connector=psycopg.connect):
        self._url, self._connector = url, connector
        self._conn = None
        self._timeout_ms = 1000
        self._deadline = None
        self._clock = monotonic

    def set_deadline(self, deadline, clock=monotonic):
        self._deadline, self._clock = deadline, clock

    def set_timeout(self, milliseconds):
        self._timeout_ms = max(100, int(milliseconds))

    def _call(self, sql, args=()):
        expired = Event()
        timer = None
        try:
            if self._conn is None or self._conn.closed:
                self._conn = self._connector(self._url, autocommit=True, connect_timeout=1)
            conn = self._conn
            stop = self._deadline - 0.2 if self._deadline is not None else None

            def budget():
                if stop is None:
                    return self._timeout_ms
                remaining = stop - self._clock()
                if expired.is_set() or remaining < 0.1:
                    raise QueryLogError("timeout")
                return min(self._timeout_ms, int(remaining * 1000))

            timeout = budget()
            if stop is not None:

                def cancel():
                    expired.set()
                    try:
                        conn.cancel_safe(timeout=0.2)
                    except psycopg.Error:
                        # 취소 전송 실패도 연결을 재사용하지 않는다. 오류 원문은 버린다.
                        conn.close()

                timer = Timer(max(0, stop - self._clock()), cancel)
                timer.daemon = True
                timer.start()
            conn.execute("SELECT set_config('statement_timeout', %s, false)", (str(timeout),))
            if stop is not None:
                # 첫 설정 왕복에서 소비한 시간을 빼고, 전체 왕복은 별도 취소로 제한한다.
                timeout = budget()
                conn.execute("SELECT set_config('statement_timeout', %s, false)", (str(timeout),))
                budget()
            result = conn.execute(sql, args).fetchone()[0]
            if expired.is_set() or (stop is not None and self._clock() >= stop):
                raise QueryLogError("timeout")
            return result
        except psycopg.Error as exc:
            kind = (
                "timeout"
                if expired.is_set() or isinstance(exc, psycopg.errors.QueryCanceled)
                else ("rejected" if isinstance(exc, psycopg.IntegrityError) else "unavailable")
            )
            self.close()
            raise QueryLogError(kind) from None
        finally:
            if timer is not None:
                timer.cancel()
                # 취소 요청이 다음 작업을 취소하지 않도록 완료까지 연결을 넘기지 않는다.
                timer.join()
            if expired.is_set():
                self.close()

    def insert(self, record):
        self._call("SELECT qk.query_record_insert(%s)", (_payload(record),))

    def delivered(self, delivery):
        self._call("SELECT qk.query_record_delivered(%s,%s)", (delivery.run_id, _payload(delivery)))

    def feedback(self, run_id, rater_id, value):
        return self._call("SELECT qk.query_feedback_set(%s,%s,%s)", (run_id, rater_id, value))

    def store_question(self, run_id, questioner_id, question):
        return self._call("SELECT qk.query_text_store(%s,%s,%s)", (run_id, questioner_id, question))

    def mark_text_skipped(self, run_id):
        self._call("SELECT qk.query_text_skip(%s)", (run_id,))

    def question_status(self, run_id, questioner_id):
        return self._call("SELECT qk.query_text_status(%s,%s)", (run_id, questioner_id))

    def sources(self):
        data = self._call("SELECT qk.sources_summary()")
        return SourcesView(
            data["index_version"],
            datetime.fromisoformat(data["activated_at"]) if data["activated_at"] else None,
            tuple(
                SourceSummary(s["name"], s["kind"], s["documents"], datetime.fromisoformat(s["last_seen_at"]))
                for s in data["sources"]
            ),
        )

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None
