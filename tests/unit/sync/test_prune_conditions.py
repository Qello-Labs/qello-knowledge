"""정리 조건(QK-STO-002 FR-027, data-model 2.4)."""

from dataclasses import replace

import pytest

from qello_knowledge.ports.index_versions import PruneState
from qello_knowledge.sync.versions import prune_conditions
from tests.unit.sync.test_version_conditions import T, row

GOOD = PruneState(row("v0", "archived"), "v2", "v2", "v1", 4, False)


def conditions(state=GOOD, version="v0", confirm=False):
    return prune_conditions(state, version=version, confirm_rollback_target=confirm)


def test_all_met():
    assert conditions() == ()


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"state": replace(GOOD, target=row("v2", "active"), current="v3"), "version": "v2"}, "active_version"),
        ({"state": replace(GOOD, target=row("v3", "ready"), current="v3"), "version": "v3"}, "current_version"),
        ({"state": replace(GOOD, target=row("v1", "archived")), "version": "v1"}, "rollback_target_unconfirmed"),
        ({"state": replace(GOOD, sync_running=True)}, "sync_running"),
    ],
)
def test_one_condition_broken(kwargs, expected):
    assert conditions(**kwargs) == (expected,)


def test_rollback_target_with_confirmation_and_already_pruned():
    assert conditions(replace(GOOD, target=row("v1", "archived")), version="v1", confirm=True) == ()
    done = replace(GOOD, target=row("v0", "archived", pruned_at=T), remaining_chunks=0, sync_running=True)
    assert conditions(done) == ()
    assert prune_conditions(replace(GOOD, target=None), version="v9", confirm_rollback_target=False) == (
        "unknown_version",
    )
