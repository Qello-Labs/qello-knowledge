"""저장소 경계(QK-STO-001 contracts/store.md).

후속 명세(QK-EMB-001, QK-SYN-001, QK-RET-001, QK-STO-002)는 이 Protocol만 보고 저장소를 쓴다.
노출 조건(활성 인덱스 버전, 활성 자료, 팀 공용 접근 범위)은 구현의 질의 안에서만 판정한다(FR-008, C-14).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from qello_knowledge.domain.store import (
    NO_FILTER,
    ArtifactRecord,
    ChunkInput,
    ChunkTrace,
    EmbeddingRef,
    NeighborResult,
    ReplaceOutcome,
    SearchFilter,
    SearchResult,
    StoreUsage,
)


class Store(Protocol):
    """청크와 벡터를 저장하고 검색한다."""

    def upsert_artifact(self, record: ArtifactRecord) -> int:
        """`(source_kind, source_id)`로 원본 자료를 넣거나 갱신하고 id를 돌려준다."""
        ...

    def replace_chunks(
        self, artifact_id: int, index_version: str, source_version: str, chunks: Sequence[ChunkInput]
    ) -> ReplaceOutcome:
        """자료 하나의 청크 묶음을 한 번에 바꾼다. 실패하면 이전 묶음이 남는다(FR-012·013)."""
        ...

    def mark_deleted(self, source_kind: str, source_id: str) -> None:
        """자료를 삭제 상태로 바꾼다. 바뀐 즉시 모든 검색에서 빠진다(FR-014)."""
        ...

    def put_embedding(self, ref: EmbeddingRef, vector: Sequence[float]) -> None:
        """벡터를 저장한다. 같은 (입력 해시, 모델 버전)이 있으면 그대로 둔다(FR-003)."""
        ...

    def find_embedding(self, ref: EmbeddingRef) -> tuple[float, ...] | None:
        """저장된 벡터를 돌려준다. 없으면 `None`(US5)."""
        ...

    def find_embeddings(self, refs: Sequence[EmbeddingRef]) -> dict[EmbeddingRef, tuple[float, ...]]:
        """여러 키를 한 번에 조회한다. 없는 키는 결과에 없다(QK-EMB-001 research R-07)."""
        ...

    def search_vector(self, query: Sequence[float], top_n: int, filters: SearchFilter = NO_FILTER) -> SearchResult:
        """거리 순 상위 N(최대 50) 청크(FR-006)."""
        ...

    def search_keyword(self, query: str, top_n: int, filters: SearchFilter = NO_FILTER) -> SearchResult:
        """관련도 순 상위 N(최대 50) 청크. 빈 검색어는 빈 결과(FR-007)."""
        ...

    def chunk_neighbors(self, chunk_id: int, before: int, after: int) -> NeighborResult | None:
        """같은 자료 안 앞뒤 청크와 상위 절. 노출되지 않는 청크면 `None`(FR-011)."""
        ...

    def trace_chunk(self, chunk_id: int) -> ChunkTrace | None:
        """청크를 원본 위치·규칙 버전·모델 버전까지 되짚는다(US1). 노출 조건은 걸지 않는다."""
        ...

    def usage(self) -> StoreUsage:
        """전체 크기, 청크 수, 벡터 수(FR-023)."""
        ...
