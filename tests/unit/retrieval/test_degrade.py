"""실패와 축소 동작(research R-14 표, spec FR-009~011, SC-008·SC-011, tasks T047)."""

from __future__ import annotations

import logging

import pytest

from qello_knowledge.domain.embedding import EmbedError, EmbedErrorKind, ProviderFailureKind
from qello_knowledge.domain.retrieval import OmitReason, RetrievalFailure, RetrievalMode, RetrievalRequest
from qello_knowledge.domain.store import StoreError, StoreUnavailable
from qello_knowledge.embedding.fake import FakeEmbeddingProvider
from qello_knowledge.ports.embedder import ProviderFailure
from qello_knowledge.retrieval import RetrievalDeps, retrieve
from tests.unit.retrieval.fakes import (
    FakeRetrievalStore,
    blocked,
    document_context,
    keyword_result,
    query_embedder,
    vector_result,
)

QUESTION = "결제 취소 API 경로가 뭐야?"
H, V, K = RetrievalMode.HYBRID, RetrievalMode.VECTOR, RetrievalMode.KEYWORD


class RaisingEmbedder:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def embed(self, request):
        raise self.error

    def preview(self, request):
        raise self.error


def _store(**kwargs) -> FakeRetrievalStore:
    return FakeRetrievalStore(
        vector=vector_result(1, 2), keyword=keyword_result((3, 2)), context=document_context({1: [1, 2, 3]}), **kwargs
    )


def _run(mode=H, store=None, embedder=None, question=QUESTION, provider=None, check=None):
    store = store or _store()
    if embedder is None:
        kwargs = {"check": check} if check else {}
        embedder, provider, ledger = query_embedder(provider, **kwargs)
    else:
        ledger = None
    result = retrieve(RetrievalRequest(question, mode=mode), RetrievalDeps(store=store, embedder=embedder))
    return result, store, ledger


def _omitted(result) -> list[tuple[str, OmitReason]]:
    return [(o.search, o.reason) for o in result.summary.omitted]


@pytest.mark.parametrize("question", ["", "   ", "가" * 2001])
def test_bad_question_makes_no_external_call(question: str) -> None:
    store = _store()
    provider = FakeEmbeddingProvider()
    result, _, ledger = _run(store=store, question=question, provider=provider)
    expected = RetrievalFailure.EMPTY_QUESTION if not question.strip() else RetrievalFailure.QUESTION_TOO_LONG
    assert result.failure is expected
    assert store.calls == [] and provider.calls == [] and ledger.rows == []
    assert result.summary.external_calls == 0


def test_hybrid_outgoing_blocked_falls_back_to_keyword() -> None:
    result, store, _ = _run(check=blocked)
    assert result.status == "ok" and [h.chunk_id for h in result.hits] == [3]
    assert _omitted(result) == [("vector", OmitReason.OUTGOING_BLOCKED)]
    assert "search_vector" not in store.names()


def test_vector_only_outgoing_blocked_fails() -> None:
    result, _, _ = _run(mode=V, check=blocked)
    assert result.failure is RetrievalFailure.OUTGOING_BLOCKED and result.hits == ()


@pytest.mark.parametrize(
    "kind", [ProviderFailureKind.TRANSIENT, ProviderFailureKind.PROVIDER_QUOTA, ProviderFailureKind.INPUT_TOO_LONG]
)
def test_hybrid_embedding_failure_falls_back(kind: ProviderFailureKind) -> None:
    provider = FakeEmbeddingProvider(fail_calls={1: ProviderFailure(kind), 2: ProviderFailure(kind)})
    result, _, _ = _run(provider=provider)
    assert result.status == "ok" and [h.chunk_id for h in result.hits] == [3]
    assert _omitted(result) == [("vector", OmitReason.QUERY_EMBEDDING_FAILED)]
    assert result.summary.omitted[0].detail is not None


def test_vector_only_embedding_failure_fails() -> None:
    provider = FakeEmbeddingProvider(fail_calls={1: ProviderFailure(ProviderFailureKind.PROVIDER_QUOTA)})
    result, _, _ = _run(mode=V, provider=provider)
    assert result.failure is RetrievalFailure.QUERY_EMBEDDING_FAILED


def test_embed_error_is_query_embedding_failure() -> None:
    error = EmbedError(EmbedErrorKind.AUTH_CONFIG)
    hybrid, _, _ = _run(embedder=RaisingEmbedder(error))
    assert _omitted(hybrid) == [("vector", OmitReason.QUERY_EMBEDDING_FAILED)] and hybrid.status == "ok"
    vector, _, _ = _run(mode=V, embedder=RaisingEmbedder(error))
    assert vector.failure is RetrievalFailure.QUERY_EMBEDDING_FAILED


def test_vector_search_error() -> None:
    hybrid, _, _ = _run(store=_store(fail={"search_vector": StoreError("x")}))
    assert _omitted(hybrid) == [("vector", OmitReason.VECTOR_SEARCH_FAILED)] and [h.chunk_id for h in hybrid.hits] == [
        3
    ]
    vector, _, _ = _run(mode=V, store=_store(fail={"search_vector": StoreError("x")}))
    assert vector.failure is RetrievalFailure.STORE_UNAVAILABLE


def test_keyword_search_error() -> None:
    hybrid, _, _ = _run(store=_store(fail={"search_keyword_terms": StoreError("x")}))
    assert _omitted(hybrid) == [("keyword", OmitReason.KEYWORD_SEARCH_FAILED)]
    assert [h.chunk_id for h in hybrid.hits] == [1, 2]
    keyword, _, _ = _run(mode=K, store=_store(fail={"search_keyword_terms": StoreError("x")}))
    assert keyword.failure is RetrievalFailure.KEYWORD_SEARCH_FAILED


@pytest.mark.parametrize("operation", ["search_vector", "search_keyword_terms", "chunk_context"])
@pytest.mark.parametrize("mode", [H, V, K])
def test_store_unavailable_never_degrades(operation: str, mode: RetrievalMode) -> None:
    store = _store(fail={operation: StoreUnavailable("down")})
    result, _, _ = _run(mode=mode, store=store)
    if operation in store.names():
        assert result.failure is RetrievalFailure.STORE_UNAVAILABLE and result.summary.omitted == ()


@pytest.mark.parametrize(
    ("setup", "expected"),
    [
        ({"check": blocked}, RetrievalFailure.OUTGOING_BLOCKED),
        ({"store_fail": {"search_vector": StoreError("x")}}, RetrievalFailure.STORE_UNAVAILABLE),
        (
            {"embedder": RaisingEmbedder(EmbedError(EmbedErrorKind.AUTH_CONFIG))},
            RetrievalFailure.QUERY_EMBEDDING_FAILED,
        ),
    ],
)
def test_vector_omitted_and_no_keyword_terms(setup: dict, expected: RetrievalFailure) -> None:
    store = _store(fail=setup.get("store_fail"))
    result, _, _ = _run(store=store, question="무엇 어디", check=setup.get("check"), embedder=setup.get("embedder"))
    assert result.failure is expected


def test_both_sides_omitted() -> None:
    store = _store(fail={"search_keyword_terms": StoreError("x")})
    result, _, _ = _run(store=store, check=blocked)
    assert result.failure is RetrievalFailure.BOTH_SEARCHES_FAILED


def test_context_store_error_fails() -> None:
    result, _, _ = _run(store=_store(fail={"chunk_context": StoreError("x")}))
    assert result.failure is RetrievalFailure.STORE_UNAVAILABLE


def test_no_question_text_in_summary_errors_logs_or_usage(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.DEBUG)
    cases = [
        _run(check=blocked),
        _run(store=_store(fail={"search_keyword_terms": StoreError("x")})),
        _run(mode=V, embedder=RaisingEmbedder(EmbedError(EmbedErrorKind.AUTH_CONFIG))),
        _run(),
    ]
    for result, _, ledger in cases:
        text = repr(result.summary) + repr(result.failure)
        assert "결제" not in text and "경로" not in text
        if ledger is not None:
            assert all("결제" not in repr(row) for row in ledger.rows)
    assert "결제" not in caplog.text
