"""검색 경계(QK-RET-001 contracts/retrieval.md 2절).

검색 흐름(`retrieval/`)이 쓰는 저장소 연산 세 개만 가진 좁은 경계다.
노출 조건(활성 인덱스 버전, 활성 자료, 팀 공용 접근 범위)은 구현의 질의 안에서만 판정한다(spec FR-007, C-14).
`domain/store.py`의 타입은 바꾸지 않고 감싼다.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol

from qello_knowledge.domain.store import NO_FILTER, Provenance, SearchFilter, SearchHit, SearchResult, SearchStatus


@dataclass(frozen=True)
class KeywordHit:
    hit: SearchHit
    matched_terms: int


@dataclass(frozen=True)
class KeywordSearchResult:
    status: SearchStatus
    index_version: str | None = None
    hits: tuple[KeywordHit, ...] = ()


@dataclass(frozen=True)
class ContextNeighbor:
    chunk_id: int
    artifact_id: int
    ordinal: int
    provenance: Provenance
    body: str = field(repr=False)


@dataclass(frozen=True)
class ContextItem:
    center: ContextNeighbor
    section_first: ContextNeighbor | None = None
    before: tuple[ContextNeighbor, ...] = ()
    after: tuple[ContextNeighbor, ...] = ()


@dataclass(frozen=True)
class ContextResult:
    index_version: str | None
    items: tuple[ContextItem, ...] = ()


class RetrievalStore(Protocol):
    def search_vector(self, query: Sequence[float], top_n: int, filters: SearchFilter = NO_FILTER) -> SearchResult:
        """QK-STO-001 벡터 검색 그대로."""
        ...

    def search_keyword_terms(
        self, terms: Sequence[str], top_n: int, filters: SearchFilter = NO_FILTER
    ) -> KeywordSearchResult:
        """낱말 배열 키워드 검색. 서로 다른 맞은 낱말 수 → OR 질의 점수 → 청크 식별자 순(research R-03)."""
        ...

    def chunk_context(self, center_ids: Sequence[int], before: int, after: int) -> ContextResult:
        """중심 청크들을 다시 확인하고 같은 문서의 주변 청크를 한 번에 가져온다(research R-06)."""
        ...
