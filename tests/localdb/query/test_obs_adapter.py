"""연결 왕복과 안전한 저장소 오류."""

from datetime import UTC, datetime

import pytest

from qello_knowledge.adapters.postgres.query_log import PostgresQueryLog, QueryLogError
from qello_knowledge.domain.query_log import QueryDelivery, QueryRecord, RecordStatus
from tests.localdb.query.obs_db import obs_connection
from tests.unit.query.obs_builders import QUESTIONER, RATER, RUN

pytestmark = pytest.mark.localdb


def test_adapter_roundtrip_and_reconnect(db_url):
    with obs_connection(db_url) as admin:
        port = PostgresQueryLog(db_url)
        try:
            port.insert(QueryRecord(RUN, datetime.now(UTC), QUESTIONER, False, RecordStatus.ANSWERED))
            assert port.feedback(RUN, QUESTIONER, "up") == "stored"
            assert port.feedback("missing", QUESTIONER, "up") == "missing"
            assert port.question_status(RUN, QUESTIONER) == "none"
            assert port.store_question(RUN, RATER, "합성 질문 1") == "not_questioner"
            assert port.store_question(RUN, QUESTIONER, "합성 질문 1") == "stored"
            assert port.store_question(RUN, QUESTIONER, "합성 질문 2") == "exists"
            assert port.question_status(RUN, QUESTIONER) == "stored"
            assert port.question_status(RUN, RATER) == "not_questioner"
            assert port.question_status("missing", RATER) == "missing"
            port.delivered(QueryDelivery(RUN, final_status=RecordStatus.FAILED, total_ms=20))
            assert admin.execute("SELECT status FROM qk.query_record").fetchone()[0] == "answered"
            port.delivered(QueryDelivery(RUN, final_status=RecordStatus.UNDELIVERED, total_ms=30))
            assert admin.execute("SELECT status FROM qk.query_record").fetchone()[0] == "undelivered"
            port.close()
            assert port.question_status(RUN, QUESTIONER) == "stored"
            with pytest.raises(QueryLogError, match="^rejected$"):
                port.feedback(RUN, "합성 질문 1", "up")
        finally:
            port.close()


def test_statement_timeout_rolls_back_and_next_call_recovers(db_url):
    from tests.localdb.query.obs_db import seed_record

    with obs_connection(db_url) as admin:
        seed_record(admin)
        admin.execute(
            "CREATE FUNCTION qk.obs_delay() RETURNS trigger LANGUAGE plpgsql AS $$"
            "BEGIN PERFORM pg_sleep(1); RETURN NEW; END $$"
        )
        admin.execute(
            "CREATE TRIGGER obs_delay BEFORE INSERT ON qk.query_feedback FOR EACH ROW EXECUTE FUNCTION qk.obs_delay()"
        )
        port = PostgresQueryLog(db_url)
        try:
            port.set_timeout(100)
            with pytest.raises(QueryLogError, match="^timeout$"):
                port.feedback(RUN, QUESTIONER, "down")
            assert admin.execute("SELECT count(*) FROM qk.query_feedback").fetchone()[0] == 0
            admin.execute("DROP TRIGGER obs_delay ON qk.query_feedback")
            assert port.feedback(RUN, QUESTIONER, "down") == "stored"
        finally:
            port.close()
            admin.execute("DROP TRIGGER IF EXISTS obs_delay ON qk.query_feedback")
            admin.execute("DROP FUNCTION qk.obs_delay()")


@pytest.mark.parametrize("delay", ["setting", "function"])
def test_front_cancel_includes_setting_roundtrip_and_rolls_back(db_url, delay):
    from threading import Event
    from time import monotonic, sleep

    import psycopg

    from qello_knowledge.query.recorder import QueryRecorder
    from tests.localdb.query.obs_db import seed_record

    # Timer와 Future 대기 뒤 Python 스레드가 재개되는 데 최대 50ms를 허용한다.
    # 200ms 여유보다 작으므로 마감에야 취소하는 구현은 통과할 수 없다.
    scheduling_tolerance = 0.05
    cancel_return, cancel_sent = Event(), Event()
    cancel_times, connections = [], []
    with obs_connection(db_url) as admin:
        seed_record(admin)
        admin.execute(
            "CREATE FUNCTION qk.obs_cancel_delay() RETURNS trigger LANGUAGE plpgsql AS $$"
            "BEGIN IF current_setting('qk.obs_delay', true) = 'on' THEN PERFORM pg_sleep(2); END IF; "
            "RETURN NEW; END $$"
        )
        admin.execute(
            "CREATE TRIGGER obs_cancel_delay AFTER INSERT ON qk.query_text "
            "FOR EACH ROW EXECUTE FUNCTION qk.obs_cancel_delay()"
        )

        class DelayedConnection:
            def __init__(self, conn, inject):
                self.conn, self.inject, self.first = conn, inject, True
                self.backend_pid = conn.info.backend_pid

            def __getattr__(self, name):
                return getattr(self.conn, name)

            def execute(self, sql, args=()):
                if self.inject and self.first and "set_config" in sql:
                    self.first = False
                    if delay == "setting":
                        self.conn.execute("SELECT pg_sleep(2)")
                    else:
                        sleep(0.6)
                if self.inject and "query_text_store" in sql:
                    # 서버 문장 타이머와의 경합을 배제하고 클라이언트 취소만 검증한다.
                    self.conn.execute("SET statement_timeout = 0")
                return self.conn.execute(sql, args)

            def cancel_safe(self, *, timeout):
                cancel_times.append(monotonic())
                try:
                    self.conn.cancel_safe(timeout=timeout)
                finally:
                    cancel_sent.set()
                    # 취소 요청의 반환을 늦춰도 호출자는 절대 마감에 돌아와야 한다.
                    assert cancel_return.wait(3)

        def connect(*args, **kwargs):
            conn = DelayedConnection(psycopg.connect(*args, **kwargs), inject=not connections)
            if conn.inject:
                conn.execute("SET qk.obs_delay = 'on'")
            connections.append(conn)
            return conn

        port = PostgresQueryLog(db_url, connector=connect)
        # 최초 연결 시간을 측정에서 분리하고 취소 요청 예정 시각과 직접 비교한다.
        port._conn = connect(db_url, autocommit=True)
        recorder = QueryRecorder(lambda: port)
        start = monotonic()
        deadline = start + 1
        try:
            result = recorder.front("store_question", RUN, QUESTIONER, "합성 질문 1", deadline=deadline)
            returned = monotonic()
            assert result.status == "timeout"
            assert deadline <= returned <= deadline + scheduling_tolerance
            assert cancel_sent.is_set()
            assert len(cancel_times) == 1
            assert deadline - 0.2 <= cancel_times[0] <= deadline - 0.2 + scheduling_tolerance
            assert admin.execute("SELECT count(*) FROM qk.query_text").fetchone()[0] == 0
            assert admin.execute("SELECT consented FROM qk.query_record").fetchone()[0] is False

            cancel_return.set()
            recovered = recorder.front("store_question", RUN, QUESTIONER, "합성 질문 1", deadline=monotonic() + 1.5)
            assert (recovered.status, recovered.value) == ("ok", "stored")
            assert len(connections) == 2
            assert connections[0].closed
            assert port._conn is connections[1]
            assert connections[0].backend_pid != connections[1].backend_pid
            assert len(cancel_times) == 1
            assert admin.execute("SELECT count(*) FROM qk.query_text").fetchone()[0] == 1
            assert admin.execute("SELECT consented FROM qk.query_record").fetchone()[0] is True
        finally:
            cancel_return.set()
            recorder.close()
            admin.execute("DROP TRIGGER obs_cancel_delay ON qk.query_text")
            admin.execute("DROP FUNCTION qk.obs_cancel_delay()")
