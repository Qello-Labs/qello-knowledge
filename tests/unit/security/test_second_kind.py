"""두 번째 가짜 종류의 접근 규칙을 더해도 필터 공통 코드는 바뀌지 않는다(FR-015, SC-006).

이 파일만 단독 커밋으로 만들고 `git show --stat`으로 변경이 `tests/` 아래뿐인지 확인한다.
"""

from dataclasses import replace
from datetime import UTC, datetime

from qello_knowledge.domain.security import AccessScope, Verdict
from qello_knowledge.domain.source import AccessInfo, AccessStatus, ChangeKeyKind, SourceItem
from qello_knowledge.security.kinds import KINDS, KindSecurityPolicy
from qello_knowledge.security.policy import SecurityPolicy
from qello_knowledge.security.screen import screen_items
from tests.unit.security.helpers import fake_config


def judge_sharing(access: AccessInfo) -> AccessScope:
    raw = dict(access.raw) if access.status == AccessStatus.PROVIDED else {}
    return AccessScope.TEAM if raw == {"sharing": "team"} else AccessScope.UNKNOWN


def _item(source_id, sharing):
    access = AccessInfo(AccessStatus.PROVIDED, (("sharing", sharing),))
    return SourceItem(
        "wiki", "fake2", source_id, f"https://fake2.invalid/{source_id}", "v1", ChangeKeyKind.VERSION, "v1",
        datetime(2026, 1, 1, tzinfo=UTC), "page", "t", f"pages/{source_id}.md", None, access, None,
    )  # fmt: skip


def test_second_kind_rule_is_used_without_common_code_changes():
    spec = KindSecurityPolicy("fake2", "fake2-sharing-v1", judge_sharing, ("fake2.invalid",), False)
    policy = SecurityPolicy(kinds={**KINDS, "fake2": spec})
    config = replace(fake_config(), name="wiki", kind="fake2")
    passed, verdicts = screen_items([_item("1", "team"), _item("2", "me")], config, policy)
    assert [item.source_id for item in passed] == ["1"]
    assert [(v.verdict, v.rule) for v in verdicts] == [(Verdict.ACCESS_HELD, "fake2-sharing-v1")]
