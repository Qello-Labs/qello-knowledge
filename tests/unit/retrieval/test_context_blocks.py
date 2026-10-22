"""문서별 문맥 묶음(spec FR-013·FR-015, US3, tasks T025). 예산은 넉넉하게 둔다."""

from __future__ import annotations

from qello_knowledge.domain.retrieval import ChunkRole, RetrievalSettings
from qello_knowledge.retrieval import fuse, pack
from tests.unit.retrieval.fakes import document_context, keyword_result, vector_result

WIDE = RetrievalSettings(context_budget=8000, expand_top=20)


def _pack(vector_ids, layout, sections=None, settings=WIDE):
    hits = fuse(vector_result(*vector_ids), None, 60)
    lookup = document_context(layout, sections=sections)
    context = lookup([h.chunk_id for h in hits][: settings.expand_top], settings.before, settings.after)
    return pack(hits, context, settings)


def test_one_block_per_document_in_order_with_gaps() -> None:
    blocks, skipped, used = _pack([12, 13, 18], {1: list(range(10, 20))})
    assert len(blocks) == 1
    block = blocks[0]
    assert [c.chunk_id for c in block.chunks] == [11, 12, 13, 14, 17, 18, 19]
    assert [c.ordinal for c in block.chunks] == [1, 2, 3, 4, 7, 8, 9]
    assert block.gaps == ((4, 7),)
    assert block.centers == ((12, 1), (13, 2), (18, 3))
    assert block.rank == 1 and block.source_id == "S1"
    assert used == block.estimated_tokens and skipped == ()


def test_shared_neighbors_appear_once() -> None:
    blocks, _, _ = _pack([12, 14], {1: list(range(10, 17))})
    ids = [c.chunk_id for c in blocks[0].chunks]
    assert ids == sorted(set(ids)) and ids.count(13) == 1


def test_blocks_ordered_by_best_center_rank_with_source_ids() -> None:
    blocks, _, _ = _pack([21, 11, 22], {1: [10, 11, 12], 2: [20, 21, 22, 23]})
    assert [(b.artifact_id, b.rank, b.source_id) for b in blocks] == [(2, 1, "S1"), (1, 2, "S2")]


def test_section_first_is_added_once_and_not_duplicated_when_center() -> None:
    blocks, _, _ = _pack([15, 12], {1: list(range(10, 20))}, sections={15: 12, 12: 12})
    roles = {c.chunk_id: c.role for c in blocks[0].chunks}
    assert roles[12] is ChunkRole.CENTER and roles[15] is ChunkRole.CENTER
    assert list(roles).count(12) == 1


def test_block_carries_document_and_chunk_provenance() -> None:
    blocks, _, _ = _pack([11], {7: [10, 11, 12]})
    block = blocks[0]
    assert block.source_url.endswith("doc-7") and block.source_version == "sha-7"
    assert block.collected_at is not None and block.source_modified_at is None
    assert all(c.locator["path"] == "docs/doc-7.md" for c in block.chunks)
    assert {c.role for c in block.chunks} == {ChunkRole.BEFORE, ChunkRole.CENTER, ChunkRole.AFTER}


def test_keyword_only_hits_also_expand() -> None:
    hits = fuse(None, keyword_result((11, 2)), 60)
    context = document_context({1: [10, 11, 12]})([11], 1, 1)
    blocks, _, _ = pack(hits, context, WIDE)
    assert [c.chunk_id for c in blocks[0].chunks] == [10, 11, 12]


def test_repeatable() -> None:
    first = _pack([12, 18], {1: list(range(10, 20))})
    assert first == _pack([12, 18], {1: list(range(10, 20))})
