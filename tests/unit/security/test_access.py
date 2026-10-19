"""자료원 종류별 접근 판정(research R-05, FR-016·017)."""

import pytest

from qello_knowledge.domain.security import AccessScope
from qello_knowledge.domain.source import AccessInfo, AccessStatus
from qello_knowledge.security.kinds import KINDS

GITHUB = KINDS["github_repo_files"]
FAKE = KINDS["fake"]


def _provided(*pairs):
    return AccessInfo(AccessStatus.PROVIDED, tuple(pairs))


def test_rule_names():
    assert (GITHUB.rule_name, FAKE.rule_name) == ("github-visibility-v1", "fake-visibility-v1")


def test_github_public_repository_is_team():
    assert GITHUB.judge(_provided(("visibility", "public"))) == AccessScope.TEAM


@pytest.mark.parametrize(
    "access",
    [
        _provided(("visibility", "private")),
        _provided(("visibility", "internal")),
        _provided(("visibility", "")),
        _provided(("visibility", "everyone")),
        _provided(("visibility", "public"), ("visibility", "private")),
        _provided(("visibility", "public"), ("visibility", "public")),
        _provided(("visibility", "public"), ("owner", "team")),
        _provided(("owner", "team")),
        AccessInfo(AccessStatus.UNKNOWN),
    ],
)
def test_github_anything_else_is_unknown(access):
    assert GITHUB.judge(access) == AccessScope.UNKNOWN


@pytest.mark.parametrize(
    ("value", "scope"),
    [("public", AccessScope.TEAM), ("restricted", AccessScope.RESTRICTED), ("private", AccessScope.UNKNOWN)],
)
def test_fake_visibility(value, scope):
    assert FAKE.judge(_provided(("visibility", value))) == scope


@pytest.mark.parametrize("spec", [GITHUB, FAKE])
def test_unknown_input_is_always_unknown(spec):
    assert spec.judge(AccessInfo(AccessStatus.UNKNOWN)) == AccessScope.UNKNOWN
