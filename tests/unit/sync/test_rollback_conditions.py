"""되돌리기 조건(QK-STO-002 FR-023·FR-024, data-model 2.4)."""

from dataclasses import replace

import pytest

from qello_knowledge.domain.secret_rules import find_secrets
from qello_knowledge.ports.index_versions import RollbackState
from qello_knowledge.sync.versions import reason_issue, rollback_conditions
from tests.unit.sync.test_version_conditions import T, row
from tests.unit.synthetic_secrets import SYNTHETIC

GOOD = RollbackState(
    active=row("v2", "active", ever_active=True),
    target=row("v1", "archived", ever_active=True),
    current="v2",
    sync_running=False,
    purge_pending=0,
    missing_documents=0,
    provenance_mismatch=0,
)


def conditions(state=GOOD, *, confirm_stale=False, reason="품질 문제로 직전 버전으로 되돌림"):
    return rollback_conditions(
        state, version="v1", confirm_stale=confirm_stale, reason_problem=reason_issue(reason, find_secrets)
    )


def test_all_met():
    assert conditions() == ()


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"reason": None}, "reason_required"),
        ({"reason": "x" * 201}, "reason_required"),
        ({"reason": "   "}, "reason_required"),
        ({"reason": "token " + SYNTHETIC["github-classic"]}, "reason_secret"),
        ({"state": replace(GOOD, target=row("v1", "ready", ever_active=True))}, "not_archived"),
        ({"state": replace(GOOD, target=row("v1", "archived", ever_active=True, pruned_at=T))}, "pruned"),
        ({"state": replace(GOOD, target=row("v1", "archived", ever_active=False))}, "never_active"),
        ({"state": replace(GOOD, purge_pending=1)}, "purge_pending"),
        ({"state": replace(GOOD, sync_running=True)}, "sync_running"),
        ({"state": replace(GOOD, provenance_mismatch=2)}, "provenance_unconfirmed"),
    ],
)
def test_one_condition_broken(kwargs, expected):
    assert conditions(**kwargs) == (expected,)


def test_confirm_stale_and_no_active():
    assert conditions(replace(GOOD, provenance_mismatch=2), confirm_stale=True) == ()
    assert conditions(replace(GOOD, active=None)) == ("no_active_version",)
