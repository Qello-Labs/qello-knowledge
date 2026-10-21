"""동기화 저장 경계. 외부 SDK와 청크 본문을 상태 조회에 노출하지 않는다."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from qello_knowledge.domain.source import SourceOrigin
from qello_knowledge.domain.store import ArtifactRecord, ChunkInput
from qello_knowledge.domain.sync import ActivationCheck, DocumentDecision, DocumentOutcome


@dataclass(frozen=True)
class IndexState:
    active: str | None = None
    ready: tuple[str, ...] = ()


@dataclass(frozen=True)
class IndexSpec:
    id: str
    embedding_model: str
    dimension: int
    chunking_version: str
    metadata_schema_version: str = "meta-v1"


@dataclass(frozen=True, kw_only=True)
class StoredDocument:
    artifact_id: int
    source_id: str = field(repr=False)
    source_name: str | None
    source_kind: str
    location: str | None = field(default=None, repr=False)
    chunk_input_hash: str | None = None
    processed_chunking_version: str | None = None
    processed_index_version: str | None = None
    processed_outcome: str | None = None
    last_seen_version: str | None = None
    last_seen_at: datetime | None = None
    takedown_reason: str | None = None
    takedown_at: datetime | None = None
    purge_pending: tuple[str, ...] = ()
    purge_reason: str | None = None
    source_url: str = field(default="", repr=False)
    source_version: str = ""
    content_hash: str = ""
    collected_at: datetime | None = None
    access_scope: str | None = None
    status: str = "active"


@dataclass(frozen=True)
class StoredSource:
    source_name: str
    source_kind: str
    scope_key: str = field(repr=False)
    origin_id: str | None = field(default=None, repr=False)
    origin_name: str | None = field(default=None, repr=False)


@dataclass(frozen=True)
class ArtifactWrite:
    record: ArtifactRecord = field(repr=False)
    source_name: str
    location: str = field(repr=False)
    chunk_input_hash: str
    chunking_version: str
    processed_outcome: str


@dataclass(frozen=True)
class RunInfo:
    run_id: str
    trigger: str
    target: str
    rules_version: str
    chunking_version: str
    index_version: str
    source_kinds: tuple[str, ...] = ()


class SyncLock(Protocol):
    def close(self) -> None: ...


class SyncStore(Protocol):
    def index_state(self) -> IndexState: ...
    def ensure_index_version(self, spec: IndexSpec) -> str: ...
    def load_documents(self, source_kind: str) -> Mapping[str, StoredDocument]: ...
    def load_sources(self) -> Mapping[str, StoredSource]: ...
    def try_lock(self, source_kinds: Sequence[str]) -> SyncLock | None: ...
    def begin_run(self, run: RunInfo, source_names: Sequence[str]) -> None: ...
    def register_origin(self, source_name: str, kind: str, scope_key: str, origin: SourceOrigin) -> None: ...
    def apply_document(
        self,
        run_id: str,
        doc: DocumentDecision,
        artifact: ArtifactWrite,
        index_version: str,
        chunks: Sequence[ChunkInput],
    ) -> int: ...
    def take_down(self, run_id, doc, reason, access_scope, delete_bodies) -> None: ...
    def purge_pending_bodies(self, run_id, doc) -> None: ...
    def mark_seen(self, run_id, docs, version, at) -> None: ...
    def record_outcome(self, run_id: str, doc: DocumentDecision, action: str, outcome: DocumentOutcome) -> None: ...
    def finish_source(self, run_id, source_name, status, summary) -> None: ...
    def finish_run(self, run_id, status, summary) -> None: ...
    def activation_check(self, version: str) -> ActivationCheck: ...
    def activate(self, version: str) -> ActivationCheck: ...
    def list_runs(self, limit: int): ...
    def run_detail(self, run_id: str): ...
    def run_failures(self, run_id: str): ...
    def prune_runs(self, retention_days: int): ...
