"""첫 활성화의 전환 기록(QK-STO-002 FR-002, US3-5). 기존 `test_index_version.py`는 고치지 않는다."""

import psycopg
import pytest

from qello_knowledge.adapters.postgres.sync_store import PostgresSyncStore
from qello_knowledge.sync.activate import activate_first_index
from qello_knowledge.sync.run import SyncOptions, current_spec, run_sync
from tests.unit.sync.helpers import harness

pytestmark = pytest.mark.localdb


def _transitions(url):
    with psycopg.connect(url) as conn:
        return conn.execute(
            "SELECT kind, version, before_active, after_active, documents, chunks, target FROM qk.index_transition"
        ).fetchall()


def test_first_activation_writes_one_transition_with_target(db_url, store):
    with PostgresSyncStore(db_url, target="remote") as sync_store:
        h = harness(store=sync_store, cache_store=store)
        run_sync(h.targets, h.deps, SyncOptions())
        version = current_spec(h.deps).id
        sync_store.current_version = version
        assert activate_first_index(sync_store, version).failed_conditions == ()
        assert _transitions(db_url) == [("first_activation", version, None, version, 5, 5, "remote")]
        assert "active_exists" in activate_first_index(sync_store, version).failed_conditions
    assert len(_transitions(db_url)) == 1


def test_refused_first_activation_writes_nothing(db_url, store, sync_store):
    h = harness(store=sync_store, cache_store=store)
    run_sync(h.targets, h.deps, SyncOptions())
    sync_store.current_version = current_spec(h.deps).id
    assert "current_version" in activate_first_index(sync_store, "iv-other").failed_conditions
    assert _transitions(db_url) == []


def test_default_target_is_local(db_url, store, sync_store):
    h = harness(store=sync_store, cache_store=store)
    run_sync(h.targets, h.deps, SyncOptions())
    version = current_spec(h.deps).id
    sync_store.current_version = version
    activate_first_index(sync_store, version)
    assert _transitions(db_url)[0][-1] == "local"
