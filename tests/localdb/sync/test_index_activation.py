"""활성화(QK-STO-002 SC-002 활성화, US3-1~US3-4, FR-021). 조건마다 그것 하나만 어긴 사례에서 상태가 그대로다."""

import psycopg
import pytest

from qello_knowledge.sync.run import SyncOptions, run_sync
from tests.localdb.sync.version_setup import DOCS, NEW_CHUNKING, activate, prepare, state, verified, verifier
from tests.unit.indexer.index_fakes import BODY, DB_URL
from tests.unit.sync.helpers import harness

pytestmark = pytest.mark.localdb


@pytest.fixture
def ready(db_url, sync_store, store, monkeypatch):
    return prepare(sync_store, store, monkeypatch)


def _sql(db_url, statement, params=()):
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(statement, params)


def _break(name, db_url, sync_store, ready, monkeypatch):
    """조건 하나만 어기게 만들고 게이트 대역을 돌려준다."""
    gate = None
    v2 = ready.v2
    if name == "current_version":
        sync_store.current_version = "iv-other-setting"
    elif name == "ready_version":
        _sql(db_url, "UPDATE qk.index_version SET status='archived' WHERE id=%s", (v2,))
    elif name == "last_reindex":
        _sql(db_url, "UPDATE qk.sync_run SET status='partial' WHERE run_id=%s", (ready.run_id,))
    elif name == "coverage":
        _sql(db_url, "UPDATE qk.artifact SET processed_index_version=NULL WHERE source_id='A'")
    elif name == "failed_documents":
        _sql(
            db_url,
            "UPDATE qk.sync_document_result SET outcome='FAILED', stage='embed' WHERE run_id=%s AND artifact_id="
            "(SELECT id FROM qk.artifact WHERE source_id='A')",
            (ready.run_id,),
        )
    elif name == "missing_vectors":
        _sql(
            db_url,
            "UPDATE qk.chunk SET embedding_id=NULL WHERE id=(SELECT min(id) FROM qk.chunk WHERE index_version=%s)",
            (v2,),
        )
    elif name == "visible_documents":
        _sql(db_url, "DELETE FROM qk.chunk WHERE index_version=%s", (v2,))
    elif name == "gate_verdict":
        gate = verifier(failed=("gate_verdict",))
    elif name == "keyword_rule":
        from types import MappingProxyType

        from qello_knowledge.domain import keyword_rules

        rules = {k: v for k, v in keyword_rules.INDEX_KEYWORD_RULES.items() if k != v2}
        monkeypatch.setattr(keyword_rules, "INDEX_KEYWORD_RULES", MappingProxyType(rules))
    elif name == "tokenizer":
        gate = verifier(verified(candidate_tokenizer="TokenBigramSplitSymbolAlpha"))
    elif name == "retrieval_settings":
        gate = verifier(verified(search={"query_rule": "kw-query-v1", "candidates": 30, "rrf_k": 60}))
    elif name == "purge_pending":
        _sql(
            db_url,
            "UPDATE qk.artifact SET purge_pending=ARRAY[%s], purge_reason='security_secret' WHERE source_id='B'",
            (v2,),
        )
    elif name == "sync_running":
        _sql(
            db_url,
            "INSERT INTO qk.sync_run(run_id,trigger,target,rules_version,chunking_version,index_version,status) "
            "VALUES ('sync-running','schedule','local','r','c','iv-x','running')",
        )
    return gate


CONDITIONS = [
    "current_version",
    "ready_version",
    "last_reindex",
    "coverage",
    "failed_documents",
    "missing_vectors",
    "visible_documents",
    "gate_verdict",
    "keyword_rule",
    "tokenizer",
    "retrieval_settings",
    "purge_pending",
    "sync_running",
]


@pytest.mark.parametrize("name", CONDITIONS)
def test_each_condition_alone_blocks_activation(name, db_url, sync_store, ready, monkeypatch):
    gate = _break(name, db_url, sync_store, ready, monkeypatch)
    before = state(db_url)
    code, value = activate(sync_store, ready.v2, gate=gate)
    assert code == (6 if name == "sync_running" else 1) and value["failed_conditions"] == [name]
    assert state(db_url) == before


def test_lock_held_by_sync_is_refused(db_url, sync_store, ready):
    before = state(db_url)
    with psycopg.connect(db_url, autocommit=True) as other:
        other.execute("SELECT pg_advisory_lock_shared(hashtext('qk-sync-index')::bigint)")
        code, value = activate(sync_store, ready.v2)
    assert code == 6 and value["failed_conditions"] == ["sync_running"]
    assert state(db_url) == before


def test_preview_values_match_database(db_url, sync_store, ready):
    code, value = activate(sync_store, ready.v2, confirm=False)
    assert code == 4 and value["applied"] is False
    with psycopg.connect(db_url) as conn:
        chunks = conn.execute("SELECT count(*) FROM qk.chunk WHERE index_version=%s", (ready.v2,)).fetchone()[0]
        sources = conn.execute("SELECT source_name, source_kind FROM qk.sync_source").fetchall()
    assert value["candidate"] == {
        "version": ready.v2,
        "documents": len(DOCS),
        "chunks": chunks,
        "chunks_without_vector": 0,
    }
    assert value["coverage"]["visible"] == value["coverage"]["covered"] == len(DOCS)
    assert value["failed_documents"] == 0 and value["purge_pending_documents"] == 0
    assert value["uncovered_sources"] == [{"name": n, "kind": k} for n, k in sources if n != "docs"]
    assert value["retrieval_settings"]["policy"] == value["retrieval_settings"]["code_defaults"]


def test_activation_switches_once_and_records_transition(db_url, sync_store, store, ready):
    code, value = activate(sync_store, ready.v2)
    assert code == 0 and value["applied"] is True
    statuses, _ = state(db_url)
    assert statuses == {ready.v1: "archived", ready.v2: "active"}
    with psycopg.connect(db_url) as conn:
        row = conn.execute(
            "SELECT kind, before_active, after_active, documents, chunks, gate_record_id, gate_record_sha256, details "
            "FROM qk.index_transition WHERE kind='activation'"
        ).fetchone()
    assert row[:3] == ("activation", ready.v1, ready.v2) and row[3] == len(DOCS)
    assert row[5:7] == ("gate-x", "a" * 64)
    assert row[7]["policy"] == {"id": "p", "version": 1} and "embedding_model" in row[7]
    text = str(row[7])
    assert BODY not in text and DB_URL not in text and "Text for" not in text  # SC-007
    assert store.search_keyword("Synthetic", 20).index_version == ready.v2
    # 활성화 뒤 예약 동기화는 불일치가 없어 바뀐 문서를 처리하고 일반 내림을 한다(US3-4).
    docs = {k: v for k, v in DOCS.items() if k != "J"}
    docs["C"] = "# Synthetic C\n\nChanged after activation.\n"
    scheduled = harness(docs, store=sync_store, cache_store=store, chunking=NEW_CHUNKING)
    result = run_sync(scheduled.targets, scheduled.deps, SyncOptions(trigger="schedule"))
    assert "INDEX_MISMATCH" not in result.sources[0]["holds"]
    assert result.sources[0]["counts"].get("PROCESS") == 1
    assert result.sources[0]["takedowns"] == {"source_missing": 1}
