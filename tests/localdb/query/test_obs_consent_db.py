"""동의 함수와 결과 불명 뒤 모든 재선택 경로의 실제 저장 상태."""

from time import sleep

import pytest

from qello_knowledge.adapters.postgres.query_log import PostgresQueryLog
from qello_knowledge.query.recorder import QueryRecorder
from tests.localdb.query.obs_db import obs_connection, seed_record
from tests.unit.query.obs_builders import QUESTIONER, RATER, RUN
from tests.unit.query.test_obs_consent_flow import click, consent_runtime

pytestmark = pytest.mark.localdb


@pytest.mark.parametrize("delay", ["statement", "return"])
@pytest.mark.parametrize("after", ["keep", "skip", "expired", "restart"])
def test_unknown_consent_matches_database(db_url, delay, after):
    with obs_connection(db_url) as admin:
        seed_record(admin)

        class Delayed(PostgresQueryLog):
            slow = True

            def store_question(self, *args):
                result = super().store_question(*args)
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
                "CREATE TRIGGER obs_delay BEFORE INSERT ON qk.query_text FOR EACH ROW EXECUTE FUNCTION qk.obs_delay()"
            )
        with QueryRecorder(lambda: port, lambda: PostgresQueryLog(db_url)) as recorder:
            runtime, p = consent_runtime(recorder)
            try:
                assert "저장 여부를 확인하지 못했습니다" in click(runtime, "keep")["data"]["content"]
                recorder._front.executor.submit(lambda: None).result(2)
                count = admin.execute("SELECT count(*) FROM qk.query_text").fetchone()[0]
                assert count == (0 if delay == "statement" else 1)
                if delay == "statement":
                    admin.execute("DROP TRIGGER obs_delay ON qk.query_text")
                if after in ("expired", "restart"):
                    p.close()
                action = after if after in ("keep", "skip") else "keep"
                text = click(runtime, action)["data"]["content"]
                if after == "keep":
                    assert "질문을 저장했습니다" in text
                elif count:
                    assert "이미 저장된 질문" in text
                elif after == "skip":
                    assert text == "저장하지 않았습니다."
                else:
                    assert "질문이 남아 있지 않아" in text
                rows = admin.execute("SELECT question,consent_method FROM qk.query_text").fetchall()
                assert rows == ([("합성 질문 1", "feedback_down")] if count or after == "keep" else [])
                assert port.question_status(RUN, RATER) == "not_questioner"
                assert port.question_status("missing", QUESTIONER) == "missing"
                assert admin.execute("SELECT consented FROM qk.query_record").fetchone()[0] == bool(rows)
            finally:
                runtime.jobs.close()
                if delay == "statement":
                    admin.execute("DROP TRIGGER IF EXISTS obs_delay ON qk.query_text")
                    admin.execute("DROP FUNCTION qk.obs_delay()")
