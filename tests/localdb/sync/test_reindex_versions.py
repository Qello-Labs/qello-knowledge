"""재색인 대상 버전 바뀜과 재사용(QK-STO-002 US1-7·US1-8, FR-009, FR-002, research R-06)."""

import psycopg
import pytest

from qello_knowledge.adapters.postgres.index_versions import PostgresIndexVersionStore
from qello_knowledge.adapters.postgres.sync_store import PostgresSyncStore
from qello_knowledge.domain.chunking import ChunkingSettings
from qello_knowledge.sync.activate import activate_first_index
from qello_knowledge.sync.run import SyncOptions, current_spec, run_sync
from tests.unit.sync.helpers import harness
from tests.unit.sync.reindex_fakes import DOCS, NEW_CHUNKING

pytestmark = pytest.mark.localdb

THIRD = ChunkingSettings(target_tokens=300)


def _status(db_url):
    with psycopg.connect(db_url) as conn:
        return dict(conn.execute("SELECT id, status FROM qk.index_version").fetchall())


def test_candidate_follows_current_settings_and_old_ready_stays(db_url, store):
    with PostgresSyncStore(db_url) as sync_store:
        first = harness(DOCS, store=sync_store, cache_store=store)
        run_sync(first.targets, first.deps, SyncOptions())
        v1 = current_spec(first.deps).id
        sync_store.current_version = v1
        activate_first_index(sync_store, v1)
        h2 = harness(DOCS, store=sync_store, cache_store=store, chunking=NEW_CHUNKING)
        v2 = current_spec(h2.deps).id
        run_sync(h2.targets, h2.deps, SyncOptions(reindex=True))
        h3 = harness(DOCS, store=sync_store, cache_store=store, chunking=THIRD)
        v3 = current_spec(h3.deps).id
        result = run_sync(h3.targets, h3.deps, SyncOptions(reindex=True))
        assert result.summary["reindex"]["candidate"] == v3
    assert _status(db_url) == {v1: "active", v2: "ready", v3: "ready"}
    with PostgresIndexVersionStore(db_url, current_version=v3) as versions:
        assert versions.coverage(v3).covered == len(DOCS)
        assert versions.coverage(v2).covered == 0  # 문서 처리 상태는 버전 하나만 저장한다(FR-025)


def test_archived_version_is_reused_and_keeps_history(db_url, store):
    with PostgresSyncStore(db_url, target="remote") as sync_store:
        first = harness(DOCS, store=sync_store, cache_store=store)
        run_sync(first.targets, first.deps, SyncOptions())
        v1 = current_spec(first.deps).id
        sync_store.current_version = v1
        activate_first_index(sync_store, v1)
        v2 = current_spec(harness(DOCS, store=sync_store, cache_store=store, chunking=NEW_CHUNKING).deps).id
        with psycopg.connect(db_url, autocommit=True) as conn:
            conn.execute(
                "INSERT INTO qk.index_version(id,embedding_model,dimension,chunking_version,metadata_schema_version,"
                "status,pruned_at) VALUES (%s,'@cf/baai/bge-m3',1024,'old','meta-v1','archived',now())",
                (v2,),
            )
            conn.execute(
                "INSERT INTO qk.index_transition(kind,version,before_active,after_active,documents,chunks,target,"
                "gate_record_id,gate_record_sha256,deleted_chunks) VALUES "
                "('activation',%s,%s,%s,0,0,'local','gate-x',%s,NULL),('prune',%s,%s,%s,0,0,'local',NULL,NULL,0)",
                (v2, v1, v2, "a" * 64, v2, v1, v1),
            )
        h2 = harness(DOCS, store=sync_store, cache_store=store, chunking=NEW_CHUNKING)
        result = run_sync(h2.targets, h2.deps, SyncOptions(reindex=True, target="remote"))
        assert result.status == "succeeded"
    with psycopg.connect(db_url) as conn:
        assert conn.execute("SELECT status, pruned_at FROM qk.index_version WHERE id=%s", (v2,)).fetchone() == (
            "ready",
            None,
        )
        reuse = conn.execute(
            "SELECT before_active, after_active, target FROM qk.index_transition WHERE kind='reuse' AND version=%s",
            (v2,),
        ).fetchall()
    assert reuse == [(v1, v1, "remote")]
    with PostgresIndexVersionStore(db_url, current_version=v2) as versions:
        row = next(r for r in versions.versions() if r.id == v2)
        assert row.ever_active and row.last_reindex.status == "succeeded"
