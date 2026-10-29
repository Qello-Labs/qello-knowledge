"""질의 관측 데이터. 원문은 동의 대기에만, 식별자는 repr에 넣지 않는다."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from types import MappingProxyType


class RecordStatus(StrEnum):
    ANSWERED = "answered"
    CANNOT_CONFIRM = "cannot_confirm"
    RETRIEVAL_FAILED = "retrieval_failed"
    GENERATION_FAILED = "generation_failed"
    OUTGOING_BLOCKED = "outgoing_blocked"
    TIMED_OUT = "timed_out"
    NOT_STARTED = "not_started"
    FAILED = "failed"
    UNDELIVERED = "undelivered"
    BUSY = "busy"


class FeedbackValue(StrEnum):
    UP = "up"
    DOWN = "down"


class ComponentAction(StrEnum):
    UP = "up"
    DOWN = "down"
    KEEP = "keep"
    SKIP = "skip"


@dataclass(frozen=True)
class QueryRecord:
    run_id: str
    received_at: datetime
    questioner_id: str | None = field(repr=False)
    private: bool
    status: RecordStatus
    failure: str | None = None
    first_response_ms: int = 0
    stage_ms: Mapping[str, int] = field(default_factory=dict)
    calls: Mapping[str, int] = field(default_factory=dict)
    retrieval: Mapping[str, object] = field(default_factory=dict)
    generation: Mapping[str, object] = field(default_factory=dict)
    input_tokens: int | None = None
    output_tokens: int | None = None
    context_chunk_ids: tuple[int, ...] = ()
    context_block_sizes: tuple[int, ...] = ()
    cited_blocks: tuple[int, ...] = ()
    index_version: str | None = None
    model_id: str | None = None
    prompt_version: str | None = None

    def __post_init__(self):
        for name in ("stage_ms", "calls", "retrieval", "generation"):
            object.__setattr__(self, name, MappingProxyType(dict(getattr(self, name))))
        for name in ("context_chunk_ids", "context_block_sizes", "cited_blocks"):
            object.__setattr__(self, name, tuple(getattr(self, name)))


@dataclass(frozen=True)
class QueryDelivery:
    run_id: str
    final_status: RecordStatus | None = None
    total_ms: int = 0
    deliver_ms: int = 0
    deliver_calls: int = 0
    deliver_retries: int = 0
    deliver_failure: str | None = None


@dataclass(frozen=True)
class PendingQuestion:
    run_id: str
    questioner_id: str = field(repr=False)
    question: str | None = field(repr=False)
    state: str
    expires_at: float


@dataclass(frozen=True)
class SourceSummary:
    name: str
    kind: str
    documents: int
    last_seen_at: datetime


@dataclass(frozen=True)
class SourcesView:
    index_version: str | None
    activated_at: datetime | None
    sources: tuple[SourceSummary, ...] = ()
