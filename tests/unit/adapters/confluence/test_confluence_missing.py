"""사라진 페이지 단건 확인(QK-ING-003 FR-030, research R-04, contracts/confluence-adapter.md `check_missing`)."""

import pytest

from qello_knowledge.domain.source import MissingCheck
from tests.unit.adapters.confluence_scenarios import STATUS_QUERY, Scenario, adapter, config, session


def _check(scenario, ids):
    source_config = config()
    pages_adapter = adapter()
    transport = scenario.transport()
    result = pages_adapter.check_missing(session(pages_adapter, transport, source_config), source_config, ids)
    return result, transport


@pytest.mark.parametrize(
    ("status", "body", "expected"),
    [
        (403, {}, MissingCheck.GONE),
        (404, {}, MissingCheck.GONE),
        (200, {"id": "9", "status": "current", "spaceId": "555"}, MissingCheck.GONE),
        (200, {"id": "9", "status": "archived", "spaceId": "100"}, MissingCheck.ARCHIVED),
        (200, {"id": "9", "status": "trashed", "spaceId": "100"}, MissingCheck.ARCHIVED),
        (200, {"id": "9", "status": "deleted", "spaceId": "100"}, MissingCheck.ARCHIVED),
        (200, {"id": "9", "status": "current", "spaceId": "100"}, MissingCheck.PRESENT),
        (200, {"id": "9", "status": "draft", "spaceId": "100"}, MissingCheck.UNCERTAIN),
        (200, "not json", MissingCheck.UNCERTAIN),
        (500, {}, MissingCheck.UNCERTAIN),
        (429, {}, MissingCheck.UNCERTAIN),
    ],
)
def test_single_check_results(status, body, expected):
    scenario = Scenario()
    for _ in range(4):  # 429·500은 재시도한다
        scenario.queue(f"https://api.atlassian.com/ex/confluence/cloud-test/wiki/api/v2/pages/9?{STATUS_QUERY}",
                       status=status, body=body)  # fmt: skip
    result, transport = _check(scenario, ["9"])
    assert result == {"9": expected}
    assert transport.requests[0].url.endswith("/pages/9?" + STATUS_QUERY)


def test_each_id_is_checked_once():
    scenario = Scenario()
    for page_id in ("7", "8"):
        scenario.missing(page_id, status=404)
    result, transport = _check(scenario, ["7", "8"])
    assert result == {"7": MissingCheck.GONE, "8": MissingCheck.GONE}
    assert len(transport.requests) == 2
