"""질의당 외부 호출 수(spec FR-026, SC-007, SC-009 일부, research R-07, tasks T048)."""

from __future__ import annotations

import pytest

from qello_knowledge.domain.embedding import EmbedError, EmbedErrorKind, ProviderFailureKind
from qello_knowledge.domain.retrieval import RetrievalFailure, RetrievalMode, RetrievalRequest
from qello_knowledge.embedding.fake import FakeEmbeddingProvider
from qello_knowledge.ports.embedder import ProviderFailure
from qello_knowledge.retrieval import RetrievalDeps, retrieve
from tests.unit.retrieval.fakes import (
    FakeRetrievalStore,
    document_context,
    keyword_result,
    query_embedder,
    vector_result,
)

QUESTION = "결제 취소 API 경로가 뭐야?"
CAP = 7


def _store() -> FakeRetrievalStore:
    return FakeRetrievalStore(
        vector=vector_result(*range(1, 21)),
        keyword=keyword_result(*((i, 1) for i in range(21, 41))),
        context=document_context({1: list(range(1, 41))}),
    )


def _actual(store: FakeRetrievalStore, provider: FakeEmbeddingProvider, ledger) -> int:
    return len(store.calls) + len(provider.calls) + len(ledger.rows)


@pytest.mark.parametrize("expand_top", [1, 8, 20])
def test_calls_do_not_grow_with_expansion(expand_top: int) -> None:
    store = _store()
    embedder, provider, ledger = query_embedder()
    request = RetrievalRequest(QUESTION, overrides={"expand_top": expand_top})
    result = retrieve(request, RetrievalDeps(store=store, embedder=embedder))
    assert result.status == "ok"
    assert result.summary.external_calls == _actual(store, provider, ledger) == 5
    assert [n for n, _ in store.calls].count("chunk_context") == 1


def test_retry_path_stays_within_cap() -> None:
    store = _store()
    provider = FakeEmbeddingProvider(fail_calls={1: ProviderFailure(ProviderFailureKind.TRANSIENT)})
    embedder, provider, ledger = query_embedder(provider)
    result = retrieve(RetrievalRequest(QUESTION), RetrievalDeps(store=store, embedder=embedder))
    assert result.status == "ok" and len(provider.calls) == 2 and len(ledger.rows) == 2  # 시도마다 사용량 기록
    assert result.summary.external_calls == _actual(store, provider, ledger) == CAP


def test_retry_is_at_most_once() -> None:
    transient = ProviderFailure(ProviderFailureKind.TRANSIENT)
    provider = FakeEmbeddingProvider(fail_calls={1: transient, 2: transient, 3: transient})
    embedder, provider, _ = query_embedder(provider)
    retrieve(RetrievalRequest(QUESTION), RetrievalDeps(store=_store(), embedder=embedder))
    assert len(provider.calls) == 2


def test_keyword_only_makes_no_embedding_calls() -> None:
    store = _store()
    embedder, provider, ledger = query_embedder()
    result = retrieve(
        RetrievalRequest(QUESTION, mode=RetrievalMode.KEYWORD), RetrievalDeps(store=store, embedder=embedder)
    )
    assert provider.calls == [] and ledger.rows == [] and result.summary.external_calls == 2


def test_version_change_does_not_search_again() -> None:
    store = _store()
    store.keyword = keyword_result((21, 1), version="v2")
    embedder, provider, ledger = query_embedder()
    result = retrieve(RetrievalRequest(QUESTION), RetrievalDeps(store=store, embedder=embedder))
    assert result.failure is RetrievalFailure.INDEX_VERSION_CHANGED
    assert store.names() == ["search_vector", "search_keyword_terms"]
    assert result.summary.external_calls == _actual(store, provider, ledger) == 4


class AuthFailingEmbedder:
    """제공자 호출·기록 뒤 `EmbedError`가 올라오는 경로. `RunSummary`를 받지 못한다."""

    def embed(self, request):
        raise EmbedError(EmbedErrorKind.AUTH_CONFIG)

    def preview(self, request):
        raise EmbedError(EmbedErrorKind.AUTH_CONFIG)


def test_embed_error_counts_embedding_share_at_maximum() -> None:
    store = _store()
    result = retrieve(RetrievalRequest(QUESTION), RetrievalDeps(store=store, embedder=AuthFailingEmbedder()))
    assert result.status == "ok"
    assert result.summary.external_calls == 4 + len(store.calls) <= CAP
