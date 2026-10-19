"""저장소 테스트 기반(QK-STO-001 research R-10).

세션마다 로컬 DB에 `qk_test_<무작위>` 데이터베이스를 만들어 전체 마이그레이션을 적용하고 끝나면 지운다.
공유 `postgres` 데이터베이스는 건드리지 않는다(AGENTS.md 4절).
"""

from __future__ import annotations

import io
import os
from collections.abc import Iterator

import psycopg
import pytest

from qello_knowledge.adapters.postgres.migrate import apply_migrations, load_migrations
from qello_knowledge.adapters.postgres.store import PostgresStore
from tests.conftest import _local_db_reachable, local_db_port
from tests.localdb.store.builders import create_database, database_url_for, drop_database, seed_index_versions


@pytest.fixture(scope="session")
def db_url() -> Iterator[str]:
    port = local_db_port()
    if not _local_db_reachable(port):
        message = f"로컬 DB(127.0.0.1:{port})에 연결할 수 없다. `uv run qk-dev db up`을 먼저 실행한다"
        if os.environ.get("QK_REQUIRE_LOCALDB") == "1":
            pytest.fail(message)
        pytest.skip(message)
    name = create_database()
    url = database_url_for(name)
    try:
        with psycopg.connect(url, autocommit=True) as conn:
            code = apply_migrations(conn, load_migrations(), is_local=True, out=io.StringIO())
        assert code == 0
        yield url
    finally:
        drop_database(name)


@pytest.fixture(autouse=True)
def clean_tables(db_url: str) -> None:
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute("TRUNCATE qk.chunk, qk.embedding, qk.artifact, qk.index_version RESTART IDENTITY CASCADE")
        seed_index_versions(conn)


@pytest.fixture
def store(db_url: str) -> Iterator[PostgresStore]:
    with PostgresStore(db_url) as instance:
        yield instance
