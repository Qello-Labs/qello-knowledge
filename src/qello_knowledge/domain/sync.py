"""동기화 판단 값. 작업 허용표는 미리 보기와 실행의 공통 경계다."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum, auto
from types import MappingProxyType
from typing import TYPE_CHECKING

from qello_knowledge.domain.chunking import ChunkedContent, ChunkingSummary
from qello_knowledge.domain.embedding import EmbedPreview
from qello_knowledge.domain.security import AccessScope, FilterSummary
from qello_knowledge.domain.source import StopInfo

if TYPE_CHECKING:
    from qello_knowledge.domain.source import SourceOrigin


class ChangeReason(StrEnum):
    NEW = "NEW"
    INPUT_CHANGED = "INPUT_CHANGED"
    CHUNKING_CHANGED = "CHUNKING_CHANGED"
    REINSTATED = "REINSTATED"
    INDEX_CHANGED = "INDEX_CHANGED"


class DocumentOutcome(StrEnum):
    PROCESSED = "PROCESSED"
    PROCESSED_EMPTY = "PROCESSED_EMPTY"
    UNCHANGED = "UNCHANGED"
    TAKEN_DOWN = "TAKEN_DOWN"
    PURGED = "PURGED"
    FAILED = "FAILED"
    HELD = "HELD"
    SKIPPED = "SKIPPED"


class HoldReason(StrEnum):
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    BUDGET_EXHAUSTED = "BUDGET_EXHAUSTED"
    INDEX_MISMATCH = "INDEX_MISMATCH"
    TAKEDOWN_RATIO = "TAKEDOWN_RATIO"
    ORIGIN_MISMATCH = "ORIGIN_MISMATCH"
    ORIGIN_MISSING = "ORIGIN_MISSING"
    COLLECTION_INCOMPLETE = "COLLECTION_INCOMPLETE"


class TakedownReason(StrEnum):
    SECURITY_PATH = "security_path"
    SECURITY_SECRET = auto()
    SECURITY_ACCESS = "security_access"
    CONFIG_EXCLUDED = "config_excluded"
    SOURCE_MISSING = "source_missing"
    NOT_TARGET = "not_target"
    SOURCE_DISABLED = "source_disabled"

    @property
    def is_security(self) -> bool:
        return self in {self.SECURITY_PATH, self.SECURITY_SECRET, self.SECURITY_ACCESS, self.CONFIG_EXCLUDED}


class Action(StrEnum):
    PROCESS = "PROCESS"
    UNCHANGED = "UNCHANGED"
    TAKE_DOWN = "TAKE_DOWN"
    PURGE = "PURGE"
    FAIL = "FAIL"
    HOLD = "HOLD"
    SKIP = "SKIP"


class Operation(StrEnum):
    PROCESS = "PROCESS"
    SECURITY_HIDE = "SECURITY_HIDE"
    SECURITY_PURGE = "SECURITY_PURGE"
    SOURCE_MISSING = "SOURCE_MISSING"
    GENERAL_TAKEDOWN = "GENERAL_TAKEDOWN"
    PURGE = "PURGE"
    MARK_SEEN = "MARK_SEEN"


_ALL = frozenset(Operation)
ALLOWED: Mapping[HoldReason, frozenset[Operation]] = MappingProxyType(
    {
        HoldReason.BUDGET_EXCEEDED: _ALL - {Operation.PROCESS},
        HoldReason.BUDGET_EXHAUSTED: _ALL,  # PROCESS는 실행 단계에서 캐시 완비 여부도 확인한다.
        HoldReason.INDEX_MISMATCH: _ALL - {Operation.PROCESS, Operation.SOURCE_MISSING, Operation.GENERAL_TAKEDOWN},
        HoldReason.TAKEDOWN_RATIO: _ALL
        - {Operation.SECURITY_PURGE, Operation.SOURCE_MISSING, Operation.GENERAL_TAKEDOWN, Operation.PURGE},
        HoldReason.ORIGIN_MISMATCH: frozenset({Operation.SECURITY_HIDE, Operation.SECURITY_PURGE}),
        HoldReason.ORIGIN_MISSING: frozenset({Operation.SECURITY_HIDE, Operation.SECURITY_PURGE}),
        HoldReason.COLLECTION_INCOMPLETE: _ALL - {Operation.SOURCE_MISSING},
    }
)


def allowed(holds, operation: Operation) -> bool:
    operation = Operation(operation)
    return all(operation in ALLOWED[HoldReason(hold)] for hold in holds)


@dataclass(frozen=True, kw_only=True)
class DocumentDecision:
    doc_key: str
    display: str
    actions: tuple[Action, ...]
    artifact_id: int | None = None
    change_reason: ChangeReason | None = None
    takedown_reason: TakedownReason | None = None
    delete_bodies: bool = False
    chunked: ChunkedContent | None = field(default=None, repr=False)
    stage: str | None = None
    failure: str | None = None
    source_id: str = field(default="", repr=False)
    source_name: str = ""
    fingerprint: str | None = None
    access_scope: AccessScope | None = None
    rule: str | None = None
    lines: tuple[int, ...] = ()
    hold: HoldReason | None = None

    def __post_init__(self):
        actions = tuple(Action(a) for a in self.actions)
        if not actions or len(set(actions)) != len(actions) or len(actions) > 2:
            raise ValueError("invalid decision actions")
        if len(actions) == 2 and (actions[0] != Action.PURGE or actions[1] == Action.PURGE):
            raise ValueError("purge must precede the document action")
        if Action.TAKE_DOWN in actions and self.takedown_reason is None:
            raise ValueError("takedown requires reason")
        object.__setattr__(self, "actions", actions)
        if self.takedown_reason is not None:
            object.__setattr__(self, "takedown_reason", TakedownReason(self.takedown_reason))


@dataclass(frozen=True, kw_only=True)
class SourcePlan:
    source_name: str
    mode: str = "FULL"
    origin_version: str | None = None
    listing_complete: bool | None = None
    stop: StopInfo | None = None
    fetch_summary: Mapping = field(default_factory=dict)
    origin: SourceOrigin | None = None
    origin_check: str = "OK"
    decisions: tuple[DocumentDecision, ...] = ()
    takedown_ratio: Mapping = field(default_factory=dict)
    holds: frozenset[HoldReason] = frozenset()
    filter_summary: FilterSummary | None = None
    chunking_summary: ChunkingSummary | None = None

    def __post_init__(self):
        if self.mode not in {"FULL", "TAKEDOWN_ONLY"}:
            raise ValueError("invalid source mode")
        for doc in self.decisions:
            operations = []
            for action in doc.actions:
                if action == Action.PROCESS:
                    if self.mode == "TAKEDOWN_ONLY":
                        raise ValueError("takedown-only cannot process")
                    operations.append(Operation.PROCESS)
                elif action == Action.UNCHANGED:
                    operations.append(Operation.MARK_SEEN)
                elif action == Action.PURGE:
                    operations.append(Operation.PURGE)
                elif action == Action.TAKE_DOWN:
                    reason = doc.takedown_reason
                    if reason.is_security:
                        operations.append(Operation.SECURITY_HIDE)
                        if doc.delete_bodies:
                            operations.append(Operation.SECURITY_PURGE)
                    else:
                        operations.append(
                            Operation.SOURCE_MISSING
                            if reason == TakedownReason.SOURCE_MISSING
                            else Operation.GENERAL_TAKEDOWN
                        )
            if any(not allowed(self.holds, operation) for operation in operations):
                raise ValueError("source plan contains a held operation")


@dataclass(frozen=True)
class SyncPreview:
    sources: tuple[Mapping, ...]
    embedding_preview: EmbedPreview
    index_state: Mapping
    runnable: bool
    confirm_takedown: bool = False
    allow_partial_budget: bool = False


@dataclass(frozen=True)
class SyncRunResult:
    run_id: str
    status: str
    sources: tuple[Mapping, ...]
    exit_code: int
    summary: Mapping = field(default_factory=dict)


@dataclass(frozen=True)
class ActivationCheck:
    version: str
    documents: int
    chunks: int
    chunks_without_vector: int
    last_run_status: str | None
    failed_conditions: tuple[str, ...]
