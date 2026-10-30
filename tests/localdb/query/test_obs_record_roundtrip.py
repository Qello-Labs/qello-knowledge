"""질의 작업 → 기록기 → 질의 역할 함수의 메타데이터 왕복."""

import pytest

from qello_knowledge.adapters.postgres.query_log import PostgresQueryLog
from qello_knowledge.query.recorder import QueryRecorder
from tests.localdb.query.obs_db import obs_connection, query_connection
from tests.unit.query.bot_runtime import bot_runtime
from tests.unit.query.obs_builders import QUESTIONER
from tests.unit.query.test_obs_query_record import run_query

pytestmark = pytest.mark.localdb


@pytest.mark.parametrize("undelivered", [False, True])
def test_query_role_roundtrip(db_url, undelivered):
    with obs_connection(db_url), query_connection(db_url) as conn:
        port = PostgresQueryLog(db_url)
        port._conn = conn
        recorder = QueryRecorder(lambda: port, lambda: port)
        runtime = bot_runtime(recorder=recorder)
        try:
            if undelivered:
                runtime.jobs._deliver = lambda *args: (_ for _ in ()).throw(OSError())
            run = run_query(runtime)
            recorder._back.executor.submit(lambda: None).result(1)
            conn.execute("RESET ROLE")
            row = conn.execute("SELECT run_id,questioner_id,status FROM qk.query_record").fetchone()
            assert row == (run, QUESTIONER, "undelivered" if undelivered else "answered")
            columns = {
                r[0]
                for r in conn.execute(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_schema='qk' AND table_name='query_record'"
                )
            }
            assert not columns & {"question", "answer", "title", "source_url", "channel_id", "guild_id", "token"}
        finally:
            # 기존 트랜잭션 도우미가 연결·멤버십을 롤백한다.
            port._conn = None
            recorder.close()
            runtime.jobs.close()
