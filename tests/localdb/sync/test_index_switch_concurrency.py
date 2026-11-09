"""전환 중 동시 검색(QK-STO-002 SC-004, research R-08).

섞인 결과·활성 없음 0건이어야 하고, `index_version_changed` 수는 시험 기록에 남긴다.
"""

import threading

import psycopg
import pytest

from qello_knowledge.adapters.postgres.store import PostgresStore
from qello_knowledge.domain.retrieval import RetrievalRequest
from qello_knowledge.retrieval import RetrievalDeps, retrieve
from tests.localdb.sync.version_setup import activate, prepare, rollback
from tests.unit.retrieval.fakes import query_embedder

pytestmark = pytest.mark.localdb


def test_switches_never_mix_versions(db_url, sync_store, store, monkeypatch, record_property):
    # 원본이 바뀐 문서가 없는 데이터라 되돌리기의 출처 어긋남은 0이다(tasks T042).
    ready = prepare(sync_store, store, monkeypatch)
    assert activate(sync_store, ready.v2)[0] == 0
    stop = threading.Event()
    seen = []

    def search():
        embedder, _, _ = query_embedder()
        with PostgresStore(db_url) as own:
            deps = RetrievalDeps(store=own, embedder=embedder, new_run_id=lambda: "run")
            while not stop.is_set():
                seen.append(retrieve(RetrievalRequest("Synthetic"), deps))

    worker = threading.Thread(target=search)
    worker.start()
    try:
        for i in range(12):
            target = ready.v1 if i % 2 == 0 else ready.v2
            code, value = rollback(sync_store, target)
            assert code == 0, value
    finally:
        stop.set()
        worker.join(timeout=30)
    assert seen
    statuses = [r.status for r in seen]
    mixed = 0
    with psycopg.connect(db_url) as conn:
        for result in seen:
            ids = [h.chunk_id for h in result.hits] + [c.chunk_id for b in result.context for c in b.chunks]
            if not ids:
                continue
            versions = conn.execute(
                "SELECT count(DISTINCT index_version) FROM qk.chunk WHERE id = ANY(%s)", (ids,)
            ).fetchone()[0]
            mixed += versions != 1
    changed = statuses.count("index_version_changed")
    record_property("searches", len(seen))
    record_property("index_version_changed", changed)
    print(f"searches={len(seen)} index_version_changed={changed}")
    assert mixed == 0
    assert statuses.count("no_active_index") == 0
    assert set(statuses) <= {"ok", "index_version_changed"}
