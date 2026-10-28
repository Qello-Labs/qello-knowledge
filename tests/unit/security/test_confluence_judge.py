"""Confluence 접근 판정 규칙 `confluence-access-v1`(QK-ING-003 data-model 4절, FR-002·FR-008~FR-012)."""

import pytest

from qello_knowledge.domain.security import AccessScope
from qello_knowledge.domain.source import AccessInfo, AccessStatus
from qello_knowledge.security.kinds import KINDS, judge_confluence_access


def raw(mode="site_users", space_type="global", status="current", flag="true", restricted="none", count="1"):
    flag_key = "site_review_valid" if mode == "site_users" else "team_group_read"
    return (
        ("judge_mode", mode),
        ("space_type", space_type),
        ("space_status", status),
        (flag_key, flag),
        ("read_restricted", restricted),
        ("ancestor_count", count),
    )


def judge(pairs):
    return judge_confluence_access(AccessInfo(AccessStatus.PROVIDED, pairs))


@pytest.mark.parametrize("space_type", ["global", "collaboration", "knowledge_base"])
@pytest.mark.parametrize("mode", ["site_users", "team_group"])
def test_team_space_types_with_permission_and_no_restriction_are_team(space_type, mode):
    assert judge(raw(mode, space_type)) == AccessScope.TEAM


@pytest.mark.parametrize("space_type", ["personal", "system", "onboarding", "xflow_sample_space", "new_kind", ""])
def test_other_space_types_are_unknown(space_type):
    assert judge(raw(space_type=space_type)) == AccessScope.UNKNOWN


@pytest.mark.parametrize("status", ["archived", "trashed", "unknown"])
def test_non_current_space_is_unknown(status):
    assert judge(raw(status=status)) == AccessScope.UNKNOWN


@pytest.mark.parametrize("mode", ["site_users", "team_group"])
def test_missing_permission_is_unknown(mode):
    assert judge(raw(mode, flag="false")) == AccessScope.UNKNOWN


@pytest.mark.parametrize("restricted", ["self", "ancestor"])
def test_view_restriction_is_restricted(restricted):
    assert judge(raw(restricted=restricted)) == AccessScope.RESTRICTED
    assert judge(raw(flag="false", restricted=restricted)) == AccessScope.RESTRICTED


def test_unknown_restriction_is_unknown():
    assert judge(raw(restricted="unknown")) == AccessScope.UNKNOWN


@pytest.mark.parametrize(
    "pairs",
    [
        raw()[:-1],  # 키 누락
        raw() + (("extra", "1"),),  # 모르는 키
        tuple(reversed(raw())),  # 키 순서가 다름
        (("judge_mode", "site_users"), *raw("team_group")[1:]),  # 방식과 맞지 않는 키
        (("judge_mode", "everyone"), *raw()[1:]),
        raw(count="-1"),
        raw(flag="yes"),
    ],
)
def test_malformed_raw_is_unknown(pairs):
    assert judge(pairs) == AccessScope.UNKNOWN


def test_unknown_access_status_is_unknown():
    assert judge_confluence_access(AccessInfo(AccessStatus.UNKNOWN)) == AccessScope.UNKNOWN


def test_registered_kind_values():
    spec = KINDS["confluence_pages"]
    assert spec.rule_name == "confluence-access-v1"
    assert spec.public_link_hosts == () and spec.source_id_is_path is False
    assert spec.opaque_item_fields is True and spec.lookup_failure_threshold == 0.10
