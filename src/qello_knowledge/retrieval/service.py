"""검색 경계 `retrieve`(QK-RET-001 contracts/retrieval.md 3절).

저장소 호출은 이 모듈에서만 한다. 노출 조건은 저장소 함수가 판정하고, 여기서는 그 결과만 다룬다(spec FR-007).
질문 원문과 검색어 낱말은 지역 변수로만 지나고 요약·예외·로그에 남기지 않는다(spec FR-008).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field

from qello_knowledge.domain.embedding import EmbedInput, EmbedPurpose, EmbedRequest, RunSummary
from qello_knowledge.domain.keyword_rules import index_rule_for
from qello_knowledge.domain.retrieval import (
    DEFAULT_QUERY_MODEL,
    ChunkRole,
    OmitReason,
    Omitted,
    RetrievalFailure,
    RetrievalMode,
    RetrievalRequest,
    RetrievalResult,
    RetrievalSettings,
    RetrievalSummary,
    Skipped,
    SkipReason,
)
from qello_knowledge.domain.store import SearchResult, StoreError
from qello_knowledge.ports.embedder import Embedder
from qello_knowledge.ports.retrieval import KeywordSearchResult, RetrievalStore
from qello_knowledge.retrieval.fusion import fuse
from qello_knowledge.retrieval.keyword import keyword_query
from qello_knowledge.retrieval.pack import pack


def _new_run_id() -> str:
    return "query-" + uuid.uuid4().hex


@dataclass(frozen=True)
class RetrievalDeps:
    store: RetrievalStore
    embedder: Embedder
    new_run_id: Callable[[], str] = field(default=_new_run_id)
    model_version: str = DEFAULT_QUERY_MODEL  # 활성 인덱스 버전의 임베딩 모델. 조립하는 쪽이 넘긴다


class _DuplicateHit(StoreError):
    """한 검색 결과에 같은 청크가 두 번 나왔다(research R-02). 그 검색의 오류로 본다."""


def _check_unique(chunk_ids: list[int]) -> None:
    if len(set(chunk_ids)) != len(chunk_ids):
        raise _DuplicateHit("검색 결과에 같은 청크가 두 번 있다")


@dataclass
class _Run:
    """한 질의의 진행 상태. 질문 원문은 담지 않는다."""

    settings: RetrievalSettings
    request: RetrievalRequest
    calls: int = 0
    omitted: list[Omitted] = field(default_factory=list)
    embedding: RunSummary | None = None
    vector: SearchResult | None = None
    keyword: KeywordSearchResult | None = None
    terms: int = 0

    def index_version(self) -> str | None:
        return next((r.index_version for r in (self.vector, self.keyword) if r is not None and r.index_version), None)

    def summary(self, **extra: object) -> RetrievalSummary:
        index_version = self.index_version()
        values: dict[str, object] = {
            "mode": self.request.mode,
            "candidates": self.settings.candidates,
            "rrf_k": self.settings.rrf_k,
            "query_rule": self.settings.query_rule,
            "index_version": index_version,
            "index_rule": index_rule_for(index_version),
            "omitted": tuple(self.omitted),
            "vector_count": len(self.vector.hits) if self.vector is not None else 0,
            "keyword_count": len(self.keyword.hits) if self.keyword is not None else 0,
            "keyword_terms": self.terms,
            "budget": self.settings.context_budget,
            "embedding": self.embedding,
            "external_calls": self.calls,
        }
        values.update(extra)
        return RetrievalSummary(**values)  # type: ignore[arg-type]

    def result(self, status: str, **extra: object) -> RetrievalResult:
        return RetrievalResult(status=status, summary=self.summary(), **extra)  # type: ignore[arg-type]


def retrieve(
    request: RetrievalRequest, deps: RetrievalDeps, settings: RetrievalSettings | None = None
) -> RetrievalResult:
    settings = settings or RetrievalSettings()
    if request.overrides:
        settings = settings.with_overrides(request.overrides)
    run = _Run(settings=settings, request=request)
    question = request.question.strip()
    if not question:
        return run.result(RetrievalFailure.EMPTY_QUESTION.value)
    if len(question) > settings.question_max_chars:
        return run.result(RetrievalFailure.QUESTION_TOO_LONG.value)

    mode = request.mode
    query_vector = None
    if mode in (RetrievalMode.HYBRID, RetrievalMode.VECTOR):
        embedded = deps.embedder.embed(
            EmbedRequest(
                inputs=(EmbedInput(question),),
                purpose=EmbedPurpose.QUERY,
                model_version=deps.model_version,
                run_id=deps.new_run_id(),
            )
        )
        run.embedding = embedded.summary
        run.calls += 2 * embedded.summary.provider_calls  # 제공자 호출마다 사용량 기록 1(research R-07)
        query_vector = embedded.items[0].vector

    uses_keyword = mode in (RetrievalMode.HYBRID, RetrievalMode.KEYWORD)
    terms = keyword_query(question, settings.query_rule) if uses_keyword else ()
    run.terms = len(terms)

    if query_vector is not None:
        run.calls += 1
        try:
            run.vector = deps.store.search_vector(query_vector, settings.candidates, request.filters)
            _check_unique([h.chunk_id for h in run.vector.hits])
        except StoreError:
            run.vector = None
            run.omitted.append(Omitted("vector", OmitReason.VECTOR_SEARCH_FAILED))
    if uses_keyword:
        run.calls += 1
        try:
            run.keyword = deps.store.search_keyword_terms(terms, settings.candidates, request.filters)
            _check_unique([h.hit.chunk_id for h in run.keyword.hits])
        except StoreError:
            run.keyword = None
            run.omitted.append(Omitted("keyword", OmitReason.KEYWORD_SEARCH_FAILED))

    results = [r for r in (run.vector, run.keyword) if r is not None]
    if any(r.status == "no_active_index" for r in results):
        return run.result(RetrievalFailure.NO_ACTIVE_INDEX.value)
    if len({r.index_version for r in results}) > 1:
        return run.result(RetrievalFailure.INDEX_VERSION_CHANGED.value)  # 다시 검색하지 않는다(spec FR-006)

    hits = fuse(run.vector, run.keyword, settings.rrf_k)
    if not hits:
        return run.result("no_results")
    if not request.want_context:
        return run.result("ok", hits=hits)

    centers = [h.chunk_id for h in hits[: settings.expand_top]]
    run.calls += 1
    try:
        context = deps.store.chunk_context(centers, settings.before, settings.after)
    except StoreError:
        return run.result(RetrievalFailure.STORE_UNAVAILABLE.value, hits=hits)
    if context.index_version != run.index_version():
        return run.result(RetrievalFailure.INDEX_VERSION_CHANGED.value)
    returned = {item.center.chunk_id for item in context.items}
    gone = tuple(Skipped(cid, ChunkRole.CENTER, SkipReason.NOT_VISIBLE) for cid in centers if cid not in returned)
    blocks, skipped, used = pack(hits, context, settings)
    return RetrievalResult(
        status="ok",
        hits=hits,
        context=blocks,
        summary=run.summary(block_count=len(blocks), used_tokens=used, skipped=gone + skipped),
    )
