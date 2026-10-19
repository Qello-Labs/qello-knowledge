"""활성 인덱스가 없을 때와 상위 N 상한(Edge Cases, FR-010)."""

from __future__ import annotations

import psycopg
import pytest

from qello_knowledge.adapters.postgres.store import PostgresStore
from tests.localdb.store.builders import document, vec

pytestmark = pytest.mark.localdb


def test_no_active_index_is_reported_without_error(store: PostgresStore, db_url: str) -> None:
    document(store, "a.md", ["배포 문서"], vector=vec(1))
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute("UPDATE qk.index_version SET status = 'archived' WHERE status = 'active'")
    for result in (store.search_vector(vec(1), 20), store.search_keyword("배포", 20)):
        assert result.status == "no_active_index"
        assert result.index_version is None
        assert result.hits == ()


def test_top_n_is_capped_at_50(store: PostgresStore) -> None:
    document(store, "many.md", [f"배포 항목 {i}" for i in range(60)], vector=vec(3))
    assert len(store.search_vector(vec(3), 500).hits) == 50
    assert len(store.search_keyword("배포", 500).hits) == 50
    assert len(store.search_keyword("배포", 0).hits) == 1
