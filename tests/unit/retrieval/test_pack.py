"""토큰 예산 담기 알고리즘(spec FR-016, SC-003, US4, contracts/retrieval.md 4절, tasks T031).

`bytes_per_token=1.0`과 ASCII 본문을 써서 예상 토큰 = 본문 길이가 되게 한다.
"""

from __future__ import annotations

from qello_knowledge.domain.retrieval import ChunkRole, RetrievalSettings, SkipReason
from qello_knowledge.retrieval import estimated_tokens, fuse, pack
from tests.unit.retrieval.fakes import document_context, vector_result


def _settings(budget: int, **kwargs) -> RetrievalSettings:
    return RetrievalSettings(context_budget=budget, bytes_per_token=1.0, expand_top=20, **kwargs)


def _run(centers, layout, sizes, budget, sections=None, **kwargs):
    settings = _settings(budget, **kwargs)
    hits = fuse(vector_result(*centers), None, 60)
    bodies = {cid: "a" * size for cid, size in sizes.items()}
    context = document_context(layout, bodies=bodies, sections=sections)(centers, settings.before, settings.after)
    return pack(hits, context, settings)


def _taken(blocks) -> list[int]:
    return [c.chunk_id for b in blocks for c in b.chunks]


def test_everything_fits() -> None:
    blocks, skipped, used = _run([2], {1: [1, 2, 3]}, {1: 10, 2: 10, 3: 10}, budget=100)
    assert _taken(blocks) == [1, 2, 3] and skipped == () and used == 30


def test_center_larger_than_budget_is_skipped_and_next_center_continues() -> None:
    blocks, skipped, used = _run([1, 5], {1: [1], 2: [5]}, {1: 101, 5: 20}, budget=100)
    assert _taken(blocks) == [5] and used == 20
    assert [(s.chunk_id, s.role, s.reason) for s in skipped] == [(1, ChunkRole.CENTER, SkipReason.LARGER_THAN_BUDGET)]


def test_budget_exhausted_center_is_skipped_and_smaller_later_center_is_taken() -> None:
    blocks, skipped, used = _run([1, 2, 3], {1: [1], 2: [2], 3: [3]}, {1: 60, 2: 50, 3: 30}, budget=100)
    assert sorted(_taken(blocks)) == [1, 3] and used == 90
    assert [(s.chunk_id, s.reason) for s in skipped] == [(2, SkipReason.BUDGET_EXHAUSTED)]


def test_all_centers_come_before_any_neighbor() -> None:
    # 1위 중심의 이웃(40)을 먼저 담으면 2위 중심(40)이 들어가지 못한다. 중심을 먼저 담아야 한다.
    blocks, skipped, _ = _run([11, 21], {1: [10, 11, 12], 2: [21]}, {10: 40, 11: 10, 12: 40, 21: 40}, budget=100)
    assert set(_taken(blocks)) == {11, 21, 10}
    assert [(s.chunk_id, s.role, s.reason) for s in skipped] == [(12, ChunkRole.AFTER, SkipReason.BUDGET_EXHAUSTED)]


def test_neighbor_order_section_first_then_nearest_before_then_after() -> None:
    layout = {1: [10, 11, 12, 13, 14, 15, 16]}
    sizes = {cid: 10 for cid in layout[1]}
    # 중심 14, 절 첫 청크 10, 앞 13·12, 뒤 15·16. 예산 40이면 중심 + 절 첫 + 가까운 앞 + 다음 앞까지.
    blocks, skipped, _ = _run([14], layout, sizes, budget=40, sections={14: 10}, before=2, after=2)
    assert _taken(blocks) == [10, 12, 13, 14]
    assert [(s.chunk_id, s.role) for s in skipped] == [(15, ChunkRole.AFTER), (16, ChunkRole.AFTER)]
    roles = {c.chunk_id: c.role for c in blocks[0].chunks}
    assert roles[10] is ChunkRole.SECTION_FIRST and roles[13] is ChunkRole.BEFORE


def test_skipping_continues_to_smaller_candidates() -> None:
    blocks, skipped, _ = _run([12], {1: [11, 12, 13]}, {11: 80, 12: 10, 13: 5}, budget=30)
    assert _taken(blocks) == [12, 13]
    assert [(s.chunk_id, s.reason) for s in skipped] == [(11, SkipReason.BUDGET_EXHAUSTED)]


def test_same_chunk_is_recorded_once_in_skipped() -> None:
    # 13은 12의 뒤이자 14의 앞이다. 두 번 건너뛰어도 한 번만 남고, 처음 역할을 쓴다.
    _, skipped, _ = _run([12, 14], {1: [11, 12, 13, 14]}, {11: 1, 12: 10, 13: 90, 14: 10}, budget=30)
    assert [(s.chunk_id, s.role) for s in skipped if s.chunk_id == 13] == [(13, ChunkRole.AFTER)]


def test_no_chunk_is_cut_and_total_within_budget() -> None:
    blocks, _, used = _run([2, 5], {1: [1, 2, 3], 2: [4, 5, 6]}, {i: 17 for i in range(1, 7)}, budget=50)
    assert used <= 50 and all(c.estimated_tokens == 17 for b in blocks for c in b.chunks)
    assert used == sum(b.estimated_tokens for b in blocks)


def test_repeatable() -> None:
    args = ([2, 5], {1: [1, 2, 3], 2: [4, 5, 6]}, {i: 17 for i in range(1, 7)}, 50)
    assert _run(*args) == _run(*args)


def test_estimated_tokens_uses_bytes_per_token() -> None:
    assert estimated_tokens("가나다", 3.5) == 3  # 9바이트 ÷ 3.5 올림
    assert estimated_tokens("abcd", 1.0) == 4
    assert estimated_tokens("", 3.5) == 0
