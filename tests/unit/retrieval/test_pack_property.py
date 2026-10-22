"""담기 알고리즘의 성질(spec SC-003, tasks T032). 고정 시드 무작위 100개 경우."""

from __future__ import annotations

import random

from qello_knowledge.domain.retrieval import ChunkRole, RetrievalSettings, SkipReason
from qello_knowledge.retrieval import fuse, pack
from tests.unit.retrieval.fakes import document_context, vector_result


def _case(seed: int):
    rng = random.Random(seed)  # noqa: S311 - 재현 가능한 합성 데이터용이다
    layout, sizes, next_id = {}, {}, 1
    for doc in range(1, rng.randint(1, 4) + 1):
        ids = list(range(next_id, next_id + rng.randint(1, 8)))
        next_id += len(ids)
        layout[doc] = ids
        sizes.update({cid: rng.randint(1, 120) for cid in ids})
    all_ids = [cid for ids in layout.values() for cid in ids]
    centers = rng.sample(all_ids, rng.randint(1, min(8, len(all_ids))))
    settings = RetrievalSettings(
        context_budget=rng.randint(1, 400), bytes_per_token=1.0, expand_top=20, before=rng.randint(0, 3),
        after=rng.randint(0, 3),
    )  # fmt: skip
    hits = fuse(vector_result(*centers), None, 60)
    bodies = {cid: "a" * size for cid, size in sizes.items()}
    context = document_context(layout, bodies=bodies)(centers, settings.before, settings.after)
    return settings, hits, pack(hits, context, settings), sizes


def test_invariants_hold_for_random_cases() -> None:
    for seed in range(100):
        settings, hits, (blocks, skipped, used), sizes = _case(seed)
        taken = [c for b in blocks for c in b.chunks]
        ids = [c.chunk_id for c in taken]
        assert used <= settings.context_budget, seed
        assert len(ids) == len(set(ids)), seed
        assert all(c.estimated_tokens == sizes[c.chunk_id] for c in taken), seed  # 잘린 청크 없음
        assert set(ids).isdisjoint(s.chunk_id for s in skipped), seed
        # 중심은 순위 순서로 먼저 담긴다: 빠진 중심은 그보다 순위가 높은 담긴 중심들 다음에 정말 들어가지 않았어야 한다
        rank = {h.chunk_id: h.rank for h in hits}
        taken_centers = [c for c in taken if c.role is ChunkRole.CENTER]
        for s in skipped:
            if s.role is not ChunkRole.CENTER:
                continue
            size = sizes[s.chunk_id]
            if s.reason is SkipReason.LARGER_THAN_BUDGET:
                assert size > settings.context_budget, seed
            else:
                ahead = sum(sizes[c.chunk_id] for c in taken_centers if rank[c.chunk_id] < rank[s.chunk_id])
                assert ahead + size > settings.context_budget, seed
