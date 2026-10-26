"""질의 시험은 세션 전용 qk_test 데이터베이스만 쓴다(QK-BOT-001 T002)."""

from collections.abc import Iterator

import psycopg
import pytest

from qello_knowledge.adapters.postgres.store import PostgresStore
from tests.localdb.store.builders import seed_index_versions
from tests.localdb.store.conftest import db_url  # noqa: F401 - 세션 fixture 재사용

pytestmark = pytest.mark.localdb


@pytest.fixture(autouse=True)
def bot_clean_tables(db_url: str) -> None:  # noqa: F811
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(
            "TRUNCATE qk.sync_run, qk.sync_source, qk.chunk, qk.embedding, qk.artifact, qk.index_version,"
            " qk.embedding_usage, qk.embedding_usage_daily, qk.generation_usage, qk.generation_usage_daily"
            " RESTART IDENTITY CASCADE"
        )
        seed_index_versions(conn)


@pytest.fixture
def bot_store(db_url: str) -> Iterator[PostgresStore]:  # noqa: F811
    with PostgresStore(db_url) as instance:
        yield instance
