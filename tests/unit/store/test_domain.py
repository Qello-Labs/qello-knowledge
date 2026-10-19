"""저장소 입력 검증(US1 AS2·AS3, FR-004·010)."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from qello_knowledge.domain.store import (
    ArtifactRecord,
    ChunkInput,
    InvalidRecord,
    chunk_set_hash,
    clamp_top_n,
    validate_artifact,
    validate_chunks,
    validate_vector,
)

RECORD = ArtifactRecord(
    source_kind="github",
    source_id="docs/a.md",
    source_url="https://example.invalid/a",
    source_version="sha-1",
    collected_at=datetime(2026, 10, 19, tzinfo=UTC),
    content_hash="h",
    artifact_kind="markdown",
)
CHUNK = ChunkInput(ordinal=0, locator={"path": "a.md"}, body="본문", search_text="본문", chunking_version="c1")


def test_valid_artifact_passes() -> None:
    validate_artifact(RECORD)


@pytest.mark.parametrize("field", ["source_url", "source_version", "source_id"])
@pytest.mark.parametrize("value", ["", "   "])
def test_artifact_without_provenance_is_rejected(field: str, value: str) -> None:
    with pytest.raises(InvalidRecord):
        validate_artifact(replace(RECORD, **{field: value}))


def test_chunk_without_locator_is_rejected() -> None:
    with pytest.raises(InvalidRecord):
        validate_chunks("sha-1", [replace(CHUNK, locator={})])


def test_chunk_without_source_version_is_rejected() -> None:
    with pytest.raises(InvalidRecord):
        validate_chunks(" ", [CHUNK])


def test_duplicate_or_negative_ordinal_is_rejected() -> None:
    with pytest.raises(InvalidRecord):
        validate_chunks("sha-1", [CHUNK, CHUNK])
    with pytest.raises(InvalidRecord):
        validate_chunks("sha-1", [replace(CHUNK, ordinal=-1)])


@pytest.mark.parametrize("size", [0, 3, 768, 1025])
def test_vector_with_wrong_dimension_is_rejected(size: int) -> None:
    with pytest.raises(InvalidRecord):
        validate_vector([0.0] * size)


def test_vector_with_1024_dimensions_passes() -> None:
    validate_vector([0.0] * 1024)


@pytest.mark.parametrize(("given", "expected"), [(0, 1), (20, 20), (50, 50), (500, 50)])
def test_top_n_is_clamped(given: int, expected: int) -> None:
    assert clamp_top_n(given) == expected


def test_chunk_set_hash_is_order_independent_and_version_sensitive() -> None:
    second = replace(CHUNK, ordinal=1, body="다음")
    assert chunk_set_hash("v1", "sha-1", [CHUNK, second]) == chunk_set_hash("v1", "sha-1", [second, CHUNK])
    assert chunk_set_hash("v1", "sha-1", [CHUNK]) != chunk_set_hash("v1", "sha-2", [CHUNK])
    assert chunk_set_hash("v1", "sha-1", [CHUNK]) != chunk_set_hash("v2", "sha-1", [CHUNK])
