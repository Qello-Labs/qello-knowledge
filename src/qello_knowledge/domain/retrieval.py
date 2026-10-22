"""검색 흐름의 설정·요청·결과 타입(QK-RET-001 data-model 1~2절).

질문 원문과 청크 본문은 `repr`에 나오지 않는다(spec FR-008). 저장소 제품 고유 타입은 나오지 않는다(C-06).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, fields, replace
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Literal

from qello_knowledge.domain.embedding import RunSummary
from qello_knowledge.domain.keyword_rules import QUERY_RULES
from qello_knowledge.domain.store import NO_FILTER, Provenance, SearchFilter

DEFAULT_QUERY_MODEL = "@cf/baai/bge-m3"  # ADR-002, 활성 인덱스 버전의 임베딩 모델
GAP_MARKER = "\n\n(…)\n\n"  # 묶음 안 순서가 끊긴 자리(data-model 2.3)

_RANGES: Mapping[str, tuple[int, int]] = MappingProxyType(
    {
        "candidates": (1, 50),
        "rrf_k": (1, 1000),
        "expand_top": (1, 20),
        "before": (0, 3),
        "after": (0, 3),
        "context_budget": (1, 8000),
        "question_max_chars": (1, 8000),
    }
)


class RetrievalMode(StrEnum):
    HYBRID = "hybrid"
    VECTOR = "vector"
    KEYWORD = "keyword"


class RetrievalFailure(StrEnum):
    """spec FR-011의 실패 종류. 하이브리드의 축소 동작은 실패가 아니라 `Omitted`로 남는다."""

    EMPTY_QUESTION = "empty_question"
    QUESTION_TOO_LONG = "question_too_long"
    NO_ACTIVE_INDEX = "no_active_index"
    STORE_UNAVAILABLE = "store_unavailable"
    INDEX_VERSION_CHANGED = "index_version_changed"
    QUERY_EMBEDDING_FAILED = "query_embedding_failed"
    OUTGOING_BLOCKED = "outgoing_blocked"
    KEYWORD_SEARCH_FAILED = "keyword_search_failed"
    BOTH_SEARCHES_FAILED = "both_searches_failed"


class OmitReason(StrEnum):
    """하이브리드에서 한쪽 검색을 생략한 사유(research R-14)."""

    OUTGOING_BLOCKED = "outgoing_blocked"
    QUERY_EMBEDDING_FAILED = "query_embedding_failed"
    VECTOR_SEARCH_FAILED = "vector_search_failed"
    KEYWORD_SEARCH_FAILED = "keyword_search_failed"


class ChunkRole(StrEnum):
    CENTER = "center"
    SECTION_FIRST = "section_first"
    BEFORE = "before"
    AFTER = "after"


class SkipReason(StrEnum):
    LARGER_THAN_BUDGET = "larger_than_budget"
    BUDGET_EXHAUSTED = "budget_exhausted"
    NOT_VISIBLE = "not_visible"


@dataclass(frozen=True)
class RetrievalSettings:
    """검색 기본값과 범위(data-model 1.1, research R-12). 범위를 벗어나면 `ValueError`."""

    candidates: int = 20
    rrf_k: int = 60
    expand_top: int = 8
    before: int = 1
    after: int = 1
    context_budget: int = 2000
    question_max_chars: int = 2000
    query_rule: str = "kw-query-v1"
    bytes_per_token: float = 3.5

    def __post_init__(self) -> None:
        for name, (low, high) in _RANGES.items():
            value = getattr(self, name)
            if type(value) is not int or not low <= value <= high:
                raise ValueError(f"{name}는 {low}~{high} 정수여야 한다")
        if self.query_rule not in QUERY_RULES:
            raise ValueError("알 수 없는 질의 쪽 키워드 규칙")
        if not isinstance(self.bytes_per_token, (int, float)) or isinstance(self.bytes_per_token, bool):
            raise ValueError("bytes_per_token은 수여야 한다")
        if self.bytes_per_token <= 0:
            raise ValueError("bytes_per_token은 0보다 커야 한다")

    def with_overrides(self, overrides: Mapping[str, object]) -> RetrievalSettings:
        known = {f.name for f in fields(self)}
        unknown = set(overrides) - known
        if unknown:
            raise ValueError("알 수 없는 검색 설정: " + ", ".join(sorted(unknown)))
        return replace(self, **overrides)  # type: ignore[arg-type]


@dataclass(frozen=True)
class RetrievalRequest:
    question: str = field(repr=False)
    mode: RetrievalMode = RetrievalMode.HYBRID
    filters: SearchFilter = NO_FILTER
    want_context: bool = True
    overrides: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class FusedHit:
    chunk_id: int
    rank: int
    score: float
    provenance: Provenance
    vector_rank: int | None = None
    vector_score: float | None = None
    keyword_rank: int | None = None
    keyword_matched: int | None = None
    keyword_score: float | None = None


@dataclass(frozen=True)
class ContextChunk:
    chunk_id: int
    artifact_id: int
    ordinal: int
    role: ChunkRole
    heading_path: tuple[str, ...]
    locator: Mapping[str, object]
    body: str = field(repr=False)
    estimated_tokens: int = 0


@dataclass(frozen=True)
class ContextBlock:
    """문서 하나의 문맥 묶음(spec FR-013·FR-015)."""

    source_id: str
    rank: int
    artifact_id: int
    source_url: str
    source_version: str
    source_modified_at: datetime | None
    collected_at: datetime
    chunks: tuple[ContextChunk, ...]
    centers: tuple[tuple[int, int], ...]
    gaps: tuple[tuple[int, int], ...] = ()

    def __post_init__(self) -> None:
        ids = [c.chunk_id for c in self.chunks]
        if not ids or len(set(ids)) != len(ids):
            raise ValueError("묶음의 청크는 비어 있지 않고 서로 달라야 한다")
        if any(c.artifact_id != self.artifact_id for c in self.chunks):
            raise ValueError("묶음의 청크는 모두 같은 자료여야 한다")
        ordinals = [c.ordinal for c in self.chunks]
        if any(a >= b for a, b in zip(ordinals, ordinals[1:], strict=False)):
            raise ValueError("묶음의 청크는 순서 번호 오름차순이어야 한다")

    @property
    def estimated_tokens(self) -> int:
        return sum(c.estimated_tokens for c in self.chunks)

    @property
    def text(self) -> str:
        """청크 본문을 원문 순서로 잇고, 끊긴 자리에 생략 표시를 둔다."""
        parts: list[str] = []
        for previous, chunk in zip((None, *self.chunks), self.chunks, strict=False):
            if previous is not None:
                parts.append(GAP_MARKER if chunk.ordinal != previous.ordinal + 1 else "\n\n")
            parts.append(chunk.body)
        return "".join(parts)


@dataclass(frozen=True)
class Skipped:
    chunk_id: int
    role: ChunkRole
    reason: SkipReason


@dataclass(frozen=True)
class Omitted:
    search: Literal["vector", "keyword"]
    reason: OmitReason
    detail: str | None = None  # 임베딩 실패 종류 값처럼 원문 없는 구분자만


@dataclass(frozen=True)
class RetrievalSummary:
    """검색 조건과 결과 요약(spec FR-024). 질문 원문·검색어 낱말·청크 본문은 없다."""

    mode: RetrievalMode = RetrievalMode.HYBRID
    candidates: int = 0
    rrf_k: int = 0
    query_rule: str = ""
    index_rule: str = "unknown"
    index_version: str | None = None
    omitted: tuple[Omitted, ...] = ()
    vector_count: int = 0
    keyword_count: int = 0
    keyword_terms: int = 0
    block_count: int = 0
    used_tokens: int = 0
    budget: int = 0
    skipped: tuple[Skipped, ...] = ()
    embedding: RunSummary | None = None
    external_calls: int = 0
    source_revisions: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalResult:
    status: str  # "ok", "no_results" 또는 RetrievalFailure 값
    hits: tuple[FusedHit, ...] = ()
    context: tuple[ContextBlock, ...] = ()
    summary: RetrievalSummary = field(default_factory=RetrievalSummary)

    @property
    def failure(self) -> RetrievalFailure | None:
        return None if self.status in ("ok", "no_results") else RetrievalFailure(self.status)
