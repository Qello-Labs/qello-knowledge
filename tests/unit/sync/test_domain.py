from dataclasses import FrozenInstanceError

import pytest

from qello_knowledge.domain.sync import (
    Action,
    DocumentDecision,
    HoldReason,
    Operation,
    SourcePlan,
    TakedownReason,
    allowed,
)


def decision(*actions, **kwargs):
    return DocumentDecision(doc_key="a" * 64, display="sample", actions=actions, **kwargs)


def test_decision_hides_chunked_body_and_is_frozen():
    doc = decision(Action.PROCESS, chunked="QK-SYN-001-LEAK-MARKER", change_reason="NEW")
    assert "QK-SYN-001-LEAK-MARKER" not in repr(doc)
    with pytest.raises(FrozenInstanceError):
        doc.display = "changed"


@pytest.mark.parametrize(
    "holds, mode",
    [
        ({HoldReason.ORIGIN_MISSING}, "FULL"),
        ({HoldReason.ORIGIN_MISMATCH}, "FULL"),
        ({HoldReason.INDEX_MISMATCH}, "FULL"),
        (set(), "TAKEDOWN_ONLY"),
        ({HoldReason.BUDGET_EXCEEDED}, "FULL"),
    ],
)
def test_plan_rejects_forbidden_processing(holds, mode):
    with pytest.raises(ValueError):
        SourcePlan(
            source_name="docs",
            mode=mode,
            holds=frozenset(holds),
            decisions=(decision(Action.PROCESS, chunked=object(), change_reason="NEW"),),
        )


@pytest.mark.parametrize("hold", list(HoldReason))
def test_security_search_exclusion_survives_every_hold(hold):
    assert allowed({hold}, Operation.SECURITY_HIDE)


@pytest.mark.parametrize(
    "doc, holds",
    [
        (decision(Action.UNCHANGED), {HoldReason.ORIGIN_MISMATCH}),
        (decision(Action.TAKE_DOWN, takedown_reason=TakedownReason.SOURCE_MISSING), {HoldReason.COLLECTION_INCOMPLETE}),
        (decision(Action.TAKE_DOWN, takedown_reason=TakedownReason.NOT_TARGET), {HoldReason.INDEX_MISMATCH}),
        (
            decision(Action.TAKE_DOWN, takedown_reason=TakedownReason.SECURITY_ACCESS, delete_bodies=True),
            {HoldReason.TAKEDOWN_RATIO},
        ),
        (decision(Action.PURGE), {HoldReason.ORIGIN_MISSING}),
    ],
)
def test_plan_rejects_other_forbidden_operations(doc, holds):
    with pytest.raises(ValueError):
        SourcePlan(source_name="docs", decisions=(doc,), holds=frozenset(holds))


def test_security_takedown_can_be_held_without_blocking_search_exclusion():
    plan = SourcePlan(
        source_name="docs",
        holds=frozenset({HoldReason.TAKEDOWN_RATIO}),
        decisions=(decision(Action.TAKE_DOWN, takedown_reason=TakedownReason.CONFIG_EXCLUDED),),
    )
    assert len(plan.decisions) == 1
    assert TakedownReason.CONFIG_EXCLUDED.is_security
    assert not TakedownReason.SOURCE_MISSING.is_security


@pytest.mark.parametrize("actions", [(), (Action.PROCESS, Action.UNCHANGED), (Action.PROCESS, Action.PURGE)])
def test_decision_rejects_invalid_action_sequences(actions):
    with pytest.raises(ValueError):
        decision(*actions)
