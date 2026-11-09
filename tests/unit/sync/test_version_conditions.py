"""활성화 조건(QK-STO-002 FR-021, data-model 2.4). 조건마다 그것 하나만 어긴 사례."""

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from qello_knowledge.ports.index_versions import ActivationState, Coverage, FailedDoc, RunRef, VersionRow
from qello_knowledge.sync.versions import GateFacts, activation_conditions

T = datetime(2026, 11, 5, tzinfo=UTC)
DEFAULTS = {"query_rule": "kw-query-v1", "candidates": 20, "rrf_k": 60}


def row(vid, status, **kw):
    values = dict(
        id=vid,
        embedding_model="m",
        dimension=1024,
        chunking_version="c",
        metadata_schema_version="meta-v1",
        status=status,
        created_at=T,
        activated_at=None,
        pruned_at=None,
        documents=5,
        chunks=5,
        chunks_without_vector=0,
        ever_active=False,
        last_reindex=RunRef("sync-1", "succeeded", T),
    )
    values.update(kw)
    return VersionRow(**values)


GOOD = ActivationState(
    active=row("v1", "active", ever_active=True),
    target=row("v2", "ready"),
    current="v2",
    sync_running=False,
    coverage=Coverage("v2", 5, 5, 0),
    purge_pending=0,
    tokenizer="TokenBigramSplitSymbol",
)
GATE = GateFacts(candidate_tokenizer="TokenBigramSplitSymbol", search=DEFAULTS)


def conditions(state=GOOD, gate=GATE, rule="kw-index-baseline-v1", defaults=DEFAULTS, version="v2"):
    return activation_conditions(state, version=version, gate=gate, keyword_rule=rule, code_defaults=defaults)


def test_all_conditions_met():
    assert conditions() == ()


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"state": replace(GOOD, current="v3")}, "current_version"),
        ({"state": replace(GOOD, target=row("v2", "archived"))}, "ready_version"),
        ({"state": replace(GOOD, target=row("v2", "ready", last_reindex=RunRef("s", "partial", T)))}, "last_reindex"),
        ({"state": replace(GOOD, target=row("v2", "ready", last_reindex=None))}, "last_reindex"),
        ({"state": replace(GOOD, coverage=Coverage("v2", 5, 4, 1))}, "coverage"),
        (
            {"state": replace(GOOD, coverage=Coverage("v2", 5, 5, 0, (FailedDoc("d", "embed", "s"),)))},
            "failed_documents",
        ),
        ({"state": replace(GOOD, target=row("v2", "ready", chunks_without_vector=1))}, "missing_vectors"),
        ({"state": replace(GOOD, target=row("v2", "ready", documents=0))}, "visible_documents"),
        ({"gate": replace(GATE, failed=("gate_verdict",))}, "gate_verdict"),
        ({"rule": "unknown"}, "keyword_rule"),
        ({"gate": replace(GATE, candidate_tokenizer="TokenBigramSplitSymbolAlpha")}, "tokenizer"),
        ({"gate": replace(GATE, search={**DEFAULTS, "candidates": 30})}, "retrieval_settings"),
        ({"state": replace(GOOD, purge_pending=1)}, "purge_pending"),
        ({"state": replace(GOOD, sync_running=True)}, "sync_running"),
    ],
)
def test_one_condition_broken(kwargs, expected):
    assert conditions(**kwargs) == (expected,)


def test_gate_baseline_is_rechecked_against_state():
    assert conditions(gate=replace(GATE, baseline="v1")) == ()
    assert conditions(gate=replace(GATE, baseline="v0")) == ("gate_baseline",)
    assert conditions(gate=replace(GATE, baseline="v0", failed=("gate_baseline",))) == ("gate_baseline",)


def test_unreadable_gate_reports_only_gate_integrity():
    unreadable = GateFacts(failed=("gate_integrity",))
    assert conditions(gate=unreadable) == ("gate_integrity",)
    assert conditions(gate=GateFacts()) == ("gate_integrity",)


def test_no_active_version_and_multiple_failures():
    assert conditions(replace(GOOD, active=None)) == ("no_active_version",)
    failed = conditions(replace(GOOD, purge_pending=2, sync_running=True), rule="unknown")
    assert failed == ("keyword_rule", "purge_pending", "sync_running")
