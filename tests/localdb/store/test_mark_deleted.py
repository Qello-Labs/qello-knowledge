"""삭제 상태 전환(FR-014)."""

from __future__ import annotations

import pytest

from qello_knowledge.adapters.postgres.store import PostgresStore
from tests.localdb.store.builders import artifact, document, vec

pytestmark = pytest.mark.localdb


def test_deleted_document_disappears_from_both_searches(store: PostgresStore) -> None:
    document(store, "gone.md", ["삭제대상 문서"], vector=vec(5))
    document(store, "kept.md", ["삭제대상 아님"], vector=vec(6))
    store.mark_deleted("github", "gone.md")
    assert [h.body for h in store.search_keyword("삭제대상", 20).hits] == ["삭제대상 아님"]
    assert [h.body for h in store.search_vector(vec(5), 20).hits] == ["삭제대상 아님"]
    store.mark_deleted("github", "gone.md")  # 다시 불러도 오류가 없다
    store.mark_deleted("github", "never-existed.md")


def test_upsert_brings_document_back(store: PostgresStore) -> None:
    document(store, "back.md", ["되살림 문서"])
    store.mark_deleted("github", "back.md")
    artifact(store, "back.md")
    assert [h.body for h in store.search_keyword("되살림", 20).hits] == ["되살림 문서"]
