"""문맥 확장 단계(contracts/retrieval.md 3절 8~10, spec FR-012, tasks T026)."""

from __future__ import annotations

from qello_knowledge.domain.retrieval import RetrievalFailure, RetrievalRequest, SkipReason
from qello_knowledge.domain.store import StoreError
from qello_knowledge.ports.retrieval import ContextResult
from qello_knowledge.retrieval import RetrievalDeps, retrieve
from tests.unit.retrieval.fakes import FakeRetrievalStore, document_context, query_embedder, vector_result

QUESTION = "배포 승인 절차"


def _run(store: FakeRetrievalStore, **request):
    embedder, _, _ = query_embedder()
    return retrieve(RetrievalRequest(QUESTION, **request), RetrievalDeps(store=store, embedder=embedder))


def _store(**kwargs) -> FakeRetrievalStore:
    layout = kwargs.pop("layout", {1: list(range(1, 30))})
    return FakeRetrievalStore(vector=vector_result(*range(1, 13)), context=document_context(layout), **kwargs)


def test_chunk_context_called_once_with_top_expand() -> None:
    store = _store()
    result = _run(store, overrides={"expand_top": 5, "before": 2, "after": 0})
    calls = [args for name, args in store.calls if name == "chunk_context"]
    assert calls == [((1, 2, 3, 4, 5), 2, 0)]
    assert result.status == "ok" and result.context


def test_missing_centers_are_skipped_as_not_visible() -> None:
    store = _store(layout={1: [1, 2, 3]})  # 4~8은 다시 확인에서 빠진 중심
    result = _run(store, overrides={"expand_top": 8})
    in_context = {c.chunk_id for b in result.context for c in b.chunks}
    assert in_context == {1, 2, 3}
    gone = {s.chunk_id for s in result.summary.skipped if s.reason is SkipReason.NOT_VISIBLE}
    assert gone == {4, 5, 6, 7, 8}
    assert {h.chunk_id for h in result.hits} >= gone  # 순위에는 남는다


def test_context_version_mismatch_fails() -> None:
    store = _store()
    store.context = ContextResult(index_version="v2")
    result = _run(store)
    assert result.failure is RetrievalFailure.INDEX_VERSION_CHANGED and result.context == ()


def test_ranks_only_skips_context() -> None:
    store = _store()
    result = _run(store, want_context=False)
    assert "chunk_context" not in store.names() and result.context == () and result.hits


def test_context_store_error_is_store_unavailable() -> None:
    store = _store(fail={"chunk_context": StoreError("x")})
    result = _run(store)
    assert result.failure is RetrievalFailure.STORE_UNAVAILABLE
