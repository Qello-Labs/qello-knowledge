"""세션 전용 qk_test DB에서 질의 역할의 성공·거부 목록을 검증한다(T048)."""

from contextlib import contextmanager

import psycopg
import pytest

from qello_knowledge.adapters.postgres.migrate import load_migrations
from qello_knowledge.adapters.postgres.store import PostgresStore
from tests.localdb.query.bot_builders import bot_document
from tests.localdb.store.builders import vec

pytestmark = pytest.mark.localdb

BOT_EMBED_RECORD = "SELECT qk.embedding_record('bot-query','synthetic-model',1,12,1,1,false,'ok',3000)"
BOT_GENERATION_RECORD = (
    "SELECT qk.generation_record('bot-query','synthetic-model','synthetic-prompt',1::smallint,"
    "10,5,10,1,false,'ok',false,3000)"
)
BOT_INDEX_INSERT = (
    "INSERT INTO qk.embedding_usage(purpose,run_id,model_version,input_count,input_bytes,estimated_neurons,state)"
    " VALUES('index','bot-index','synthetic-model',1,12,1,'reserved')"
)


@contextmanager
def bot_as_query(db_url):
    with psycopg.connect(db_url, autocommit=True) as conn:
        assert conn.execute("SELECT 1 FROM pg_roles WHERE rolname='qk_query'").fetchone() is not None, (
            "0007 role missing"
        )
        # 로컬 postgres는 비슈퍼유저다. PG16+ 역할 생성자의 ADMIN은 SET을 포함하지 않는다.
        # 역할 멤버십은 클러스터 전역이므로 DB 삭제에 맡기지 않고 기존 상태로 롤백한다.
        with conn.transaction(force_rollback=True):
            conn.execute("GRANT qk_query TO CURRENT_USER WITH SET TRUE, INHERIT FALSE")
            conn.execute("SET LOCAL ROLE qk_query")
            yield conn


def bot_seed_usage(conn):
    conn.execute(BOT_EMBED_RECORD)
    conn.execute(BOT_GENERATION_RECORD)


def test_bot_query_role_reads_searches_context_and_records_usage(db_url, bot_store):
    bot_document(bot_store, "bot-role-document", ["합성 검색 자료", "합성 이웃 자료"], vector=vec(1))
    with psycopg.connect(db_url, autocommit=True) as owner:
        ids = [row[0] for row in owner.execute("SELECT id FROM qk.chunk ORDER BY ordinal")]
    with bot_as_query(db_url) as conn:
        assert conn.execute("SELECT qk.search_vector(%s::vector,1)", (str(vec(1)),)).fetchone()[0]["hits"]
        assert conn.execute("SELECT qk.search_keyword('합성',1)").fetchone()[0]["hits"]
        assert conn.execute("SELECT qk.search_keyword_terms(ARRAY['합성'],1)").fetchone()[0]["hits"]
        assert conn.execute("SELECT qk.chunk_neighbors(%s,0,1)", (ids[0],)).fetchone()[0]["center"]
        assert conn.execute("SELECT qk.chunk_context(%s::bigint[],0,1)", ([ids[0]],)).fetchone()[0]["items"]
        assert conn.execute(BOT_EMBED_RECORD).fetchone()[0]["query_used"] == 1
        assert conn.execute("SELECT qk.embedding_usage_today(5000,3000)").fetchone()[0]["query_used"] == 1
        assert conn.execute(BOT_GENERATION_RECORD).fetchone()[0]["generation_used"] == 1
        assert conn.execute("SELECT qk.generation_usage_today(3000)").fetchone()[0]["answer_total"] == 2
        store = PostgresStore(db_url)
        store._conn = conn
        try:
            assert store.search_keyword_terms(("합성",), 1).hits
        finally:
            store._conn = None


@pytest.mark.parametrize(
    "query",
    [
        "SELECT qk.embedding_reserve('bot-index','synthetic-model',1,12,1,100000)",
        BOT_INDEX_INSERT,
        "SELECT qk.embedding_settle(1,1,false,'ok')",
        "SELECT qk.embedding_usage_prune(1)",
        "SELECT qk.generation_usage_prune(1)",
        "UPDATE qk.embedding_usage SET neurons=2 WHERE run_id='bot-query'",
        "DELETE FROM qk.embedding_usage WHERE run_id='bot-query'",
        "UPDATE qk.generation_usage SET neurons=2 WHERE run_id='bot-query'",
        "DELETE FROM qk.generation_usage WHERE run_id='bot-query'",
        "INSERT INTO qk.embedding_usage_daily VALUES(current_date,'query','synthetic-model',1,1,1)",
        "INSERT INTO qk.generation_usage_daily VALUES(current_date,'synthetic-model',1,1,1)",
        "CREATE TABLE qk.bot_denied(id int)",
        "ALTER TABLE qk.artifact ADD COLUMN bot_denied int",
    ],
)
def test_bot_query_role_denies_index_reservation_mutation_and_schema_changes(db_url, query):
    with psycopg.connect(db_url, autocommit=True) as owner:
        bot_seed_usage(owner)
    with bot_as_query(db_url) as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(query)


@pytest.mark.parametrize("table", ["artifact", "chunk", "embedding", "index_version"])
@pytest.mark.parametrize(
    "operation", ["INSERT INTO {table} DEFAULT VALUES", "DELETE FROM {table} WHERE false", "TRUNCATE {table}"]
)
def test_bot_query_role_cannot_write_or_remove_index_data(db_url, table, operation):
    from psycopg import sql

    statement = sql.SQL(operation).format(table=sql.Identifier("qk", table))
    with bot_as_query(db_url) as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(statement)


@pytest.mark.parametrize("table", ["sync_source", "sync_run", "sync_run_source", "sync_document_result"])
@pytest.mark.parametrize(
    "operation", ["SELECT * FROM {table}", "INSERT INTO {table} DEFAULT VALUES", "DELETE FROM {table} WHERE false"]
)
def test_bot_query_role_cannot_read_or_write_sync_data(db_url, table, operation):
    from psycopg import sql

    statement = sql.SQL(operation).format(table=sql.Identifier("qk", table))
    with bot_as_query(db_url) as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(statement)


def test_bot_owner_index_writes_still_work_and_rls_is_not_forced(db_url):
    with psycopg.connect(db_url, autocommit=True) as conn:
        row = conn.execute(
            "SELECT relrowsecurity,relforcerowsecurity FROM pg_class WHERE oid='qk.embedding_usage'::regclass"
        ).fetchone()
        assert row == (True, False)
        assert conn.execute("SELECT qk.embedding_reserve('bot-owner','synthetic-model',1,12,1,100000)").fetchone()[0][
            "granted"
        ]
        conn.execute(BOT_INDEX_INSERT)
        assert conn.execute("SELECT count(*) FROM qk.embedding_usage WHERE purpose='index'").fetchone()[0] == 2


def test_bot_migration_is_idempotent_and_grants_only_usage_sequence_privileges(db_url):
    migration = next(m for m in load_migrations() if m.version == 7)
    with psycopg.connect(db_url, autocommit=True) as conn:
        for _ in range(2):
            with conn.transaction():
                conn.execute(migration.sql)
        assert conn.execute("SELECT rolcanlogin FROM pg_roles WHERE rolname='qk_query'").fetchone() == (False,)
    with bot_as_query(db_url) as conn:
        for sequence in ("qk.embedding_usage_id_seq", "qk.generation_usage_id_seq"):
            assert conn.execute("SELECT has_sequence_privilege(current_user,%s,'USAGE')", (sequence,)).fetchone()[0]
            assert not conn.execute("SELECT has_sequence_privilege(current_user,%s,'UPDATE')", (sequence,)).fetchone()[
                0
            ]
        assert (
            len(
                conn.execute(
                    "SELECT * FROM pg_policies WHERE schemaname='qk' AND tablename='embedding_usage'"
                ).fetchall()
            )
            == 2
        )
