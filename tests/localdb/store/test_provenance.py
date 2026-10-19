"""US1: 모든 청크를 원본 위치로 되돌릴 수 있게 저장한다(SC-001, FR-001~005)."""

from __future__ import annotations

import psycopg
import pytest

from qello_knowledge.adapters.postgres.store import PostgresStore
from qello_knowledge.domain.store import EmbeddingRef, InvalidRecord
from tests.localdb.store.builders import ACTIVE, MODEL, artifact, chunk, document, vec

pytestmark = pytest.mark.localdb


def test_every_chunk_traces_back_to_its_source(store: PostgresStore, db_url: str) -> None:
    document(store, "docs/a.md", [f"본문 {i}" for i in range(5)], vector=vec(1))
    document(store, "docs/b.md", ["다른 문서"], vector=vec(2))
    with psycopg.connect(db_url) as conn:
        ids = [row[0] for row in conn.execute("SELECT id FROM qk.chunk ORDER BY id").fetchall()]
    assert len(ids) == 6

    for chunk_id in ids:  # 표본이 아니라 전부 확인한다(SC-001 100%)
        trace = store.trace_chunk(chunk_id)
        assert trace is not None
        assert trace.provenance.source_url.startswith("https://example.invalid/github/docs/")
        assert trace.provenance.source_version == "sha-1"
        assert trace.provenance.locator["path"] == "docs/sample.md"
        assert trace.chunking_version == "chunk-v1"
        assert trace.index_version == ACTIVE
        assert trace.embedding_model == MODEL


def test_chunk_without_locator_is_rejected(store: PostgresStore) -> None:
    artifact_id = artifact(store, "docs/a.md")
    with pytest.raises(InvalidRecord):
        store.replace_chunks(artifact_id, ACTIVE, "sha-1", [chunk(0, "본문", locator={})])


def test_database_rejects_missing_provenance_even_without_the_adapter(store: PostgresStore, db_url: str) -> None:
    artifact_id = artifact(store, "docs/a.md")
    with psycopg.connect(db_url) as conn:
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                "INSERT INTO qk.chunk (artifact_id, index_version, source_version, locator, ordinal, body,"
                " search_text, chunking_version) VALUES (%s, %s, '', '{\"path\": \"a\"}', 0, 'b', 'b', 'c')",
                (artifact_id, ACTIVE),
            )
        conn.rollback()
        with pytest.raises(psycopg.errors.CheckViolation):
            conn.execute(
                "INSERT INTO qk.artifact (source_kind, source_id, source_url, source_version, collected_at,"
                " content_hash, artifact_kind) VALUES ('github', 'x', '', 'sha', now(), 'h', 'markdown')"
            )


def test_vector_with_wrong_dimension_is_rejected(store: PostgresStore, db_url: str) -> None:
    with pytest.raises(InvalidRecord):
        store.put_embedding(EmbeddingRef("h", MODEL), [0.1, 0.2, 0.3])
    with psycopg.connect(db_url) as conn, pytest.raises(psycopg.errors.DataException):
        conn.execute("INSERT INTO qk.embedding (input_hash, model_version, vector) VALUES ('h', 'm', '[1,2,3]')")


def test_second_active_index_version_is_rejected(db_url: str) -> None:
    with psycopg.connect(db_url) as conn, pytest.raises(psycopg.errors.UniqueViolation):
        conn.execute(
            "INSERT INTO qk.index_version (id, embedding_model, dimension, chunking_version,"
            " metadata_schema_version, status) VALUES ('v2', 'm', 1024, 'c', 'm', 'active')"
        )
