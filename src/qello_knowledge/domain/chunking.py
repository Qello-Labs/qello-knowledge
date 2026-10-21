"""Markdown 청킹 값 객체. 본문과 제목을 repr·요약에 노출하지 않는다."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from statistics import median_low
from types import MappingProxyType

from qello_knowledge.domain.embedding import MODELS
from qello_knowledge.domain.security import ScreenedContent
from qello_knowledge.domain.store import ChunkInput

WORST_BYTES_PER_TOKEN = 1.2


@dataclass(frozen=True)
class ChunkingSettings:
    model_version: str = "@cf/baai/bge-m3"
    target_tokens: int = 512
    limit_tokens: int = 2800

    def __post_init__(self) -> None:
        model = MODELS.get(self.model_version)
        if (
            model is None
            or type(self.target_tokens) is not int
            or type(self.limit_tokens) is not int
            or not 1 <= self.target_tokens <= self.limit_tokens
        ):
            raise ValueError("청킹 설정이 올바르지 않다")
        if self.limit_tokens * model.bytes_per_token_estimate / WORST_BYTES_PER_TOKEN > model.max_input_tokens:
            raise ValueError("청킹 상한이 모델 안전 여유를 넘는다")


class ChunkOutcomeKind(StrEnum):
    CHUNKED = "CHUNKED"
    EMPTY = "EMPTY"
    NOT_MARKDOWN = "NOT_MARKDOWN"
    FAILED = "FAILED"


class ChunkFailureKind(StrEnum):
    LINE_TOO_LONG = "LINE_TOO_LONG"
    HEADER_TOO_LONG = "HEADER_TOO_LONG"
    PROCESSING_ERROR = "PROCESSING_ERROR"


class StructureWarningKind(StrEnum):
    TABLE_CELL_MISMATCH = "TABLE_CELL_MISMATCH"
    UNCLOSED_FENCE = "UNCLOSED_FENCE"


@dataclass(frozen=True)
class StructureWarning:
    kind: StructureWarningKind
    line: int


@dataclass(frozen=True)
class ChunkDraft:
    chunk: ChunkInput = field(repr=False)
    search_header: str = field(repr=False)
    embedding_text: str = field(repr=False)
    estimated_tokens: int


@dataclass(frozen=True)
class ChunkOutcome:
    outcome: ChunkOutcomeKind
    document_title: str | None = field(repr=False)
    drafts: tuple[ChunkDraft, ...]
    warnings: tuple[StructureWarning, ...]
    failure: ChunkFailureKind | None
    split_blocks: int
    chunking_version: str

    def __post_init__(self) -> None:
        if bool(self.drafts) != (self.outcome == ChunkOutcomeKind.CHUNKED):
            raise ValueError("drafts require CHUNKED")
        if (self.failure is not None) != (self.outcome == ChunkOutcomeKind.FAILED):
            raise ValueError("failure requires FAILED")
        if self.split_blocks < 0 or (self.outcome != ChunkOutcomeKind.CHUNKED and self.split_blocks != 0):
            raise ValueError("split_blocks require CHUNKED")
        if self.warnings and self.outcome != ChunkOutcomeKind.CHUNKED:
            raise ValueError("warnings require CHUNKED")


@dataclass(frozen=True, kw_only=True)
class ChunkedContent(ChunkOutcome):
    screened: ScreenedContent = field(repr=False)


@dataclass(frozen=True)
class ChunkingSummary:
    chunking_version: str
    by_outcome: Mapping[ChunkOutcomeKind, int]
    chunk_count: int
    by_failure: Mapping[ChunkFailureKind, int]
    by_warning: Mapping[StructureWarningKind, int]
    tokens_min: int | None
    tokens_median: int | None
    tokens_max: int | None
    split_blocks: int

    @classmethod
    def from_results(cls, results: Iterable[ChunkedContent]) -> ChunkingSummary:
        results = tuple(results)
        tokens = [d.estimated_tokens for r in results for d in r.drafts]
        return cls(
            results[0].chunking_version if results else "",
            MappingProxyType(dict(Counter(r.outcome for r in results))),
            len(tokens),
            MappingProxyType(dict(Counter(r.failure for r in results if r.failure is not None))),
            MappingProxyType(dict(Counter(w.kind for r in results for w in r.warnings))),
            min(tokens) if tokens else None,
            median_low(tokens) if tokens else None,
            max(tokens) if tokens else None,
            sum(r.split_blocks for r in results),
        )


@dataclass(frozen=True)
class ChunkingResult:
    results: tuple[ChunkedContent, ...]
    summary: ChunkingSummary
