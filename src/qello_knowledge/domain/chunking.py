"""Markdown·코드 청킹 값 객체. 본문·제목·코드 메타데이터를 repr·요약에 노출하지 않는다."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from statistics import median_low
from types import MappingProxyType

from qello_knowledge.domain.embedding import MODELS
from qello_knowledge.domain.keyword_rules import INDEX_BASELINE, INDEX_RULES
from qello_knowledge.domain.security import ScreenedContent
from qello_knowledge.domain.store import ChunkInput

WORST_BYTES_PER_TOKEN = 1.2


@dataclass(frozen=True)
class ChunkingSettings:
    model_version: str = "@cf/baai/bge-m3"
    target_tokens: int = 512
    limit_tokens: int = 2800
    keyword_text_rule: str = INDEX_BASELINE  # QK-RET-001 색인 쪽 키워드 규칙. 운영 기본값은 기준선(research R-04)

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
        if self.keyword_text_rule not in INDEX_RULES:
            raise ValueError("알 수 없는 색인 쪽 키워드 규칙")


@dataclass(frozen=True)
class CodeChunkingSettings:
    """코드 청킹 설정(QK-CHK-001 data-model). 값이 없으면(`None`) 코드 청킹이 꺼져 있다."""

    model_version: str = "@cf/baai/bge-m3"
    target_tokens: int = 512
    limit_tokens: int = 1500  # Context 예산 비교는 `qk-index check` 교차 검사(research R-03)

    def __post_init__(self) -> None:
        model = MODELS.get(self.model_version)
        if (
            model is None
            or type(self.target_tokens) is not int
            or type(self.limit_tokens) is not int
            or not 1 <= self.target_tokens <= self.limit_tokens
        ):
            raise ValueError("코드 청킹 설정이 올바르지 않다")
        if self.limit_tokens * model.bytes_per_token_estimate / WORST_BYTES_PER_TOKEN > model.max_input_tokens:
            raise ValueError("코드 청킹 상한이 모델 안전 여유를 넘는다")


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
    PARSE_FALLBACK = "PARSE_FALLBACK"  # 구문 해석 실패로 파일 전체를 대체 청킹했다(QK-CHK-001 FR-019)
    CONTEXT_OMITTED = "CONTEXT_OMITTED"  # 임베딩 입력에서 맥락 줄을 뺐다(QK-CHK-001 FR-018)


class CodeChunkKind(StrEnum):
    FILE_HEAD = "FILE_HEAD"
    FILE_SUMMARY = "FILE_SUMMARY"
    TYPE_SUMMARY = "TYPE_SUMMARY"
    TYPE_HEAD = "TYPE_HEAD"
    METHOD = "METHOD"
    CONSTRUCTOR = "CONSTRUCTOR"
    TOP_FUNCTION = "TOP_FUNCTION"
    FIELDS = "FIELDS"
    TOP_PROPERTIES = "TOP_PROPERTIES"
    INITIALIZER = "INITIALIZER"
    FALLBACK = "FALLBACK"


class AndroidComponent(StrEnum):
    ACTIVITY = "ACTIVITY"
    FRAGMENT = "FRAGMENT"
    VIEW_MODEL = "VIEW_MODEL"
    SERVICE = "SERVICE"
    BROADCAST_RECEIVER = "BROADCAST_RECEIVER"
    CONTENT_PROVIDER = "CONTENT_PROVIDER"
    APPLICATION = "APPLICATION"
    COMPOSABLE = "COMPOSABLE"


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
    code_chunking_version: str | None = None
    by_code_kind: Mapping[CodeChunkKind, int] = field(default_factory=lambda: MappingProxyType({}))
    code_test_chunks: int = 0
    code_components: Mapping[AndroidComponent, int] = field(default_factory=lambda: MappingProxyType({}))

    @classmethod
    def from_results(
        cls,
        results: Iterable[ChunkedContent],
        *,
        chunking_version: str | None = None,
        code_chunking_version: str | None = None,
    ) -> ChunkingSummary:
        results = tuple(results)
        tokens = [d.estimated_tokens for r in results for d in r.drafts]
        kinds, components, tests = _code_counts(results)
        if chunking_version is None:
            chunking_version = results[0].chunking_version if results else ""
        return cls(
            chunking_version,
            MappingProxyType(dict(Counter(r.outcome for r in results))),
            len(tokens),
            MappingProxyType(dict(Counter(r.failure for r in results if r.failure is not None))),
            MappingProxyType(dict(Counter(w.kind for r in results for w in r.warnings))),
            min(tokens) if tokens else None,
            median_low(tokens) if tokens else None,
            max(tokens) if tokens else None,
            sum(r.split_blocks for r in results),
            code_chunking_version,
            MappingProxyType(dict(kinds)),
            tests,
            MappingProxyType(dict(components)),
        )


def _code_counts(results: tuple[ChunkedContent, ...]) -> tuple[Counter, Counter, int]:
    """코드 청크 수치. 컴포넌트는 같은 심볼 경로·종류가 이어지는 조각 중 첫 청크에서만 센다(tasks T005)."""
    kinds: Counter = Counter()
    components: Counter = Counter()
    tests = 0
    for result in results:
        previous = None
        for draft in result.drafts:
            code = draft.chunk.locator.get("code")
            if not isinstance(code, Mapping):
                previous = None
                continue
            kind = CodeChunkKind(code["chunk_kind"])
            kinds[kind] += 1
            tests += bool(code["test_code"])
            key = (draft.chunk.heading_path, kind, code["summary"])
            component = code["component"]
            if key != previous and component:
                composable = component == AndroidComponent.COMPOSABLE
                if (kind == CodeChunkKind.TYPE_HEAD and not composable) or (
                    composable and kind in (CodeChunkKind.METHOD, CodeChunkKind.TOP_FUNCTION)
                ):
                    components[AndroidComponent(component)] += 1
            previous = key
    return kinds, components, tests


@dataclass(frozen=True)
class ChunkingResult:
    results: tuple[ChunkedContent, ...]
    summary: ChunkingSummary
