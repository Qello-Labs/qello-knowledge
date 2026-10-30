"""질의 역할 직접 접근 금지와 입력 허용 목록."""

import psycopg
import pytest
from psycopg import sql
from psycopg.types.json import Jsonb

from tests.localdb.query.obs_db import obs_connection, query_connection, record_payload, seed_record
from tests.unit.query.obs_builders import QUESTIONER, RUN

pytestmark = pytest.mark.localdb


def test_query_role_and_functions(db_url):
    with obs_connection(db_url), query_connection(db_url) as conn:
        for table in ("query_record", "query_feedback", "query_text", "query_erasure_run"):
            for statement in ("SELECT * FROM {}", "DELETE FROM {}", "INSERT INTO {} DEFAULT VALUES"):
                command = sql.SQL(statement).format(sql.Identifier("qk", table))
                with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
                    conn.execute(command)
        payload = record_payload(
            stage_ms={"retrieve": 4, "bad": "합성 질문 1", "generate": False},
            retrieval={"neurons": 2.5, "measured": True, "question": "합성 질문 1"},
            model_id="합성 질문 1",
            question="합성 질문 1",
        )
        conn.execute("SELECT qk.query_record_insert(%s)", (Jsonb(payload),))
        conn.execute("SELECT qk.query_record_insert(%s)", (Jsonb(payload),))
        row = conn.execute("SELECT qk.query_text_status(%s,%s)", (RUN, QUESTIONER)).fetchone()
        assert row == ("none",)
        # 별도 관리 연결은 아직 커밋 전인 역할 트랜잭션을 읽지 않는다.
        conn.execute("RESET ROLE")
        row = conn.execute("SELECT stage_ms,retrieval,model_id FROM qk.query_record").fetchone()
        conn.execute("SET LOCAL ROLE qk_query")
        assert row == ({"retrieve": 4}, {"neurons": 2.5, "measured": True}, None)
        assert (
            conn.execute("SELECT qk.query_feedback_set(%s,%s,%s)", (RUN, QUESTIONER, "down")).fetchone()[0] == "stored"
        )
        assert (
            conn.execute("SELECT qk.query_text_store(%s,%s,%s)", (RUN, QUESTIONER, "합성 질문 1")).fetchone()[0]
            == "stored"
        )
        assert conn.execute("SELECT qk.query_text_status(%s,%s)", (RUN, QUESTIONER)).fetchone()[0] == "stored"
        conn.execute("SELECT qk.query_text_skip(%s)", (RUN,))
        conn.execute("SELECT qk.query_record_delivered(%s,%s)", (RUN, Jsonb({"total_ms": 20})))
        conn.execute("SELECT qk.sources_summary()")


@pytest.mark.parametrize("changes", [{"run_id": "bad"}, {"questioner_id": "bad"}, {"status": "bad"}])
def test_invalid_record_rejected(db_url, changes):
    with obs_connection(db_url) as conn:
        with pytest.raises(psycopg.Error):
            seed_record(conn, **changes)


@pytest.mark.parametrize("field", ["failure", "index_version", "model_id", "prompt_version"])
@pytest.mark.parametrize("value", ["x" * 65, "합성 질문 1", {"nested": "합성 질문 1"}, 42])
def test_string_metadata_filters(db_url, field, value):
    from psycopg import sql

    with obs_connection(db_url) as conn:
        seed_record(conn, **{field: value})
        assert conn.execute(sql.SQL("SELECT {} FROM qk.query_record").format(sql.Identifier(field))).fetchone() == (
            None,
        )


@pytest.mark.parametrize("table", ["query_record", "query_feedback", "query_text", "query_erasure_run"])
def test_updates_are_forbidden(db_url, table):
    from psycopg import sql

    column = (
        "status"
        if table == "query_record"
        else ("value" if table == "query_feedback" else ("question" if table == "query_text" else "kind"))
    )
    with query_connection(db_url) as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(
            sql.SQL("UPDATE qk.{} SET {}={} WHERE false").format(
                sql.Identifier(table), sql.Identifier(column), sql.Identifier(column)
            )
        )
