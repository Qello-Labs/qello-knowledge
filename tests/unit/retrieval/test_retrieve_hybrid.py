"""하이브리드 검색 1~7단계(contracts/retrieval.md 3절, spec US1, tasks T017)."""

from __future__ import annotations

import logging

import pytest

from qello_knowledge.domain.embedding import EmbedPurpose
from qello_knowledge.domain.retrieval import OmitReason, RetrievalMode, RetrievalRequest, RetrievalSettings
from qello_knowledge.domain.store import SearchFilter, SearchResult
from qello_knowledge.ports.retrieval import KeywordHit, KeywordSearchResult
from qello_knowledge.retrieval import RetrievalDeps, retrieve
from tests.unit.retrieval.fakes import FakeRetrievalStore, hit, keyword_result, query_embedder, vector_result

QUESTION = "결제 취소 API 경로가 뭐야?"


class RecordingEmbedder:
    def __init__(self) -> None:
        self.inner, self.provider, self.ledger = query_embedder()
        self.requests = []

    def embed(self, request):
        self.requests.append(request)
        return self.inner.embed(request)

    def preview(self, request):
        return self.inner.preview(request)


def _deps(store: FakeRetrievalStore, embedder=None) -> RetrievalDeps:
    run_ids = iter(f"run-{i}" for i in range(100))
    return RetrievalDeps(store=store, embedder=embedder or RecordingEmbedder(), new_run_id=lambda: next(run_ids))


def _store() -> FakeRetrievalStore:
    return FakeRetrievalStore(vector=vector_result(1, 2, 3), keyword=keyword_result((3, 4), (4, 2)))


def test_hybrid_calls_both_searches_and_fuses() -> None:
    store = _store()
    embedder = RecordingEmbedder()
    result = retrieve(RetrievalRequest(QUESTION, want_context=False), _deps(store, embedder))
    assert result.status == "ok"
    assert [h.chunk_id for h in result.hits][0] == 3
    names = store.names()
    assert names == ["search_vector", "search_keyword_terms"]
    assert store.calls[0][1][:2] == (1024, 20)
    assert store.calls[1][1][:2] == (("결제", "취소", "API", "경로"), 20)
    request = embedder.requests[0]
    assert request.purpose is EmbedPurpose.QUERY and len(request.inputs) == 1
    assert request.model_version == "@cf/baai/bge-m3" and request.run_id == "run-0"


def test_new_run_id_per_query() -> None:
    store, embedder = _store(), RecordingEmbedder()
    deps = _deps(store, embedder)
    retrieve(RetrievalRequest(QUESTION, want_context=False), deps)
    retrieve(RetrievalRequest(QUESTION, want_context=False), deps)
    assert [r.run_id for r in embedder.requests] == ["run-0", "run-1"]


def test_filters_and_candidates_are_passed_to_both() -> None:
    store = _store()
    filters = SearchFilter(source_kinds=("github_repo_files",))
    request = RetrievalRequest(QUESTION, filters=filters, want_context=False, overrides={"candidates": 7})
    retrieve(request, _deps(store))
    assert store.calls[0][1][1:] == (7, filters) and store.calls[1][1][1:] == (7, filters)


def test_hit_fields() -> None:
    result = retrieve(RetrievalRequest(QUESTION, want_context=False), _deps(_store()))
    top = result.hits[0]
    assert (top.vector_rank, top.keyword_rank, top.keyword_matched) == (3, 1, 4)
    assert top.provenance.source_url.endswith("doc-3")
    assert [h.rank for h in result.hits] == [1, 2, 3, 4]


def test_summary_basic_fields() -> None:
    result = retrieve(RetrievalRequest(QUESTION, want_context=False), _deps(_store()), RetrievalSettings())
    s = result.summary
    assert (s.mode, s.candidates, s.rrf_k, s.query_rule) == (RetrievalMode.HYBRID, 20, 60, "kw-query-v1")
    assert (s.index_version, s.index_rule) == ("v1", "unknown")
    assert (s.vector_count, s.keyword_count, s.keyword_terms) == (3, 2, 4)
    assert s.embedding is not None and s.embedding.provider_calls == 1


def test_repeatable() -> None:
    a = retrieve(RetrievalRequest(QUESTION, want_context=False), _deps(_store()))
    b = retrieve(RetrievalRequest(QUESTION, want_context=False), _deps(_store()))
    assert a.hits == b.hits


def test_no_results() -> None:
    store = FakeRetrievalStore(vector=SearchResult(status="ok", index_version="v1"))
    result = retrieve(RetrievalRequest(QUESTION, want_context=False), _deps(store))
    assert (result.status, result.hits, result.context) == ("no_results", (), ())


def test_duplicate_chunk_in_one_search_omits_that_search() -> None:
    duplicated = KeywordSearchResult(
        status="ok", index_version="v1", hits=(KeywordHit(hit(5, 1), 1), KeywordHit(hit(5, 2), 1))
    )
    store = FakeRetrievalStore(vector=vector_result(1), keyword=duplicated)
    result = retrieve(RetrievalRequest(QUESTION, want_context=False), _deps(store))
    assert [h.chunk_id for h in result.hits] == [1]
    assert [(o.search, o.reason) for o in result.summary.omitted] == [("keyword", OmitReason.KEYWORD_SEARCH_FAILED)]


def test_question_never_reaches_logs_or_summary(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    result = retrieve(RetrievalRequest(QUESTION, want_context=False), _deps(_store()))
    assert QUESTION not in caplog.text and "결제" not in caplog.text
    assert "결제" not in repr(result.summary)
