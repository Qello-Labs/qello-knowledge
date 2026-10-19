"""사용량 조회(FR-023)."""

from __future__ import annotations

import pytest

from qello_knowledge.adapters.postgres.store import PostgresStore
from tests.localdb.store.builders import document, vec

pytestmark = pytest.mark.localdb


def test_usage_counts_chunks_and_vectors(store: PostgresStore) -> None:
    empty = store.usage()
    assert (empty.chunk_count, empty.embedding_count) == (0, 0)
    document(store, "a.md", ["하나", "둘", "셋"], vector=vec(1))
    usage = store.usage()
    assert (usage.chunk_count, usage.embedding_count) == (3, 3)
    assert usage.total_bytes > 0
