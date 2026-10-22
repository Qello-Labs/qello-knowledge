"""검색 단위 시험용 가짜(QK-RET-001 tasks T013). 외부 호출이 없다."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import UTC, datetime

from qello_knowledge.domain.embedding import BudgetSettings, SendBlock
from qello_knowledge.domain.source_config import RetryPolicy
from qello_knowledge.domain.store import NO_FILTER, Provenance, SearchFilter, SearchHit, SearchResult
from qello_knowledge.embedding.fake import FakeEmbeddingProvider
from qello_knowledge.embedding.service import EmbeddingService
from qello_knowledge.ports.retrieval import (
    ContextItem,
    ContextNeighbor,
    ContextResult,
    KeywordHit,
    KeywordSearchResult,
)
from tests.unit.fakes import InMemoryUsageLedger, MemoryEmbeddingStore

COLLECTED = datetime(2026, 10, 22, 9, 0, tzinfo=UTC)
VERSION = "v1"


def provenance(chunk_id: int, artifact_id: int | None = None, heading: tuple[str, ...] = ()) -> Provenance:
    doc = artifact_id if artifact_id is not None else chunk_id
    return Provenance(
        source_url=f"https://example.invalid/doc-{doc}",
        source_version=f"sha-{doc}",
        locator={"path": f"docs/doc-{doc}.md", "lines": [chunk_id, chunk_id]},
        heading_path=heading,
        collected_at=COLLECTED,
    )


def hit(chunk_id: int, rank: int, score: float = 1.0, body: str | None = None) -> SearchHit:
    return SearchHit(chunk_id, rank, score, body if body is not None else f"본문 {chunk_id}", provenance(chunk_id))


def vector_result(*chunk_ids: int, version: str | None = VERSION) -> SearchResult:
    if version is None:
        return SearchResult(status="no_active_index")
    hits = tuple(hit(c, i + 1, score=1.0 - i / 100) for i, c in enumerate(chunk_ids))
    return SearchResult(status="ok", index_version=version, hits=hits)


def keyword_result(*pairs: tuple[int, int], version: str | None = VERSION) -> KeywordSearchResult:
    """`pairs`는 (청크 식별자, 맞은 낱말 수)를 순위 순으로."""
    if version is None:
        return KeywordSearchResult(status="no_active_index")
    hits = tuple(KeywordHit(hit(c, i + 1, score=float(n)), n) for i, (c, n) in enumerate(pairs))
    return KeywordSearchResult(status="ok", index_version=version, hits=hits)


def neighbor(
    chunk_id: int, artifact_id: int, ordinal: int, body: str | None = None, heading: tuple[str, ...] = ()
) -> ContextNeighbor:
    return ContextNeighbor(
        chunk_id=chunk_id,
        artifact_id=artifact_id,
        ordinal=ordinal,
        provenance=provenance(chunk_id, artifact_id, heading),
        body=body if body is not None else f"본문 {chunk_id}",
    )


def document_context(
    layout: Mapping[int, Sequence[int]],
    *,
    bodies: Mapping[int, str] | None = None,
    sections: Mapping[int, int] | None = None,
    version: str | None = VERSION,
) -> Callable[[Sequence[int], int, int], ContextResult]:
    """`layout`은 {자료 id: 순서대로 놓인 청크 id들}. `sections`는 {중심 청크 id: 절 첫 청크 id}.

    돌려주는 함수는 `qk.chunk_context`처럼 동작한다. `layout`에 없는 중심은 노출되지 않은 것으로 본다.
    """
    bodies = bodies or {}
    sections = sections or {}
    where = {cid: (aid, i) for aid, ids in layout.items() for i, cid in enumerate(ids)}

    def make(cid: int) -> ContextNeighbor:
        aid, ordinal = where[cid]
        return neighbor(cid, aid, ordinal, bodies.get(cid))

    def lookup(center_ids: Sequence[int], before: int, after: int) -> ContextResult:
        items = []
        for cid in list(center_ids)[:20]:
            if cid not in where:
                continue
            aid, ordinal = where[cid]
            ids = layout[aid]
            items.append(
                ContextItem(
                    center=make(cid),
                    section_first=make(sections[cid]) if cid in sections else None,
                    before=tuple(make(c) for c in ids[max(0, ordinal - min(before, 3)) : ordinal]),
                    after=tuple(make(c) for c in ids[ordinal + 1 : ordinal + 1 + min(after, 3)]),
                )
            )
        return ContextResult(index_version=version, items=tuple(items))

    return lookup


class FakeRetrievalStore:
    """`RetrievalStore` 가짜. 정해 둔 결과를 돌려주고 호출을 기록한다. `fail`의 연산 이름에서 예외를 낸다."""

    def __init__(
        self,
        vector: SearchResult | None = None,
        keyword: KeywordSearchResult | None = None,
        context: ContextResult | Callable[[Sequence[int], int, int], ContextResult] | None = None,
        fail: Mapping[str, Exception] | None = None,
    ) -> None:
        self.vector = vector or SearchResult(status="ok", index_version=VERSION)
        self.keyword = keyword or KeywordSearchResult(status="ok", index_version=VERSION)
        self.context = context or ContextResult(index_version=VERSION)
        self.fail = dict(fail or {})
        self.calls: list[tuple[str, tuple]] = []

    def _call(self, name: str, *args: object) -> None:
        self.calls.append((name, args))
        if name in self.fail:
            raise self.fail[name]

    def names(self) -> list[str]:
        return [name for name, _ in self.calls]

    def search_vector(self, query: Sequence[float], top_n: int, filters: SearchFilter = NO_FILTER) -> SearchResult:
        self._call("search_vector", len(query), top_n, filters)
        return self.vector

    def search_keyword_terms(
        self, terms: Sequence[str], top_n: int, filters: SearchFilter = NO_FILTER
    ) -> KeywordSearchResult:
        self._call("search_keyword_terms", tuple(terms), top_n, filters)
        return self.keyword

    def chunk_context(self, center_ids: Sequence[int], before: int, after: int) -> ContextResult:
        self._call("chunk_context", tuple(center_ids), before, after)
        return self.context(center_ids, before, after) if callable(self.context) else self.context


def no_block(text: str, origin: tuple[str, str] | None) -> tuple[SendBlock, ...]:
    return ()


def blocked(text: str, origin: tuple[str, str] | None) -> tuple[SendBlock, ...]:
    return (SendBlock("test_secret_rule", 1),)


def query_embedder(
    provider: FakeEmbeddingProvider | None = None,
    *,
    check: Callable[[str, tuple[str, str] | None], tuple[SendBlock, ...]] = no_block,
    ledger: InMemoryUsageLedger | None = None,
) -> tuple[EmbeddingService, FakeEmbeddingProvider, InMemoryUsageLedger]:
    """질의 경로처럼 재시도 1회로 조립한 임베딩 서비스(research R-07). 대기는 하지 않는다."""
    provider = provider or FakeEmbeddingProvider()
    ledger = ledger or InMemoryUsageLedger(BudgetSettings())
    service = EmbeddingService(
        provider,
        MemoryEmbeddingStore(),
        ledger,
        BudgetSettings(),
        check,
        retry_policy=RetryPolicy(max_retries=1),
        sleep=lambda seconds: None,
    )
    return service, provider, ledger
