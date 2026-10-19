"""저장소 경계의 입력·출력 타입(QK-STO-001 contracts/store.md).

저장소 제품 고유 타입(psycopg, pgvector)은 여기에 나오지 않는다(FR-015, C-06).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Literal

EMBEDDING_DIMENSION = 1024  # ADR-002 bge-m3
TOP_N_LIMIT = 50  # FR-010 초기값

ReplaceOutcome = Literal["replaced", "unchanged"]
SearchStatus = Literal["ok", "no_active_index"]


class StoreError(Exception):
    """저장소 오류. 메시지에 접속 정보나 비밀 값을 넣지 않는다."""


class InvalidRecord(StoreError):  # noqa: N818 - 계약(contracts/store.md)의 이름을 따른다
    """출처 누락, 차원 불일치, 빈 위치 정보처럼 저장할 수 없는 입력."""


class StoreUnavailable(StoreError):  # noqa: N818 - 계약의 이름을 따른다
    """연결 실패, 운영 인스턴스 중지·회수."""


@dataclass(frozen=True)
class ArtifactRecord:
    source_kind: str
    source_id: str
    source_url: str
    source_version: str
    collected_at: datetime
    content_hash: str
    artifact_kind: str
    title: str | None = None
    source_modified_at: datetime | None = None
    access_scope: str | None = None


@dataclass(frozen=True)
class EmbeddingRef:
    input_hash: str
    model_version: str


@dataclass(frozen=True)
class ChunkInput:
    ordinal: int
    locator: Mapping[str, object]
    body: str
    search_text: str
    chunking_version: str
    heading_path: tuple[str, ...] = ()
    embedding: EmbeddingRef | None = None


@dataclass(frozen=True)
class SearchFilter:
    source_kinds: tuple[str, ...] = ()
    artifact_kinds: tuple[str, ...] = ()


NO_FILTER = SearchFilter()


@dataclass(frozen=True)
class Provenance:
    source_url: str
    source_version: str
    locator: Mapping[str, object]
    heading_path: tuple[str, ...]
    collected_at: datetime
    source_modified_at: datetime | None = None


@dataclass(frozen=True)
class SearchHit:
    chunk_id: int
    rank: int
    score: float
    body: str
    provenance: Provenance


@dataclass(frozen=True)
class SearchResult:
    status: SearchStatus
    index_version: str | None = None
    hits: tuple[SearchHit, ...] = ()


@dataclass(frozen=True)
class NeighborResult:
    center: SearchHit
    before: tuple[SearchHit, ...] = ()
    after: tuple[SearchHit, ...] = ()
    parents: tuple[SearchHit, ...] = ()


@dataclass(frozen=True)
class ChunkTrace:
    """청크 하나를 원본까지 되짚는 정보(US1, SC-001)."""

    chunk_id: int
    provenance: Provenance
    chunking_version: str
    index_version: str
    embedding_model: str | None = None


@dataclass(frozen=True)
class StoreUsage:
    total_bytes: int
    chunk_count: int
    embedding_count: int


def _require(value: str | None, name: str) -> None:
    if value is None or not value.strip():
        raise InvalidRecord(f"{name}이(가) 비어 있다")


def validate_artifact(record: ArtifactRecord) -> None:
    """출처 필수 항목을 검사한다(FR-004). DB 제약이 같은 규칙을 한 번 더 강제한다."""
    for name in ("source_kind", "source_id", "source_url", "source_version", "content_hash", "artifact_kind"):
        _require(getattr(record, name), name)


def validate_chunks(source_version: str, chunks: Sequence[ChunkInput]) -> None:
    _require(source_version, "source_version")
    seen: set[int] = set()
    for chunk in chunks:
        if chunk.ordinal < 0 or chunk.ordinal in seen:
            raise InvalidRecord(f"청크 순서 {chunk.ordinal}이(가) 음수이거나 중복이다")
        seen.add(chunk.ordinal)
        if not chunk.locator:
            raise InvalidRecord(f"청크 {chunk.ordinal}의 위치 정보가 비어 있다")
        _require(chunk.chunking_version, "chunking_version")


def validate_vector(vector: Sequence[float]) -> None:
    if len(vector) != EMBEDDING_DIMENSION:
        raise InvalidRecord(f"벡터 차원이 {EMBEDDING_DIMENSION}이 아니다: {len(vector)}")


def clamp_top_n(top_n: int) -> int:
    return max(1, min(top_n, TOP_N_LIMIT))


def chunk_set_hash(index_version: str, source_version: str, chunks: Sequence[ChunkInput]) -> str:
    """같은 인덱스 버전·같은 원본 버전·같은 청크 묶음이면 같은 값이다(교체 멱등 판정, research R-07)."""
    key = {
        "index_version": index_version,
        "source_version": source_version,
        "chunks": [asdict(c) for c in sorted(chunks, key=lambda c: c.ordinal)],
    }
    payload = json.dumps(key, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
