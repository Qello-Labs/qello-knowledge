"""버전 저장소 읽기(QK-STO-002 research R-04·R-12·R-17, data-model 2.3). 행은 SQL로 직접 넣는다."""

from datetime import UTC, datetime, timedelta

import psycopg
import pytest

from qello_knowledge.adapters.postgres.index_versions import PostgresIndexVersionStore

pytestmark = pytest.mark.localdb

V1, V2 = "iv-store-1", "iv-store-2"
T0 = datetime(2026, 11, 1, tzinfo=UTC)


def _version(conn, vid, status, activated=None):
    conn.execute(
        "INSERT INTO qk.index_version(id,embedding_model,dimension,chunking_version,metadata_schema_version,status,"
        "created_at,activated_at) VALUES (%s,'m',1024,'c','meta-v1',%s,%s,%s)",
        (vid, status, T0, activated),
    )


def _artifact(conn, name, *, processed=None, outcome="chunked", status="active", scope="team", purge=()):
    return conn.execute(
        "INSERT INTO qk.artifact(source_kind,source_id,source_url,source_version,collected_at,content_hash,"
        "artifact_kind,access_scope,status,processed_index_version,processed_outcome,purge_pending,purge_reason) "
        "VALUES ('fake',%s,%s,'rev',%s,'h','markdown',%s,%s,%s,%s,%s,%s) RETURNING id",
        (
            name,
            f"https://example.invalid/{name}",
            T0,
            scope,
            status,
            processed,
            outcome if processed else None,
            list(purge),
            "security_secret" if purge else None,
        ),
    ).fetchone()[0]


def _chunk(conn, artifact_id, version, ordinal=0, embedded=True):
    embedding = None
    if embedded:
        embedding = conn.execute(
            "INSERT INTO qk.embedding(input_hash,model_version,vector) VALUES (%s,'m',%s::vector) RETURNING id",
            (f"{artifact_id}-{version}-{ordinal}", "[" + ",".join(["0.01"] * 1024) + "]"),
        ).fetchone()[0]
    conn.execute(
        "INSERT INTO qk.chunk(artifact_id,index_version,source_version,locator,ordinal,body,search_text,"
        "chunking_version,embedding_id) VALUES (%s,%s,'rev','{\"p\":1}',%s,'b','b','c',%s)",
        (artifact_id, version, ordinal, embedding),
    )


def _run(conn, run_id, version, *, kind="reindex", status="succeeded", started=T0):
    conn.execute(
        "INSERT INTO qk.sync_run(run_id,trigger,target,rules_version,chunking_version,index_version,status,kind,"
        "started_at,finished_at) VALUES (%s,'manual','local','r','c',%s,%s,%s,%s,%s)",
        (run_id, version, status, kind, started, started + timedelta(minutes=1)),
    )


def _result(conn, run_id, artifact_id, outcome, display, stage=None):
    conn.execute(
        "INSERT INTO qk.sync_document_result(run_id,doc_key,action,source_name,doc_display,artifact_id,outcome,stage)"
        " VALUES (%s,%s,'PROCESS','fake',%s,%s,%s,%s)",
        (run_id, f"k-{artifact_id}", display, artifact_id, outcome, stage),
    )


@pytest.fixture
def seeded(db_url):
    with psycopg.connect(db_url, autocommit=True) as conn:
        _version(conn, V1, "active", T0)
        _version(conn, V2, "ready")
        conn.execute(
            "INSERT INTO qk.index_transition(kind,at,version,after_active,documents,chunks,target) "
            "VALUES ('first_activation',%s,%s,%s,0,0,'local')",
            (T0, V1, V1),
        )
        ids = {}
        ids["covered"] = _artifact(conn, "covered", processed=V2)
        ids["empty"] = _artifact(conn, "empty", processed=V2, outcome="empty")
        ids["not_target"] = _artifact(conn, "not-target", processed=V2, outcome="not_target")
        ids["remaining"] = _artifact(conn, "remaining", processed=V1)
        ids["failed_after_cover"] = _artifact(conn, "failed-after-cover", processed=V2)
        ids["hidden"] = _artifact(conn, "hidden", processed=V1, status="deleted", purge=(V2,))
        ids["new"] = _artifact(conn, "new", processed=V2)
        for name in ("covered", "empty", "not_target", "remaining", "failed_after_cover", "hidden"):
            _chunk(conn, ids[name], V1)
        _chunk(conn, ids["covered"], V2)
        _chunk(conn, ids["new"], V2, embedded=False)
        _run(conn, "sync-old", V2, started=T0 + timedelta(hours=1))
        _result(conn, "sync-old", ids["remaining"], "FAILED", "docs/remaining.md", "chunk")
        _result(conn, "sync-old", ids["failed_after_cover"], "PROCESSED", "docs/failed-after-cover.md")
        _run(conn, "sync-new", V2, started=T0 + timedelta(hours=2))
        _result(conn, "sync-new", ids["failed_after_cover"], "FAILED", "docs/failed-after-cover.md", "embed")
        _run(conn, "sync-sched", V2, kind="sync", status="stopped", started=T0 + timedelta(minutes=30))
        conn.execute("INSERT INTO qk.sync_source(source_name,source_kind,scope_key) VALUES ('docs','fake','fake:')")
    with PostgresIndexVersionStore(db_url, current_version=V2, target="local") as store:
        yield store, ids


def test_coverage_counts_visible_active_documents(seeded):
    store, _ = seeded
    coverage = store.coverage(V2)
    assert (coverage.visible, coverage.covered, coverage.remaining) == (5, 4, 1)
    assert [(f.display, f.stage, f.run_id) for f in coverage.failed] == [
        ("docs/failed-after-cover.md", "embed", "sync-new"),
        ("docs/remaining.md", "chunk", "sync-old"),
    ]


def test_versions_rows(seeded):
    store, _ = seeded
    rows = {r.id: r for r in store.versions()}
    assert rows[V1].status == "active" and rows[V1].ever_active and rows[V1].documents == 5
    assert rows[V2].ever_active is False and rows[V2].documents == 2 and rows[V2].chunks == 2
    assert rows[V2].chunks_without_vector == 1
    assert rows[V2].last_reindex.run_id == "sync-new" and rows[V1].last_reindex is None


def test_mismatch_since_is_first_run_of_current_after_activation(seeded):
    store, _ = seeded
    assert store.mismatch_since(V1, V2) == T0 + timedelta(minutes=30)
    assert store.mismatch_since(V1, V1) is None


def test_activation_state_reads_tokenizer_purge_pending_and_sources(seeded):
    store, _ = seeded
    state = store.activation_state(V2)
    assert state.active.id == V1 and state.target.id == V2 and state.current == V2
    assert state.tokenizer == "TokenBigramSplitSymbol"
    assert state.purge_pending == 1
    assert [(s.name, s.kind) for s in state.sources] == [("docs", "fake")]
    assert state.sync_running is False
    assert store.activation_state(V1).purge_pending == 0


def test_rollback_and_prune_state(seeded, db_url):
    store, ids = seeded
    state = store.rollback_state(V2)
    assert state.missing_documents == 4  # 노출 문서 5개 가운데 V2 청크가 있는 것은 covered 하나
    assert state.provenance_mismatch == 0
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute("UPDATE qk.artifact SET source_version='rev-2' WHERE id=%s", (ids["covered"],))
    assert store.rollback_state(V2).provenance_mismatch == 1
    prune = store.prune_state(V2)
    assert prune.remaining_chunks == 2 and prune.active == V1 and prune.rollback_target is None
