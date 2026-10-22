"""Context 담기와 문서별 묶음(QK-RET-001 spec FR-013·FR-015·FR-016, contracts/retrieval.md 4절).

담는 순서: 통합 순위 순서로 중심 청크를 먼저 담고, 다시 순위 순서로 중심마다 절 첫 청크 → 앞 청크(가까운 것부터) →
뒤 청크(가까운 것부터)를 붙인다. 청크는 자르지 않는다. 담은 청크는 문서별로 모아 원문 순서의 묶음 하나로 만든다.
"""

from __future__ import annotations

import math
from collections.abc import Iterable

from qello_knowledge.domain.retrieval import (
    ChunkRole,
    ContextBlock,
    ContextChunk,
    FusedHit,
    RetrievalSettings,
    Skipped,
    SkipReason,
)
from qello_knowledge.ports.retrieval import ContextItem, ContextNeighbor, ContextResult


def estimated_tokens(text: str, bytes_per_token: float) -> int:
    """`embedding/estimate.py`와 같은 식. `ModelSpec` 대신 설정값을 받는다."""
    return math.ceil(len(text.encode("utf-8")) / bytes_per_token)


def _candidates(item: ContextItem) -> Iterable[tuple[ContextNeighbor, ChunkRole]]:
    if item.section_first is not None:
        yield item.section_first, ChunkRole.SECTION_FIRST
    for neighbor in reversed(item.before):  # 가까운 것부터
        yield neighbor, ChunkRole.BEFORE
    for neighbor in item.after:
        yield neighbor, ChunkRole.AFTER


def pack(
    hits: tuple[FusedHit, ...], context: ContextResult, settings: RetrievalSettings
) -> tuple[tuple[ContextBlock, ...], tuple[Skipped, ...], int]:
    """`context`에 있는 중심만 담는다(저장소가 다시 확인한 중심, spec FR-012)."""
    rank_of = {h.chunk_id: h.rank for h in hits}
    items = sorted((i for i in context.items if i.center.chunk_id in rank_of), key=lambda i: rank_of[i.center.chunk_id])
    budget = settings.context_budget
    used = 0
    taken: dict[int, tuple[ContextNeighbor, ChunkRole, int]] = {}
    skipped: dict[int, Skipped] = {}

    def tokens(neighbor: ContextNeighbor) -> int:
        return estimated_tokens(neighbor.body, settings.bytes_per_token)

    def take(neighbor: ContextNeighbor, role: ChunkRole) -> None:
        nonlocal used
        cost = tokens(neighbor)
        taken[neighbor.chunk_id] = (neighbor, role, cost)
        used += cost
        skipped.pop(neighbor.chunk_id, None)

    def skip(neighbor: ContextNeighbor, role: ChunkRole, reason: SkipReason) -> None:
        skipped.setdefault(neighbor.chunk_id, Skipped(neighbor.chunk_id, role, reason))

    centers: list[ContextItem] = []
    for item in items:
        cost = tokens(item.center)
        if cost > budget:
            skip(item.center, ChunkRole.CENTER, SkipReason.LARGER_THAN_BUDGET)
        elif used + cost > budget:
            skip(item.center, ChunkRole.CENTER, SkipReason.BUDGET_EXHAUSTED)
        else:
            take(item.center, ChunkRole.CENTER)
            centers.append(item)
    for item in centers:
        for neighbor, role in _candidates(item):
            if neighbor.chunk_id in taken:
                continue
            if used + tokens(neighbor) > budget:
                skip(neighbor, role, SkipReason.BUDGET_EXHAUSTED)
                continue
            take(neighbor, role)

    blocks = _blocks(taken, {i.center.chunk_id for i in centers}, rank_of)
    return blocks, tuple(skipped.values()), used


def _blocks(
    taken: dict[int, tuple[ContextNeighbor, ChunkRole, int]], centers: set[int], rank_of: dict[int, int]
) -> tuple[ContextBlock, ...]:
    by_doc: dict[int, list[tuple[ContextNeighbor, ChunkRole, int]]] = {}
    for entry in taken.values():
        by_doc.setdefault(entry[0].artifact_id, []).append(entry)
    drafts = []
    for artifact_id, entries in by_doc.items():
        entries.sort(key=lambda e: e[0].ordinal)
        chunks = tuple(
            ContextChunk(
                chunk_id=n.chunk_id,
                artifact_id=artifact_id,
                ordinal=n.ordinal,
                role=role,
                heading_path=n.provenance.heading_path,
                locator=n.provenance.locator,
                body=n.body,
                estimated_tokens=cost,
            )
            for n, role, cost in entries
        )
        doc_centers = tuple(sorted(((c.chunk_id, rank_of[c.chunk_id]) for c in chunks if c.chunk_id in centers),
                                   key=lambda p: p[1]))  # fmt: skip
        ordinals = [c.ordinal for c in chunks]
        gaps = tuple((a, b) for a, b in zip(ordinals, ordinals[1:], strict=False) if b != a + 1)
        first = entries[0][0].provenance
        drafts.append((min(rank for _, rank in doc_centers), artifact_id, chunks, doc_centers, gaps, first))
    drafts.sort(key=lambda d: (d[0], d[1]))
    return tuple(
        ContextBlock(
            source_id=f"S{index}",
            rank=rank,
            artifact_id=artifact_id,
            source_url=prov.source_url,
            source_version=prov.source_version,
            source_modified_at=prov.source_modified_at,
            collected_at=prov.collected_at,
            chunks=chunks,
            centers=doc_centers,
            gaps=gaps,
        )
        for index, (rank, artifact_id, chunks, doc_centers, gaps, prov) in enumerate(drafts, start=1)
    )
