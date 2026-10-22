"""검색 방식별 결과(spec US6 시나리오 1~4, FR-022~024, tasks T046)."""

from __future__ import annotations

from qello_knowledge.domain.retrieval import RetrievalMode, RetrievalRequest, RetrievalSettings
from qello_knowledge.retrieval import RetrievalDeps, fuse, retrieve
from tests.unit.retrieval.fakes import (
    FakeRetrievalStore,
    document_context,
    keyword_result,
    query_embedder,
    vector_result,
)

QUESTION = "결제 취소 API 경로가 뭐야?"


def _run(mode: RetrievalMode, **request):
    store = FakeRetrievalStore(
        vector=vector_result(1, 2, 3),
        keyword=keyword_result((3, 4), (4, 1)),
        context=document_context({1: [1, 2, 3, 4]}),
    )
    embedder, provider, ledger = query_embedder()
    result = retrieve(RetrievalRequest(QUESTION, mode=mode, **request), RetrievalDeps(store=store, embedder=embedder))
    return result, store, provider, ledger


def test_vector_only() -> None:
    result, store, provider, _ = _run(RetrievalMode.VECTOR)
    assert "search_keyword_terms" not in store.names() and len(provider.calls) == 1
    assert [h.chunk_id for h in result.hits] == [h.chunk_id for h in fuse(vector_result(1, 2, 3), None, 60)]
    assert all(h.keyword_rank is None for h in result.hits)


def test_keyword_only_makes_no_embedding_call() -> None:
    result, store, provider, ledger = _run(RetrievalMode.KEYWORD)
    assert "search_vector" not in store.names() and provider.calls == [] and ledger.rows == []
    assert [h.chunk_id for h in result.hits] == [3, 4]
    assert result.summary.embedding is None


def test_hybrid_matches_us1() -> None:
    result, store, _, _ = _run(RetrievalMode.HYBRID)
    assert store.names() == ["search_vector", "search_keyword_terms", "chunk_context"]
    assert [h.chunk_id for h in result.hits] == [3, 1, 2, 4]


def test_summary_records_conditions() -> None:
    result, _, _, _ = _run(RetrievalMode.HYBRID, overrides={"candidates": 9, "rrf_k": 30, "context_budget": 500})
    s = result.summary
    assert (s.mode, s.candidates, s.rrf_k, s.query_rule, s.budget) == (RetrievalMode.HYBRID, 9, 30, "kw-query-v1", 500)
    assert (s.index_version, s.index_rule) == ("v1", "unknown")
    assert (s.vector_count, s.keyword_count, s.keyword_terms) == (3, 2, 4)
    assert s.embedding is not None and s.embedding.provider_calls == 1
    assert s.block_count == 1 and s.used_tokens > 0


def test_query_rule_override() -> None:
    result, store, _, _ = _run(RetrievalMode.KEYWORD, overrides={"query_rule": "kw-query-raw"})
    assert store.calls[0][1][0] == (QUESTION,) and result.summary.query_rule == "kw-query-raw"


def test_ranks_only_skips_context() -> None:
    result, store, _, _ = _run(RetrievalMode.HYBRID, want_context=False)
    assert "chunk_context" not in store.names() and result.context == () and result.summary.block_count == 0


def test_default_settings_object_is_used_when_none() -> None:
    store = FakeRetrievalStore(vector=vector_result(1))
    embedder, _, _ = query_embedder()
    result = retrieve(RetrievalRequest(QUESTION, want_context=False), RetrievalDeps(store=store, embedder=embedder))
    assert result.summary.candidates == RetrievalSettings().candidates
