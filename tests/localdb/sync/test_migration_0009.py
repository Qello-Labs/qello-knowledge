"""마이그레이션 0009(QK-STO-002 research R-18, data-model 1절). 0008 상태의 행은 SQL로 직접 넣는다(tasks 공통 규칙)."""

import io
from datetime import UTC, datetime

import psycopg
import pytest

from qello_knowledge.adapters.postgres.migrate import apply_migrations, load_migrations
from tests.localdb.store.builders import create_database, database_url_for, drop_database

pytestmark = pytest.mark.localdb

ACTIVATED = datetime(2026, 10, 30, 1, 2, 3, tzinfo=UTC)
COLLECTED = datetime(2026, 10, 29, 4, 5, 6, tzinfo=UTC)
MODIFIED = datetime(2026, 10, 28, 7, 8, 9, tzinfo=UTC)


def _versions_before_0009():
    return [m for m in load_migrations() if m.version < 9]


@pytest.fixture
def legacy_db():
    name = create_database()
    try:
        with psycopg.connect(database_url_for(name), autocommit=True) as conn:
            assert apply_migrations(conn, _versions_before_0009(), is_local=True, out=io.StringIO()) == 0
            conn.execute(
                "INSERT INTO qk.index_version(id,embedding_model,dimension,chunking_version,metadata_schema_version,"
                "status,activated_at) VALUES ('iv-old','m',1024,'c','meta-v1','active',%s)",
                (ACTIVATED,),
            )
            artifact_id = conn.execute(
                "INSERT INTO qk.artifact(source_kind,source_id,source_url,source_version,source_modified_at,"
                "collected_at,content_hash,artifact_kind,title,access_scope) VALUES "
                "('fake','doc-1','https://example.invalid/doc-1','rev-1',%s,%s,'h','markdown','Doc','team') "
                "RETURNING id",
                (MODIFIED, COLLECTED),
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO qk.chunk(artifact_id,index_version,source_version,locator,ordinal,body,search_text,"
                "chunking_version) VALUES (%s,'iv-old','rev-1','{\"path\":\"a.md\"}',0,'body','body','c')",
                (artifact_id,),
            )
        yield database_url_for(name)
    finally:
        drop_database(name)


def _migrate(url):
    with psycopg.connect(url, autocommit=True) as conn:
        out = io.StringIO()
        assert apply_migrations(conn, load_migrations(), is_local=True, out=out) == 0
        return out.getvalue()


def test_0009_backfills_chunk_provenance_and_first_activation(legacy_db):
    _migrate(legacy_db)
    with psycopg.connect(legacy_db, autocommit=True) as conn:
        row = conn.execute("SELECT source_url, source_modified_at, collected_at FROM qk.chunk").fetchone()
        assert row == ("https://example.invalid/doc-1", MODIFIED, COLLECTED)
        transitions = conn.execute(
            "SELECT kind, version, before_active, after_active, target, at, details FROM qk.index_transition"
        ).fetchall()
        assert transitions == [
            ("first_activation", "iv-old", None, "iv-old", "unknown", ACTIVATED, {"backfilled": True})
        ]
        assert conn.execute("SELECT pruned_at FROM qk.index_version").fetchone() == (None,)


def test_0009_constraints(legacy_db):
    _migrate(legacy_db)
    with psycopg.connect(legacy_db, autocommit=True) as conn:

        def rejected(statement, params=()):
            with pytest.raises((psycopg.errors.CheckViolation, psycopg.errors.NotNullViolation)), conn.transaction():
                conn.execute(statement, params)

        rejected("UPDATE qk.index_version SET pruned_at=now() WHERE id='iv-old'")
        conn.execute(
            "INSERT INTO qk.sync_run(run_id,trigger,target,rules_version,chunking_version,index_version,status) "
            "VALUES ('r1','manual','local','s','c','iv-old','running')"
        )
        assert conn.execute("SELECT kind FROM qk.sync_run WHERE run_id='r1'").fetchone() == ("sync",)
        rejected("UPDATE qk.sync_run SET kind='other' WHERE run_id='r1'")
        conn.execute("UPDATE qk.sync_run SET kind='reindex' WHERE run_id='r1'")
        conn.execute("UPDATE qk.artifact SET processed_outcome='not_target'")
        rejected("UPDATE qk.artifact SET processed_outcome='other'")

        insert = (
            "INSERT INTO qk.index_transition(kind,version,documents,chunks,target,gate_record_id,gate_record_sha256,"
            "reason,deleted_chunks) VALUES (%s,'iv-old',0,0,%s,%s,%s,%s,%s)"
        )
        rejected(insert, ("activation", "local", None, None, None, None))
        rejected(insert, ("activation", "local", "gate-1", None, None, None))
        rejected(insert, ("prune", "local", "gate-1", None, None, 0))
        rejected(insert, ("rollback", "local", None, None, None, None))
        rejected(insert, ("rollback", "local", None, None, "", None))
        rejected(insert, ("rollback", "local", None, None, "x" * 201, None))
        rejected(insert, ("prune", "local", None, None, None, None))
        rejected(insert, ("reuse", "elsewhere", None, None, None, None))
        rejected(insert, ("other", "local", None, None, None, None))
        conn.execute(insert, ("activation", "remote", "gate-1", "a" * 64, None, None))
        conn.execute(insert, ("rollback", "local", None, None, "x" * 200, None))
        conn.execute(insert, ("prune", "local", None, None, None, 3))
        conn.execute(insert, ("reuse", "local", None, None, None, None))


def test_0009_reapplication_changes_nothing(legacy_db):
    _migrate(legacy_db)
    assert "applied=0" in _migrate(legacy_db)
