"""평가의 취소/커밋 뒤 반환 지연과 멱등성."""

import json
from time import sleep

import pytest

from qello_knowledge.adapters.postgres.query_log import PostgresQueryLog
from qello_knowledge.query.recorder import QueryRecorder
from tests.localdb.query.obs_db import obs_connection, seed_record
from tests.unit.query.bot_runtime import bot_request
from tests.unit.query.obs_builders import QUESTIONER, RATER, component
from tests.unit.query.test_obs_feedback_flow import feedback_runtime

pytestmark = pytest.mark.localdb


@pytest.mark.parametrize("delay", ["statement", "return"])
def test_feedback_unknown_then_retry(db_url, delay):
    with obs_connection(db_url) as admin:
        seed_record(admin)

        class Delayed(PostgresQueryLog):
            slow = True

            def feedback(self, *args):
                result = super().feedback(*args)
                if delay == "return" and self.slow:
                    self.slow = False
                    sleep(0.65)
                return result

        port = Delayed(db_url)
        if delay == "statement":
            admin.execute(
                "CREATE FUNCTION qk.obs_delay() RETURNS trigger LANGUAGE plpgsql AS $$"
                "BEGIN PERFORM pg_sleep(1); RETURN NEW; END $$"
            )
            admin.execute(
                "CREATE TRIGGER obs_delay BEFORE INSERT ON qk.query_feedback "
                "FOR EACH ROW EXECUTE FUNCTION qk.obs_delay()"
            )
        with QueryRecorder(lambda: port, lambda: PostgresQueryLog(db_url)) as recorder:
            runtime = feedback_runtime(recorder)
            try:
                raw = bot_request(runtime, component())[1]
                assert "저장 여부를 확인하지 못했습니다" in json.loads(raw)["data"]["content"]
                recorder._front.executor.submit(lambda: None).result(2)
                count = admin.execute("SELECT count(*) FROM qk.query_feedback").fetchone()[0]
                assert count == (0 if delay == "statement" else 1)
                if delay == "statement":
                    admin.execute("DROP TRIGGER obs_delay ON qk.query_feedback")
                assert json.loads(bot_request(runtime, component())[1])["data"]["content"] == "평가를 남겼습니다."
                bot_request(runtime, component("down"))
                bot_request(runtime, component("down", user=RATER))
                assert admin.execute("SELECT rater_id,value FROM qk.query_feedback ORDER BY rater_id").fetchall() == [
                    (QUESTIONER, "down"),
                    (RATER, "down"),
                ]
            finally:
                runtime.jobs.close()
                if delay == "statement":
                    admin.execute("DROP TRIGGER IF EXISTS obs_delay ON qk.query_feedback")
                    admin.execute("DROP FUNCTION qk.obs_delay()")
