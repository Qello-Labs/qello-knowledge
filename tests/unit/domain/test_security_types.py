from dataclasses import FrozenInstanceError

import pytest

from qello_knowledge.domain.redact import FieldKind
from qello_knowledge.domain.security import AccessScope, SecurityVerdict, Stage, Verdict


def _verdict(**changes):
    values = {
        "source_name": "docs",
        "source_id": "1",
        "location": "docs/1.md",
        "url": "https://fake.invalid/view/1",
        "title": "Document 1",
        "verdict": Verdict.PASSED,
        "stage": Stage.PASSED,
        "rule": "fake-visibility-v1",
        "access_scope": AccessScope.TEAM,
        "rules_version": "sec-000000000000",
    }
    values.update(changes)
    return SecurityVerdict(**values)


def test_enum_values_follow_data_model():
    assert [v.value for v in AccessScope] == ["TEAM", "RESTRICTED", "UNKNOWN"]
    assert [v.value for v in Verdict] == ["PASSED", "PATH_EXCLUDED", "ACCESS_HELD", "SECRET_BLOCKED", "ERROR"]
    assert [v.value for v in Stage] == ["PATH", "ACCESS", "ITEM_SECRET", "FETCH", "CONTENT_SECRET", "PASSED"]
    assert [v.value for v in FieldKind] == ["LINK", "PATH", "TEXT"]


def test_passed_requires_team_scope():
    with pytest.raises(ValueError):
        _verdict(access_scope=AccessScope.UNKNOWN)


@pytest.mark.parametrize("scope", [AccessScope.RESTRICTED, AccessScope.UNKNOWN])
def test_access_held_requires_non_team_scope(scope):
    _verdict(verdict=Verdict.ACCESS_HELD, stage=Stage.ACCESS, access_scope=scope)
    with pytest.raises(ValueError):
        _verdict(verdict=Verdict.ACCESS_HELD, stage=Stage.ACCESS, access_scope=AccessScope.TEAM)


def test_error_requires_error_type():
    _verdict(verdict=Verdict.ERROR, stage=Stage.ITEM_SECRET, access_scope=None, error_type="KeyError")
    with pytest.raises(ValueError):
        _verdict(verdict=Verdict.ERROR, stage=Stage.ITEM_SECRET, access_scope=None)


def test_verdict_is_immutable():
    verdict = _verdict()
    with pytest.raises(FrozenInstanceError):
        verdict.rule = "other"
