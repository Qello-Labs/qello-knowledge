"""추가 마이그레이션·권한 계약."""

import io

import pytest

from qello_knowledge.adapters.postgres.migrate import apply_migrations, load_migrations
from tests.localdb.query.obs_db import obs_connection

pytestmark = pytest.mark.localdb
TABLES = ("query_record", "query_feedback", "query_text", "query_erasure_run")
FUNCTIONS = (
    "query_record_insert",
    "query_record_delivered",
    "query_feedback_set",
    "query_text_store",
    "query_text_skip",
    "query_text_status",
)


def test_migration_permissions_and_repeat(db_url):
    with obs_connection(db_url) as conn:
        out = io.StringIO()
        assert apply_migrations(conn, load_migrations(), is_local=True, out=out) == 0
        assert "applied=0" in out.getvalue()
        for name in TABLES:
            assert conn.execute("SELECT to_regclass(%s)", ("qk." + name,)).fetchone()[0]
            for permission in ("SELECT", "INSERT", "UPDATE", "DELETE"):
                assert not conn.execute(
                    "SELECT has_table_privilege(%s,%s,%s)", ("qk_query", "qk." + name, permission)
                ).fetchone()[0]
        for name in FUNCTIONS:
            row = conn.execute(
                "SELECT prosecdef, proconfig, pg_get_userbyid(proowner),"
                " coalesce(array_to_string(proacl, ','), '') FROM pg_proc p"
                " JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='qk' AND proname=%s",
                (name,),
            ).fetchone()
            assert row[0] and "search_path=qk, pg_temp" in row[1]
            assert row[2] == conn.execute("SELECT current_user").fetchone()[0]
            assert not any(entry.startswith("=") for entry in row[3].split(","))
        assert not conn.execute("SELECT has_schema_privilege('qk_query','qk','CREATE')").fetchone()[0]
        assert not conn.execute(
            "SELECT prosecdef FROM pg_proc WHERE oid='qk.sources_summary()'::regprocedure"
        ).fetchone()[0]


@pytest.mark.parametrize(
    "table,column,value",
    [
        ("query_record", "run_id", "bad"),
        ("query_record", "questioner_id", "bad"),
        ("query_record", "status", "bad"),
        ("query_feedback", "rater_id", "bad"),
        ("query_feedback", "value", "bad"),
        ("query_text", "question", ""),
        ("query_text", "question", "x" * 4001),
        ("query_text", "consent_method", "other"),
    ],
)
def test_table_constraints(db_url, table, column, value):
    import psycopg
    from psycopg import sql

    from tests.localdb.query.obs_db import seed_feedback, seed_record, seed_text

    with obs_connection(db_url) as conn:
        seed_record(conn)
        seed_feedback(conn)
        seed_text(conn)
        with pytest.raises(psycopg.IntegrityError):
            conn.execute(
                sql.SQL("UPDATE qk.{} SET {}=%s").format(sql.Identifier(table), sql.Identifier(column)), (value,)
            )
