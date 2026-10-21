from dataclasses import replace
from datetime import UTC, datetime

import psycopg
import pytest

from qello_knowledge.domain.store import ArtifactRecord, ChunkInput, EmbeddingRef, InvalidRecord
from qello_knowledge.domain.sync import Action, DocumentDecision, DocumentOutcome
from qello_knowledge.ports.sync import ArtifactWrite, IndexSpec, RunInfo

pytestmark = pytest.mark.localdb
SPEC = IndexSpec("iv-test", "@cf/baai/bge-m3", 1024, "chk-test")
NOW = datetime(2026, 10, 21, tzinfo=UTC)


def begin(sync_store, run="run-1"):
    sync_store.ensure_index_version(SPEC)
    sync_store.begin_run(RunInfo(run, "manual", "local", "sec", "chk-test", "iv-test", ("fake",)), ["docs"])


def inputs():
    doc = DocumentDecision(
        doc_key="a" * 64, display="sample", actions=(Action.PROCESS,), source_id="opaque", source_name="docs"
    )
    record = ArtifactRecord(
        "fake", "opaque", "https://example.invalid/sample", "v1", NOW, "hash", "markdown", access_scope="team"
    )
    write = ArtifactWrite(record, "docs", "docs/sample.md", "fingerprint", "chk-test", "chunked")
    chunks = [ChunkInput(0, {"path": "docs/sample.md"}, "Synthetic", "Synthetic", "chk-test")]
    return doc, write, chunks


def test_ensure_index_and_load_without_body(sync_store):
    assert sync_store.ensure_index_version(SPEC) == "iv-test"
    assert sync_store.ensure_index_version(SPEC) == "iv-test"
    assert sync_store.index_state().active is None
    assert sync_store.index_state().ready == ("iv-test",)
    begin(sync_store)
    doc, write, chunks = inputs()
    identity = sync_store.apply_document("run-1", doc, write, "iv-test", chunks)
    row = sync_store.load_documents("fake")["opaque"]
    assert row.artifact_id == identity and row.location == "docs/sample.md"
    assert row.chunk_input_hash == "fingerprint" and row.processed_index_version == "iv-test"
    assert row.access_scope == "team" and row.status == "active"
    assert not hasattr(row, "body")


def test_apply_rolls_back_artifact_chunks_and_result(sync_store, db_url):
    begin(sync_store)
    doc, write, chunks = inputs()
    broken = replace(chunks[0], embedding=EmbeddingRef("missing", "@cf/baai/bge-m3"))
    with pytest.raises(InvalidRecord):
        sync_store.apply_document("run-1", doc, write, "iv-test", [broken])
    assert sync_store.load_documents("fake") == {}
    with psycopg.connect(db_url) as conn:
        assert conn.execute("SELECT count(*) FROM qk.sync_document_result").fetchone() == (0,)
        assert conn.execute("SELECT count(*) FROM qk.chunk").fetchone() == (0,)


def test_mark_seen_preserves_processed_provenance_and_records_outcomes(sync_store, db_url):
    begin(sync_store)
    doc, write, chunks = inputs()
    identity = sync_store.apply_document("run-1", doc, write, "iv-test", chunks)
    seen = replace(doc, artifact_id=identity, actions=(Action.UNCHANGED,))
    sync_store.mark_seen("run-1", [seen], "v2", NOW)
    row = sync_store.load_documents("fake")["opaque"]
    assert row.source_version == "v1" and row.last_seen_version == "v2"
    failed = replace(doc, doc_key="b" * 64, actions=(Action.FAIL,), stage="embed", failure="input_too_long")
    sync_store.record_outcome("run-1", failed, Action.FAIL, DocumentOutcome.FAILED)
    sync_store.finish_source("run-1", "docs", "partial", {"counts": {"FAIL": 1}})
    sync_store.finish_run("run-1", "partial", {"failures": 1})
    with psycopg.connect(db_url) as conn:
        assert conn.execute("SELECT count(*) FROM qk.sync_document_result").fetchone() == (3,)
        assert conn.execute("SELECT status, finished_at IS NOT NULL FROM qk.sync_run").fetchone() == ("partial", True)


def test_sync_write_keeps_existing_store_idempotency_hash_consistent(sync_store, store):
    begin(sync_store)
    doc, write, chunks = inputs()
    identity = store.upsert_artifact(write.record)
    assert store.replace_chunks(identity, "iv-test", "v1", chunks) == "replaced"
    changed = [replace(chunks[0], body="Synthetic changed", search_text="Synthetic changed")]
    sync_store.apply_document("run-1", doc, write, "iv-test", changed)
    assert store.replace_chunks(identity, "iv-test", "v1", changed) == "unchanged"
    assert store.replace_chunks(identity, "iv-test", "v1", chunks) == "replaced"
