"""한 결과는 한 인덱스 버전(spec FR-006, US2 시나리오 4, tasks T023)."""

from __future__ import annotations

from qello_knowledge.domain.retrieval import RetrievalFailure, RetrievalRequest
from qello_knowledge.retrieval import RetrievalDeps, retrieve
from tests.unit.retrieval.fakes import FakeRetrievalStore, keyword_result, query_embedder, vector_result


def _run(store: FakeRetrievalStore):
    embedder, provider, _ = query_embedder()
    return retrieve(RetrievalRequest("배포 승인 절차"), RetrievalDeps(store=store, embedder=embedder)), provider


def test_version_mismatch_fails_without_research() -> None:
    store = FakeRetrievalStore(vector=vector_result(1, version="v1"), keyword=keyword_result((2, 1), version="v2"))
    result, provider = _run(store)
    assert result.failure is RetrievalFailure.INDEX_VERSION_CHANGED
    assert result.hits == () and result.context == ()
    assert store.names() == ["search_vector", "search_keyword_terms"]  # 다시 검색하지 않는다
    assert len(provider.calls) == 1


def test_no_active_index_on_either_side() -> None:
    for store in (
        FakeRetrievalStore(vector=vector_result(version=None), keyword=keyword_result((2, 1))),
        FakeRetrievalStore(vector=vector_result(1), keyword=keyword_result(version=None)),
    ):
        result, _ = _run(store)
        assert result.failure is RetrievalFailure.NO_ACTIVE_INDEX
        assert result.hits == ()


def test_results_only_come_from_store_rows() -> None:
    store = FakeRetrievalStore(vector=vector_result(1, 2), keyword=keyword_result((3, 1)))
    result, _ = _run(store)
    assert {h.chunk_id for h in result.hits} == {1, 2, 3}
