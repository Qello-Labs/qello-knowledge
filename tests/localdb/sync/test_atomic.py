from dataclasses import replace

import psycopg
import pytest

from qello_knowledge.adapters.postgres import sync_store as module
from qello_knowledge.domain.store import StoreError
from tests.localdb.sync.test_sync_store import begin, inputs

pytestmark = pytest.mark.localdb


def snapshot(db_url):
    with psycopg.connect(db_url) as conn:
        return (
            conn.execute("SELECT row_to_json(a) FROM qk.artifact a ORDER BY id").fetchall(),
            conn.execute("SELECT row_to_json(c) FROM qk.chunk c ORDER BY id").fetchall(),
            conn.execute("SELECT row_to_json(r) FROM qk.sync_document_result r ORDER BY doc_key,action").fetchall(),
        )


def test_apply_failure_rolls_back_every_state_column_and_result(sync_store, db_url, monkeypatch):
    begin(sync_store)
    doc, write, chunks = inputs()
    identity = sync_store.apply_document("run-1", doc, write, "iv-test", chunks)
    before = snapshot(db_url)
    begin(sync_store, "run-2")
    original = module._replace_chunk_rows

    def broken(conn, *args):
        original(conn, *args)
        raise StoreError("injected failure")

    monkeypatch.setattr(module, "_replace_chunk_rows", broken)
    with pytest.raises(StoreError):
        sync_store.apply_document(
            "run-2",
            replace(doc, artifact_id=identity),
            replace(write, record=replace(write.record, source_version="v2"), chunk_input_hash="new"),
            "iv-test",
            chunks,
        )
    assert snapshot(db_url) == before
    assert sync_store.load_documents("fake")["opaque"].chunk_input_hash == "fingerprint"


def test_other_connection_observes_complete_previous_bundle_until_commit(sync_store, db_url, monkeypatch):
    begin(sync_store)
    doc, write, chunks = inputs()
    sync_store.apply_document("run-1", doc, write, "iv-test", chunks)
    before = snapshot(db_url)
    begin(sync_store, "run-2")
    original = module._replace_chunk_rows

    def observed(conn, *args):
        original(conn, *args)
        assert snapshot(db_url) == before

    monkeypatch.setattr(module, "_replace_chunk_rows", observed)
    sync_store.apply_document("run-2", doc, replace(write, chunk_input_hash="new"), "iv-test", chunks)
    assert snapshot(db_url) != before


@pytest.mark.parametrize("point, committed", [("before", False), ("after", True), ("finish", True)])
def test_connection_loss_keeps_document_and_result_in_agreement_then_reruns(
    db_url, store, point, committed, monkeypatch
):
    from qello_knowledge.adapters.postgres.sync_store import PostgresSyncStore
    from qello_knowledge.domain.store import StoreUnavailable
    from qello_knowledge.sync.run import SyncOptions, run_sync
    from tests.unit.sync.helpers import harness

    def terminate(instance):
        with psycopg.connect(db_url, autocommit=True) as other:
            assert other.execute("SELECT current_database()").fetchone()[0].startswith("qk_test_")
            other.execute("SELECT pg_terminate_backend(%s)", (instance._conn.info.backend_pid,))

    with PostgresSyncStore(db_url) as instance:
        h = harness({"A": "# Synthetic A"}, store=instance, cache_store=store)
        if point == "before":
            original = module._replace_chunk_rows

            def interrupted(conn, *args):
                terminate(instance)
                original(conn, *args)

            monkeypatch.setattr(module, "_replace_chunk_rows", interrupted)
        elif point == "after":
            original_apply = instance.apply_document

            def interrupted(*args):
                original_apply(*args)
                terminate(instance)
                raise StoreUnavailable("connection lost")

            monkeypatch.setattr(instance, "apply_document", interrupted)
        else:

            def interrupted(*args):
                terminate(instance)
                raise StoreUnavailable("connection lost")

            monkeypatch.setattr(instance, "finish_run", interrupted)
        with pytest.raises(StoreUnavailable):
            run_sync(h.targets, h.deps, SyncOptions())
        with psycopg.connect(db_url) as conn:
            assert conn.execute("SELECT count(*) FROM qk.artifact").fetchone()[0] == int(committed)
            assert conn.execute("SELECT count(*) FROM qk.sync_document_result WHERE action='PROCESS'").fetchone()[
                0
            ] == int(committed)
    monkeypatch.undo()
    with PostgresSyncStore(db_url) as recovered:
        h = harness({"A": "# Synthetic A"}, store=recovered, cache_store=store)
        assert run_sync(h.targets, h.deps, SyncOptions()).status == "succeeded"
    with psycopg.connect(db_url) as conn:
        assert conn.execute("SELECT count(*) FROM qk.artifact").fetchone() == (1,)
        assert conn.execute("SELECT count(*) FROM qk.chunk").fetchone() == (1,)
