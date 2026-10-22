"""검색 결과 타입의 불변식(data-model 2절, spec FR-008·FR-011·FR-013)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from qello_knowledge.domain.retrieval import (
    ChunkRole,
    ContextBlock,
    ContextChunk,
    RetrievalFailure,
    RetrievalRequest,
    RetrievalResult,
    RetrievalSummary,
)

COLLECTED = datetime(2026, 10, 22, tzinfo=UTC)
SECRET = "질문-원문-노출되면-안-됨"


def _chunk(chunk_id: int, ordinal: int, artifact_id: int = 1, body: str = "본문") -> ContextChunk:
    return ContextChunk(
        chunk_id=chunk_id,
        artifact_id=artifact_id,
        ordinal=ordinal,
        role=ChunkRole.CENTER,
        heading_path=("제목",),
        locator={"path": "docs/a.md"},
        body=body,
        estimated_tokens=1,
    )


def _block(chunks: tuple[ContextChunk, ...]) -> ContextBlock:
    return ContextBlock(
        source_id="S1",
        rank=1,
        artifact_id=1,
        source_url="https://example.invalid/a",
        source_version="sha",
        source_modified_at=None,
        collected_at=COLLECTED,
        chunks=chunks,
        centers=((chunks[0].chunk_id, 1),),
        gaps=(),
    )


def test_failure_kinds_match_spec_fr011() -> None:
    assert {f.value for f in RetrievalFailure} == {
        "empty_question",
        "question_too_long",
        "no_active_index",
        "store_unavailable",
        "index_version_changed",
        "query_embedding_failed",
        "outgoing_blocked",
        "keyword_search_failed",
        "both_searches_failed",
    }


def test_block_rejects_duplicate_chunk() -> None:
    with pytest.raises(ValueError):
        _block((_chunk(1, 0), _chunk(1, 1)))


def test_block_rejects_other_artifact() -> None:
    with pytest.raises(ValueError):
        _block((_chunk(1, 0), _chunk(2, 1, artifact_id=2)))


def test_block_rejects_unsorted_ordinals() -> None:
    with pytest.raises(ValueError):
        _block((_chunk(1, 3), _chunk(2, 1)))


def test_block_tokens_and_text() -> None:
    block = _block((_chunk(1, 0, body="가"), _chunk(2, 1, body="나")))
    assert block.estimated_tokens == 2
    assert block.text == "가\n\n나"


def test_question_and_bodies_are_hidden_from_repr() -> None:
    request = RetrievalRequest(question=SECRET)
    chunk = _chunk(1, 0, body=SECRET)
    result = RetrievalResult(status="ok", context=(_block((chunk,)),), summary=RetrievalSummary())
    for value in (request, chunk, result):
        assert SECRET not in repr(value)


def test_result_failure_property() -> None:
    assert RetrievalResult(status="ok").failure is None
    assert RetrievalResult(status="no_results").failure is None
    assert RetrievalResult(status="store_unavailable").failure is RetrievalFailure.STORE_UNAVAILABLE
