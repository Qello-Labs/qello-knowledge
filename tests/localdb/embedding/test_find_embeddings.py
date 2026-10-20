"""US2 저장소 쪽: 여러 키를 한 번에 조회한다(research R-07)."""

from __future__ import annotations

import pytest

from qello_knowledge.adapters.postgres.store import PostgresStore
from qello_knowledge.domain.store import EmbeddingRef
from tests.localdb.store.builders import MODEL, vec

pytestmark = pytest.mark.localdb


def test_returns_only_existing_keys(store: PostgresStore) -> None:
    store.put_embedding(EmbeddingRef("A", MODEL), vec(1))
    store.put_embedding(EmbeddingRef("B", MODEL), vec(2))
    found = store.find_embeddings([EmbeddingRef("A", MODEL), EmbeddingRef("B", MODEL), EmbeddingRef("C", MODEL)])
    assert set(found) == {EmbeddingRef("A", MODEL), EmbeddingRef("B", MODEL)}
    assert all(len(v) == 1024 for v in found.values())


def test_same_hash_other_model_is_missing(store: PostgresStore) -> None:
    store.put_embedding(EmbeddingRef("A", MODEL), vec(1))
    assert store.find_embeddings([EmbeddingRef("A", "@cf/other/model")]) == {}


def test_empty_list_does_not_touch_db(monkeypatch) -> None:
    store = PostgresStore("postgresql://unused@127.0.0.1:1/none")
    monkeypatch.setattr(store, "_db", lambda: pytest.fail("빈 목록은 DB를 부르지 않는다"))
    assert store.find_embeddings([]) == {}
