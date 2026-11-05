"""인덱스 버전 수명 저장 경계(QK-STO-002 data-model 2.3, research R-15).

활성화·되돌리기·정리·상태 보기가 쓴다. 반환값에 청크 본문과 접속 정보를 담지 않는다.
인자 이름 `version`은 인덱스 버전 ID이고, 실행 위치(`local`·`remote`)는 구현의 생성 인자다.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol


@dataclass(frozen=True)
class RunRef:
    run_id: str
    status: str
    finished_at: datetime | None


@dataclass(frozen=True)
class VersionRow:
    id: str
    embedding_model: str
    dimension: int
    chunking_version: str
    metadata_schema_version: str
    status: str
    created_at: datetime
    activated_at: datetime | None
    pruned_at: datetime | None
    documents: int  # 그 버전 청크가 있고 노출 조건(`active`, `team`)을 채우는 자료 수
    chunks: int
    chunks_without_vector: int
    ever_active: bool
    last_reindex: RunRef | None


@dataclass(frozen=True)
class FailedDoc:
    display: str
    stage: str | None
    run_id: str


@dataclass(frozen=True)
class Coverage:
    """활성 버전 노출 문서 가운데 `version` 처리를 마친 수(research R-04)."""

    version: str
    visible: int
    covered: int
    remaining: int
    failed: tuple[FailedDoc, ...] = ()


@dataclass(frozen=True)
class SourceRef:
    name: str
    kind: str


@dataclass(frozen=True)
class ActivationState:
    active: VersionRow | None
    target: VersionRow | None
    current: str | None
    sync_running: bool
    coverage: Coverage | None
    purge_pending: int  # `purge_pending`에 대상 버전이 든 자료 수
    tokenizer: str | None  # 운영 키워드 색인 토크나이저
    sources: tuple[SourceRef, ...] = ()


@dataclass(frozen=True)
class RollbackState:
    active: VersionRow | None
    target: VersionRow | None
    current: str | None
    sync_running: bool
    purge_pending: int
    missing_documents: int  # 지금 노출 문서 가운데 대상 버전 청크가 없는 수
    provenance_mismatch: int  # 대상 버전 청크의 원본 버전 ≠ 자료 행 원본 버전인 노출 문서 수(research R-01)


@dataclass(frozen=True)
class PruneState:
    target: VersionRow | None
    active: str | None
    current: str | None
    rollback_target: str | None
    remaining_chunks: int
    sync_running: bool


@dataclass(frozen=True)
class TransitionRow:
    id: int
    kind: str
    at: datetime
    version: str
    before_active: str | None
    after_active: str | None
    documents: int
    chunks: int
    target: str
    gate_record_id: str | None = None
    gate_record_sha256: str | None = None
    reason: str | None = None
    provenance_mismatch: int | None = None
    deleted_chunks: int | None = None
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SwitchResult:
    applied: bool
    failed_conditions: tuple[str, ...]
    transition_id: int | None = None


@dataclass(frozen=True)
class PruneResult:
    applied: bool
    failed_conditions: tuple[str, ...]
    deleted_chunks: int = 0
    pruned: bool = False


Check = Callable[[Any], Sequence[str]]


class IndexVersionStore(Protocol):
    current_version: str | None

    def versions(self) -> tuple[VersionRow, ...]: ...
    def coverage(self, version: str) -> Coverage | None: ...
    def mismatch_since(self, active: str, current: str) -> datetime | None: ...
    def activation_state(self, version: str) -> ActivationState: ...
    def rollback_state(self, version: str) -> RollbackState: ...
    def prune_state(self, version: str) -> PruneState: ...
    def rollback_target(self) -> str | None: ...
    def switch_active(
        self,
        version: str,
        *,
        check: Check,
        kind: str,
        gate_record_id: str | None = None,
        gate_record_sha256: str | None = None,
        reason: str | None = None,
        provenance_mismatch: int | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> SwitchResult: ...
    def prune(
        self, version: str, *, check: Check, batch_size: int = 1000, after_batch: Callable[[int], None] | None = None
    ) -> PruneResult: ...
    def transitions(self, version: str | None = None) -> tuple[TransitionRow, ...]: ...
    def close(self) -> None: ...
