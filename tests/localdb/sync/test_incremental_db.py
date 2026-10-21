import psycopg
import pytest

from qello_knowledge.sync.run import SyncOptions, run_sync
from tests.unit.sync.helpers import DEFAULT_DOCS, harness

pytestmark = pytest.mark.localdb


def test_unchanged_reuses_chunk_ids_and_single_edit_replaces_only_that_document(db_url, sync_store, store):
    def run(docs=None):
        h = harness(docs, store=sync_store, cache_store=store)
        result = run_sync(h.targets, h.deps, SyncOptions())
        assert result.status == "succeeded"
        return h

    def snapshot():
        with psycopg.connect(db_url) as conn:
            return dict(
                conn.execute(
                    "SELECT a.source_id,array_agg(c.id ORDER BY c.ordinal) FROM qk.artifact a "
                    "JOIN qk.chunk c ON a.id=c.artifact_id GROUP BY a.source_id"
                ).fetchall()
            )

    run()
    before = snapshot()
    with psycopg.connect(db_url, autocommit=True) as conn:
        assert conn.execute("SELECT count(*) FROM qk.index_version WHERE status='ready'").fetchone() == (1,)
        conn.execute("UPDATE qk.index_version SET status='active'")
    assert len(store.search_keyword("Synthetic", 50).hits) == 5
    again = run()
    assert again.provider.calls == [] and snapshot() == before
    changed = run({**DEFAULT_DOCS, "B": "# Synthetic B\n\nEdited B."})
    after = snapshot()
    assert len(changed.provider.calls) == 1
    assert after["B"] != before["B"]
    assert all(after[k] == v for k, v in before.items() if k != "B")
