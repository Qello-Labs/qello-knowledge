"""상태 보기(QK-STO-002 US5-1, FR-026, research R-17). 읽기 전용."""

import psycopg
import pytest

from qello_knowledge.indexer.index_cli import make_handler
from tests.localdb.sync.version_setup import prepare, verifier

pytestmark = pytest.mark.localdb

COUNTS = (
    "SELECT (SELECT count(*) FROM qk.index_version), (SELECT count(*) FROM qk.index_transition),"
    " (SELECT count(*) FROM qk.sync_run), (SELECT count(*) FROM qk.chunk), (SELECT count(*) FROM qk.artifact)"
)


def _counts(db_url):
    with psycopg.connect(db_url) as conn:
        return conn.execute(COUNTS).fetchone()


def _status(sync_store):
    from types import SimpleNamespace

    handler = make_handler(history_factory=lambda root: None, gate_verifier=verifier())
    return handler(SimpleNamespace(index_command="status"), sync_store, sync_store.current_version, "local")


def test_status_matches_database(db_url, sync_store, store, monkeypatch):
    ready = prepare(sync_store, store, monkeypatch)
    with psycopg.connect(db_url, autocommit=True) as conn:
        for vid, status in (("iv-ready-b", "ready"), ("iv-arch-a", "archived"), ("iv-arch-b", "archived")):
            conn.execute(
                "INSERT INTO qk.index_version(id,embedding_model,dimension,chunking_version,metadata_schema_version,"
                "status) VALUES (%s,'m',1024,'c','meta-v1',%s)",
                (vid, status),
            )
        conn.execute("UPDATE qk.index_version SET pruned_at=now() WHERE id='iv-arch-b'")
        conn.execute(
            "UPDATE qk.sync_document_result SET outcome='FAILED', stage='chunk' WHERE run_id=%s AND artifact_id="
            "(SELECT id FROM qk.artifact WHERE source_id='C')",
            (ready.run_id,),
        )
    before = _counts(db_url)
    code, value = _status(sync_store)
    assert code == 0 and _counts(db_url) == before
    assert (value["active"], value["current"], value["matches"]) == (ready.v1, ready.v2, False)
    assert value["mismatch_since"] is not None
    assert value["resolutions"] == ["reindex_gate_activate", "redeploy_active_settings"]
    assert value["coverage"]["covered"] == 10 and value["coverage"]["failed"][0]["stage"] == "chunk"
    rows = {v["id"]: v for v in value["versions"]}
    assert set(rows) == {ready.v1, ready.v2, "iv-ready-b", "iv-arch-a", "iv-arch-b"}
    assert rows[ready.v1]["status"] == "active" and rows[ready.v1]["ever_active"] is True
    assert rows[ready.v2]["coverage"]["covered"] == 10 and rows[ready.v2]["last_reindex"]["status"] == "succeeded"
    assert (
        rows["iv-ready-b"]["prune_candidate"] is True and rows["iv-ready-b"]["coverage_note"] == "not_current_version"
    )
    assert rows["iv-arch-a"]["prune_candidate"] is True and rows["iv-arch-b"]["prune_candidate"] is False
    with psycopg.connect(db_url) as conn:
        chunks = conn.execute("SELECT count(*) FROM qk.chunk WHERE index_version=%s", (ready.v2,)).fetchone()[0]
    assert rows[ready.v2]["chunks"] == chunks and rows[ready.v2]["documents"] == 10
