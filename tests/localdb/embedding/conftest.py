"""임베딩 로컬 DB 시험 기반. 저장소 시험과 같은 방식으로 세션 전용 데이터베이스를 쓴다(QK-STO-001 research R-10)."""

from __future__ import annotations

from collections.abc import Iterator

import psycopg
import pytest

from qello_knowledge.adapters.postgres.store import PostgresStore
from tests.localdb.store.builders import seed_index_versions
from tests.localdb.store.conftest import db_url  # noqa: F401 - 세션 fixture를 이 디렉터리에서도 쓴다


@pytest.fixture(autouse=True)
def clean_tables(db_url: str) -> None:  # noqa: F811
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(
            "TRUNCATE qk.chunk, qk.embedding, qk.artifact, qk.index_version, qk.embedding_usage,"
            " qk.embedding_usage_daily RESTART IDENTITY CASCADE"
        )
        seed_index_versions(conn)


@pytest.fixture
def store(db_url: str) -> Iterator[PostgresStore]:  # noqa: F811
    with PostgresStore(db_url) as instance:
        yield instance


@pytest.fixture
def make_ledger(db_url: str):  # noqa: F811
    from qello_knowledge.adapters.postgres.usage import PostgresUsageLedger
    from qello_knowledge.domain.embedding import BudgetSettings

    opened: list[PostgresUsageLedger] = []

    def build(settings: BudgetSettings | None = None) -> PostgresUsageLedger:
        ledger = PostgresUsageLedger(db_url, settings or BudgetSettings())
        opened.append(ledger)
        return ledger

    yield build
    for ledger in opened:
        ledger.close()
