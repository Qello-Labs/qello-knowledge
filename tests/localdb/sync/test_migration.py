import io

import psycopg
import pytest
from psycopg import sql

from qello_knowledge.adapters.postgres.migrate import apply_migrations, load_migrations
from tests.localdb.store.builders import artifact

pytestmark = pytest.mark.localdb


def test_schema_has_location_state_constraints_and_result_primary_key(db_url, store):
    identity = artifact(store, "sample")
    with psycopg.connect(db_url, autocommit=True) as conn:
        row = conn.execute(
            "SELECT location, purge_pending, processed_outcome FROM qk.artifact WHERE id=%s", (identity,)
        ).fetchone()
        assert row == (None, [], None)
        for column, bad in [
            ("takedown_reason", "bad"),
            ("purge_reason", "source_missing"),
            ("processed_outcome", "bad"),
        ]:
            with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
                conn.execute(
                    sql.SQL("UPDATE qk.artifact SET {}=%s WHERE id=%s").format(sql.Identifier(column)), (bad, identity)
                )
        conn.execute("INSERT INTO qk.sync_source(source_name,source_kind,scope_key) VALUES ('one','fake','fake:')")
        with pytest.raises(psycopg.errors.UniqueViolation), conn.transaction():
            conn.execute("INSERT INTO qk.sync_source(source_name,source_kind,scope_key) VALUES ('two','fake','fake:')")
        definition = conn.execute(
            "SELECT pg_get_constraintdef(oid) FROM pg_constraint "
            "WHERE conrelid='qk.sync_document_result'::regclass AND contype='p'"
        ).fetchone()[0]
        assert definition == "PRIMARY KEY (run_id, doc_key, action)"
        cascades = conn.execute(
            "SELECT confdeltype FROM pg_constraint WHERE conrelid IN "
            "('qk.sync_document_result'::regclass,'qk.sync_run_source'::regclass) AND contype='f'"
        ).fetchall()
        assert cascades == [("c",), ("c",)]


def test_migration_reapplication_changes_nothing(db_url):
    with psycopg.connect(db_url, autocommit=True) as conn:
        out = io.StringIO()
        assert apply_migrations(conn, load_migrations(), is_local=True, out=out) == 0
        assert "applied=0 skipped=4" in out.getvalue()


def test_0004_preserves_existing_artifact_values():
    from qello_knowledge.adapters.postgres.store import PostgresStore
    from tests.localdb.store.builders import create_database, database_url_for, drop_database

    name = create_database()
    try:
        with psycopg.connect(database_url_for(name), autocommit=True) as conn:
            migrations = load_migrations()
            assert apply_migrations(conn, migrations[:3], is_local=True, out=io.StringIO()) == 0
            with PostgresStore(database_url_for(name)) as old:
                identity = artifact(old, "legacy")
            before = conn.execute("SELECT row_to_json(a) FROM qk.artifact a WHERE id=%s", (identity,)).fetchone()[0]
            assert apply_migrations(conn, migrations, is_local=True, out=io.StringIO()) == 0
            after = conn.execute("SELECT row_to_json(a) FROM qk.artifact a WHERE id=%s", (identity,)).fetchone()[0]
            assert all(after[key] == value for key, value in before.items())
            assert after["location"] is None and after["purge_pending"] == []
            for reason in (
                "security_path",
                "security_secret",
                "security_access",
                "config_excluded",
                "source_missing",
                "not_target",
                "source_disabled",
            ):
                conn.execute("UPDATE qk.artifact SET takedown_reason=%s WHERE id=%s", (reason, identity))
            with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
                conn.execute("UPDATE qk.artifact SET purge_pending=ARRAY['v'] WHERE id=%s", (identity,))
    finally:
        drop_database(name)
