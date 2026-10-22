"""노출 차단(spec US2 수용 시나리오 1~4, SC-002, tasks T022·T030). 임베딩은 가짜 제공자다."""

from __future__ import annotations

import pytest

from qello_knowledge.adapters.postgres.store import PostgresStore
from qello_knowledge.domain.retrieval import RetrievalRequest
from qello_knowledge.embedding.fake import fake_vector
from qello_knowledge.retrieval import RetrievalDeps, retrieve
from tests.localdb.retrieval.builders import seed_doc, set_status
from tests.localdb.store.builders import ARCHIVED
from tests.unit.retrieval.fakes import query_embedder

pytestmark = pytest.mark.localdb

QUESTION = "배포 승인 절차"


def _deps(store: PostgresStore) -> RetrievalDeps:
    embedder, _, _ = query_embedder()
    return RetrievalDeps(store=store, embedder=embedder, new_run_id=lambda: "run")


def _all_chunk_ids(result) -> set[int]:
    ids = {h.chunk_id for h in result.hits}
    ids |= {c.chunk_id for block in result.context for c in block.chunks}
    return ids


@pytest.fixture
def query() -> list[float]:
    return list(fake_vector(QUESTION, 1024))


def test_hidden_chunks_never_appear_in_results(store: PostgresStore, db_url: str, query: list[float]) -> None:
    _, visible = seed_doc(store, "visible.md", ["배포 승인 절차 공개 문서"], vector=query)
    hidden: list[int] = []
    hidden += seed_doc(store, "unknown.md", ["배포 승인 절차 미확인"], vector=query, access_scope=None)[1]
    hidden += seed_doc(store, "limited.md", ["배포 승인 절차 제한"], vector=query, access_scope="restricted")[1]
    hidden += seed_doc(store, "deleted.md", ["배포 승인 절차 내림"], vector=query)[1]
    store.mark_deleted("github", "deleted.md")
    hidden += seed_doc(store, "archived.md", ["배포 승인 절차 보관"], vector=query)[1]
    set_status(db_url, "archived.md", "archived")
    hidden += seed_doc(store, "old.md", ["배포 승인 절차 옛 버전"], vector=query, index_version=ARCHIVED)[1]
    result = retrieve(RetrievalRequest(QUESTION), _deps(store))
    seen = _all_chunk_ids(result)
    assert visible[0] in seen
    assert seen.isdisjoint(hidden)


def test_nearest_unknown_scope_chunk_is_absent(store: PostgresStore, query: list[float]) -> None:
    _, [unknown] = seed_doc(store, "unknown.md", ["배포 승인 절차"], vector=query, access_scope=None)
    _, [far] = seed_doc(store, "far.md", ["다른 이야기"], vector=list(fake_vector("무관", 1024)))
    result = retrieve(RetrievalRequest(QUESTION), _deps(store))
    assert unknown not in _all_chunk_ids(result)
    assert far in {h.chunk_id for h in result.hits}


def test_inactive_version_neighbors_are_not_attached(store: PostgresStore, query: list[float]) -> None:
    _, current = seed_doc(store, "a.md", ["앞", "배포 승인 절차 본문", "뒤"], vector=query)
    _, old = seed_doc(store, "a.md", ["옛0", "옛1", "옛2", "옛3"], vector=query, index_version=ARCHIVED)
    result = retrieve(RetrievalRequest(QUESTION), _deps(store))
    in_context = {c.chunk_id for b in result.context for c in b.chunks}
    assert current[1] in in_context and in_context.isdisjoint(old)


class TakedownBeforeExpansion:
    """검색과 문맥 확장 사이에 문서가 내려지는 상황(spec US2 시나리오 3)."""

    def __init__(self, store: PostgresStore, source_id: str) -> None:
        self.store, self.source_id = store, source_id

    def search_vector(self, *args):
        return self.store.search_vector(*args)

    def search_keyword_terms(self, *args):
        return self.store.search_keyword_terms(*args)

    def chunk_context(self, *args):
        self.store.mark_deleted("github", self.source_id)
        return self.store.chunk_context(*args)


def test_document_taken_down_after_search_is_not_in_context(store: PostgresStore, query: list[float]) -> None:
    _, [gone] = seed_doc(store, "gone.md", ["배포 승인 절차 곧 내림"], vector=query)
    _, [kept] = seed_doc(store, "kept.md", ["배포 승인 절차 유지"], vector=query)
    embedder, _, _ = query_embedder()
    deps = RetrievalDeps(store=TakedownBeforeExpansion(store, "gone.md"), embedder=embedder)
    result = retrieve(RetrievalRequest(QUESTION), deps)
    assert gone in {h.chunk_id for h in result.hits}  # 검색 시점에는 노출 조건을 통과했다
    in_context = {c.chunk_id for b in result.context for c in b.chunks}
    assert gone not in in_context and kept in in_context
    assert any(s.chunk_id == gone and s.reason.value == "not_visible" for s in result.summary.skipped)
