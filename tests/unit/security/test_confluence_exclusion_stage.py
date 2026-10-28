"""어댑터가 정한 색인 제외 표시(QK-ING-003 research R-07)는 PATH 단계에서 본문 요청 없이 막힌다."""

import pytest

from qello_knowledge.domain.security import Stage, Verdict
from qello_knowledge.domain.source import AccessInfo, AccessStatus, ChangeKeyKind, SourceItem
from qello_knowledge.domain.source_config import SourceConfig, SourceScope
from qello_knowledge.security.policy import SecurityPolicy
from qello_knowledge.security.screen import screen_items

CONFIG = SourceConfig("docs", "fake", True, scope=SourceScope(("**",)), allowed_hosts=("fake.invalid",))


def _item(source_id="1", location="docs/a.md", exclusion=None):
    return SourceItem(
        "docs", "fake", source_id, f"https://fake.invalid/{source_id}", "v1", ChangeKeyKind.VERSION, "v1", None,
        "page", "제목", location, None, AccessInfo(AccessStatus.PROVIDED, (("visibility", "public"),)), None, exclusion,
    )  # fmt: skip


@pytest.mark.parametrize("value", ["space-home", "outside-home", "unclassified", "not-indexed-type", "excluded-tree"])
def test_exclusion_value_is_path_excluded(value):
    passed, verdicts = screen_items([_item(exclusion=value)], CONFIG, SecurityPolicy())
    assert passed == ()
    assert [(v.verdict, v.stage, v.rule) for v in verdicts] == [
        (Verdict.PATH_EXCLUDED, Stage.PATH, f"source-exclude:{value}")
    ]


def test_without_exclusion_path_stage_is_unchanged():
    passed, verdicts = screen_items([_item()], CONFIG, SecurityPolicy())
    assert [item.source_id for item in passed] == ["1"]
    assert verdicts == ()
    _, excluded = screen_items([_item(location="secrets/key.pem")], CONFIG, SecurityPolicy())
    assert excluded[0].verdict == Verdict.PATH_EXCLUDED and not excluded[0].rule.startswith("source-exclude:")
