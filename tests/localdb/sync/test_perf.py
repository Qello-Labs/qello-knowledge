"""SC-013: 시드 고정 합성 79개, 외부 대기·실제 임베딩 0, 로컬 DB 측정."""

import statistics
import time

import psycopg
import pytest

from qello_knowledge.sync.run import SyncOptions, run_sync
from tests.unit.chunking.test_perf import documents
from tests.unit.sync.helpers import harness

pytestmark = pytest.mark.localdb


def test_first_and_unchanged_sync_medians(sync_store, store, db_url, record_property):
    docs = {str(i): body for i, body in enumerate(documents())}
    first_times = []
    unchanged_times = []
    for _ in range(3):
        with psycopg.connect(db_url, autocommit=True) as conn:
            assert conn.execute("SELECT current_database()").fetchone()[0].startswith("qk_test_")
            conn.execute(
                "TRUNCATE qk.sync_run,qk.sync_source,qk.chunk,qk.embedding,qk.artifact,qk.index_version "
                "RESTART IDENTITY CASCADE"
            )
        first = harness(docs, store=sync_store, cache_store=store)
        start = time.perf_counter()
        assert run_sync(first.targets, first.deps, SyncOptions()).status == "succeeded"
        first_times.append(time.perf_counter() - start)
        again = harness(docs, store=sync_store, cache_store=store)
        start = time.perf_counter()
        assert run_sync(again.targets, again.deps, SyncOptions()).status == "succeeded"
        unchanged_times.append(time.perf_counter() - start)
        assert again.provider.calls == []
    initial = statistics.median(first_times)
    unchanged = statistics.median(unchanged_times)
    record_property("documents", 79)
    record_property("repetitions", 3)
    record_property("first_median_seconds", initial)
    record_property("unchanged_median_seconds", unchanged)
    print(f"perf documents=79 repeats=3 first_median={initial:.6f} unchanged_median={unchanged:.6f}")
    assert initial <= 60 and unchanged <= 30
