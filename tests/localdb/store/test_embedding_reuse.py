"""US5: 같은 임베딩 입력의 벡터를 다시 쓴다(FR-003)."""

from __future__ import annotations

import psycopg
import pytest

from qello_knowledge.adapters.postgres.store import PostgresStore
from qello_knowledge.domain.store import EmbeddingRef
from tests.localdb.store.builders import MODEL, vec

pytestmark = pytest.mark.localdb


def test_same_hash_and_model_returns_stored_vector(store: PostgresStore) -> None:
    vector = vec(11)
    store.put_embedding(EmbeddingRef("H", MODEL), vector)
    found = store.find_embedding(EmbeddingRef("H", MODEL))
    assert found is not None
    assert len(found) == 1024
    assert max(abs(a - b) for a, b in zip(found, vector, strict=True)) < 1e-6


def test_other_model_version_returns_none(store: PostgresStore) -> None:
    store.put_embedding(EmbeddingRef("H", MODEL), vec(11))
    assert store.find_embedding(EmbeddingRef("H", "@cf/other/model")) is None
    assert store.find_embedding(EmbeddingRef("other-hash", MODEL)) is None


def test_putting_same_key_twice_keeps_one_row(store: PostgresStore, db_url: str) -> None:
    store.put_embedding(EmbeddingRef("H", MODEL), vec(11))
    store.put_embedding(EmbeddingRef("H", MODEL), vec(12))
    with psycopg.connect(db_url) as conn:
        assert conn.execute("SELECT count(*) FROM qk.embedding").fetchone() == (1,)
