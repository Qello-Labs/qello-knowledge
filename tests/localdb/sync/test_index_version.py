import psycopg
import pytest

from qello_knowledge.sync.activate import activate_first_index
from qello_knowledge.sync.run import SyncOptions, current_spec, run_sync
from tests.unit.sync.helpers import harness

pytestmark = pytest.mark.localdb


def seed(sync_store, store):
    h = harness(store=sync_store, cache_store=store)
    result = run_sync(h.targets, h.deps, SyncOptions())
    version = current_spec(h.deps).id
    sync_store.current_version = version
    return h, result, version


def test_first_activation_requires_success_and_is_never_automatic(sync_store, store):
    h, result, version = seed(sync_store, store)
    assert sync_store.index_state().active is None
    check = activate_first_index(sync_store, version)
    assert check.failed_conditions == () and check.documents == 5 and check.chunks == 5
    assert len(store.search_keyword("Synthetic", 50).hits) == 5
    assert "active_exists" in activate_first_index(sync_store, version).failed_conditions


@pytest.mark.parametrize("bad_status", ["partial", "stopped", "unfinished", "running"])
def test_unsuccessful_last_run_rejects_activation(sync_store, store, db_url, bad_status):
    h, result, version = seed(sync_store, store)
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute("UPDATE qk.sync_run SET status=%s WHERE run_id=%s", (bad_status, result.run_id))
    assert "last_run" in activate_first_index(sync_store, version).failed_conditions
    assert sync_store.index_state().active is None


@pytest.mark.parametrize("historical_status", ["unfinished", "running"])
def test_activation_ignores_closed_history_but_rejects_any_running_run(sync_store, store, db_url, historical_status):
    h, result, version = seed(sync_store, store)
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO qk.sync_run(run_id,trigger,target,rules_version,chunking_version,index_version,"
            "started_at,finished_at,status,summary) "
            "SELECT 'sync-historical',trigger,target,rules_version,chunking_version,index_version,"
            "started_at - interval '1 day',"
            "CASE WHEN %s='unfinished' THEN started_at ELSE NULL END,%s,summary "
            "FROM qk.sync_run WHERE run_id=%s",
            (historical_status, historical_status, result.run_id),
        )
        if historical_status == "running":
            # A running execution blocks activation even for another index version.
            conn.execute("UPDATE qk.sync_run SET index_version='iv-other' WHERE run_id='sync-historical'")
    check = activate_first_index(sync_store, version)
    assert check.last_run_status == "succeeded"
    assert check.failed_conditions == (() if historical_status == "unfinished" else ("last_run",))
    assert sync_store.index_state().active == (version if historical_status == "unfinished" else None)


def test_wrong_version_empty_and_missing_vectors_are_reported(sync_store, store, db_url):
    h, result, version = seed(sync_store, store)
    assert "current_version" in activate_first_index(sync_store, "old").failed_conditions
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute("UPDATE qk.chunk SET embedding_id=NULL")
    assert "missing_vectors" in activate_first_index(sync_store, version).failed_conditions
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute("UPDATE qk.artifact SET status='deleted'")
    assert "visible_documents" in activate_first_index(sync_store, version).failed_conditions


def test_configuration_version_change_before_activation_reprocesses_into_new_ready_version(
    sync_store, store, db_url, monkeypatch
):
    from dataclasses import replace

    from qello_knowledge.sync import run as module
    from qello_knowledge.sync.keys import index_version_id

    h, result, version = seed(sync_store, store)
    spec = current_spec(h.deps)
    new_id = index_version_id(spec.embedding_model, spec.dimension, spec.chunking_version, "meta-next")
    monkeypatch.setattr(
        module, "current_spec", lambda deps: replace(spec, id=new_id, metadata_schema_version="meta-next")
    )
    next_run = harness(store=sync_store, cache_store=store)
    result = run_sync(next_run.targets, next_run.deps, SyncOptions())
    assert result.status == "succeeded" and result.sources[0]["counts"] == {"PROCESS": 5}
    assert next_run.provider.calls == []
    assert sync_store.index_state().active is None
    assert set(sync_store.index_state().ready) == {version, new_id}
    with psycopg.connect(db_url) as conn:
        assert conn.execute(
            "SELECT DISTINCT change_reason FROM qk.sync_document_result WHERE run_id=%s", (result.run_id,)
        ).fetchall() == [("INDEX_CHANGED",)]
