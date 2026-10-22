"""검색 로컬 DB 시험 기반(QK-RET-001 tasks T001).

QK-STO-001의 세션 데이터베이스(`db_url`)를 재사용하고, 시험마다 표를 비운 뒤 활성 `v1`·보관 `v0` 인덱스 버전을 넣는다.
공유 `postgres` 데이터베이스는 건드리지 않는다(AGENTS.md 4절).
"""

from __future__ import annotations

from collections.abc import Iterator

import psycopg
import pytest

from qello_knowledge.adapters.postgres.store import PostgresStore
from tests.localdb.store.builders import seed_index_versions
from tests.localdb.store.conftest import db_url  # noqa: F401 - 세션 fixture를 이 디렉터리에서도 쓴다


@pytest.fixture(autouse=True)
def clean_retrieval_tables(db_url: str) -> None:  # noqa: F811 - 위에서 가져온 fixture를 받는다
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(
            "TRUNCATE qk.sync_run, qk.sync_source, qk.chunk, qk.embedding, qk.artifact, qk.index_version,"
            " qk.embedding_usage, qk.embedding_usage_daily RESTART IDENTITY CASCADE"
        )
        seed_index_versions(conn)


@pytest.fixture
def store(db_url: str) -> Iterator[PostgresStore]:  # noqa: F811
    with PostgresStore(db_url) as instance:
        yield instance
