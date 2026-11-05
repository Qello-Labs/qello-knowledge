"""배포 순서 보호(QK-STO-002 research R-18). 0009가 없는 DB에서는 쓰기 전에 멈춘다."""

import io

import psycopg
import pytest

from qello_knowledge.adapters.postgres.migrate import apply_migrations, load_migrations
from qello_knowledge.adapters.postgres.sync_store import PostgresSyncStore, schema_ready
from qello_knowledge.domain.store import SchemaOutdated
from qello_knowledge.ports.sync import RunInfo
from tests.localdb.store.builders import create_database, database_url_for, drop_database

pytestmark = pytest.mark.localdb


@pytest.fixture
def old_db():
    name = create_database()
    try:
        with psycopg.connect(database_url_for(name), autocommit=True) as conn:
            migrations = [m for m in load_migrations() if m.version < 9]
            assert apply_migrations(conn, migrations, is_local=True, out=io.StringIO()) == 0
        yield database_url_for(name)
    finally:
        drop_database(name)


def _counts(url):
    with psycopg.connect(url) as conn:
        return conn.execute(
            "SELECT (SELECT count(*) FROM qk.sync_run), (SELECT count(*) FROM qk.index_version)"
        ).fetchone()


def test_sync_store_refuses_writes_without_0009(old_db):
    run = RunInfo("sync-x", "manual", "local", "rules", "chunk", "iv-x", ("fake",))
    with PostgresSyncStore(old_db, current_version="iv-x") as store:
        with pytest.raises(SchemaOutdated):
            store.begin_run(run, ["fake"])
        with pytest.raises(SchemaOutdated):
            store.activate("iv-x")
    assert _counts(old_db) == (0, 0)


def test_index_version_store_refuses_without_0009(old_db):
    from qello_knowledge.adapters.postgres.index_versions import PostgresIndexVersionStore

    with PostgresIndexVersionStore(old_db, current_version="iv-x", target="local") as versions:
        with pytest.raises(SchemaOutdated):
            versions.versions()


def test_schema_check_accepts_any_later_migration(old_db):
    with psycopg.connect(old_db, autocommit=True) as conn:
        assert schema_ready(conn) is False
        conn.execute(
            "INSERT INTO qk.schema_migration(version,description,checksum,destructive,result)"
            " VALUES (10,'later','x',false,'success')"
        )
        assert schema_ready(conn) is True


def test_schema_check_passes_on_fully_migrated_db(db_url):
    with psycopg.connect(db_url, autocommit=True) as conn:
        assert schema_ready(conn) is True
