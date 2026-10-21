import psycopg
import pytest

from qello_knowledge.adapters.postgres.sync_store import PostgresSyncStore
from qello_knowledge.ports.sync import RunInfo
from qello_knowledge.sync.run import SyncOptions, run_sync
from tests.unit.sync.helpers import harness

pytestmark = pytest.mark.localdb


def test_kind_lock_is_exclusive_and_refused_run_has_no_writes(db_url, sync_store, store):
    lock = sync_store.try_lock(("fake",))
    assert lock is not None
    with PostgresSyncStore(db_url) as other:
        h = harness(store=other, cache_store=store)
        result = run_sync(h.targets, h.deps, SyncOptions())
        assert result.exit_code == 6 and h.transport.requests == []
        with psycopg.connect(db_url) as conn:
            assert conn.execute("SELECT count(*) FROM qk.sync_run").fetchone() == (0,)
        assert other.try_lock(("fake",)) is None
    lock.close()
    with PostgresSyncStore(db_url) as other:
        released = other.try_lock(("fake",))
        assert released is not None
        released.close()


def test_dead_lock_owner_releases_and_closes_only_its_kinds(db_url, sync_store, store):
    lock = sync_store.try_lock(("fake",))
    sync_store.begin_run(RunInfo("dead", "manual", "local", "sec", "chk", "iv", ("fake",)), ["docs"])
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute("INSERT INTO qk.sync_source(source_name,source_kind,scope_key) VALUES ('other','other','other:')")
        conn.execute(
            "INSERT INTO qk.sync_run(run_id,trigger,target,rules_version,chunking_version,index_version,status) "
            "VALUES ('alive','manual','local','sec','chk','iv','running')"
        )
        conn.execute("INSERT INTO qk.sync_run_source(run_id,source_name,status) VALUES ('alive','other','running')")
        conn.execute("SELECT pg_terminate_backend(%s)", (sync_store._conn.info.backend_pid,))
    with PostgresSyncStore(db_url) as recovered:
        h = harness(store=recovered, cache_store=store)
        assert run_sync(h.targets, h.deps, SyncOptions(source="docs")).exit_code == 0
        with psycopg.connect(db_url) as conn:
            rows = dict(conn.execute("SELECT run_id,status FROM qk.sync_run WHERE run_id IN ('dead','alive')"))
            assert rows == {"dead": "unfinished", "alive": "running"}
    lock.close()


def test_activation_exclusive_lock_and_prune_keeps_running(db_url, sync_store):
    lock = sync_store.try_lock(("fake",))
    with PostgresSyncStore(db_url, current_version="iv") as other:
        assert "sync_running" in other.activate("iv").failed_conditions
        other.begin_run(RunInfo("running", "manual", "local", "sec", "chk", "iv", ("other",)), ["other"])
        with psycopg.connect(db_url, autocommit=True) as conn:
            conn.execute("UPDATE qk.sync_run SET started_at=now()-interval '100 days'")
        assert other.prune_runs(90) == 0
    lock.close()


def test_prune_is_idempotent_cascades_results_and_preserves_identity(sync_store, store, db_url):
    h = harness(store=sync_store, cache_store=store)
    run_sync(h.targets, h.deps, SyncOptions())
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute("UPDATE qk.sync_run SET finished_at=now()-interval '100 days'")
    assert sync_store.prune_runs(90) == 1
    assert sync_store.prune_runs(90) == 0
    assert "docs" in sync_store.load_sources()
    with psycopg.connect(db_url) as conn:
        assert conn.execute("SELECT count(*) FROM qk.sync_document_result").fetchone() == (0,)
        assert conn.execute("SELECT count(*) FROM qk.sync_run_source").fetchone() == (0,)


def test_other_name_same_kind_first_run_is_also_excluded(db_url, sync_store, store):
    from dataclasses import replace

    lock = sync_store.try_lock(("fake",))
    with PostgresSyncStore(db_url) as other:
        h = harness(store=other, cache_store=store)
        target = replace(h.targets[0], source_name="other", config=replace(h.targets[0].config, name="other"))
        assert run_sync((target,), h.deps, SyncOptions()).exit_code == 6
        assert h.transport.requests == []
    lock.close()


@pytest.mark.parametrize("second_name", ["docs", "other"])
def test_overlapping_real_runs_allow_only_one_writer(db_url, store, second_name, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from tests.unit.security.helpers import fake_config

    entered = Event()
    release = Event()
    with PostgresSyncStore(db_url) as first_store, PostgresSyncStore(db_url) as second_store:
        first = harness(store=first_store, cache_store=store)
        original = first.targets[0].adapter.list_page

        def listing(*args):
            entered.set()
            assert release.wait(10)
            return original(*args)

        monkeypatch.setattr(first.targets[0].adapter, "list_page", listing)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(run_sync, first.targets, first.deps, SyncOptions())
            try:
                assert entered.wait(10)
                second = harness(store=second_store, cache_store=store, config=fake_config(name=second_name))
                assert run_sync(second.targets, second.deps, SyncOptions()).exit_code == 6
                assert second.transport.requests == []
                with psycopg.connect(db_url) as conn:
                    assert conn.execute("SELECT count(*) FROM qk.sync_run").fetchone() == (1,)
            finally:
                release.set()
            assert future.result(timeout=10).status == "succeeded"
