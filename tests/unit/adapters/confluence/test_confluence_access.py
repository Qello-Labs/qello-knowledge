"""US2 권한 원값(QK-ING-003 FR-006~FR-012, research R-03, contracts/confluence-adapter.md 2·4~6단계)."""

import pytest

from qello_knowledge.domain.security import AccessScope
from qello_knowledge.domain.source import AccessStatus
from qello_knowledge.security.kinds import judge_confluence_access
from qello_knowledge.sources.collect import list_all
from tests.unit.adapters.confluence_scenarios import BASE, Scenario, adapter, config, session, tree


def _items(scenario, source_config=None, **adapter_changes):
    source_config = source_config or config()
    pages_adapter = adapter(**adapter_changes)
    transport = scenario.transport()
    listing = list_all(pages_adapter, source_config, session(pages_adapter, transport, source_config))
    return {item.source_id: item for item in listing.items}, transport


def _raw(item):
    return dict(item.access.raw)


def _count(transport, needle):
    return sum(needle in r.url for r in transport.requests)


def test_site_users_mode_raw_and_no_permission_request():
    items, transport = _items(Scenario(pages=tree(("2", "가", "1"), ("3", "나", "2"))))
    assert items["3"].access.raw == (
        ("judge_mode", "site_users"),
        ("space_type", "global"),
        ("space_status", "current"),
        ("site_review_valid", "true"),
        ("read_restricted", "none"),
        ("ancestor_count", "2"),
    )
    assert judge_confluence_access(items["3"].access) == AccessScope.TEAM
    assert _count(transport, "/permissions") == 0


def test_expired_or_missing_site_review_is_false():
    items, _ = _items(Scenario(pages=tree(("2", "가", "1"))), site_review_valid=False)
    assert _raw(items["2"])["site_review_valid"] == "false"
    items, _ = _items(Scenario(pages=tree(("2", "가", "1"))), site_review_valid=None)
    assert _raw(items["2"])["site_review_valid"] == "false"


def _permission(principal_type="group", principal_id="grp-1", key="read", target="space"):
    return {
        "id": "p",
        "principal": {"type": principal_type, "id": principal_id},
        "operation": {"key": key, "targetType": target},
    }


@pytest.mark.parametrize(
    ("assignments", "expected"),
    [
        ([_permission()], "true"),
        ([_permission(principal_type="user", principal_id="acct-000"), _permission()], "true"),
        ([_permission(principal_id="grp-2")], "false"),
        ([_permission(key="update")], "false"),
        ([_permission(target="page")], "false"),
        ([], "false"),
    ],
)
def test_team_group_permission_matching(assignments, expected):
    source_config = config(judge_mode="team_group", team_group_id="grp-1")
    items, transport = _items(Scenario(pages=tree(("2", "가", "1")), permissions=assignments), source_config)
    raw = _raw(items["2"])
    assert raw["team_group_read"] == expected and "site_review_valid" not in raw
    assert _count(transport, "/permissions") == 1


def test_team_group_permission_failure_is_lookup_failure():
    source_config = config(judge_mode="team_group", team_group_id="grp-1")
    scenario = Scenario(pages=tree(("2", "가", "1")), permissions=[])
    scenario.override(f"{BASE}/spaces/100/permissions?limit=250", status=403)
    items, _ = _items(scenario, source_config)
    assert all(item.access.status == AccessStatus.UNKNOWN for item in items.values())


@pytest.mark.parametrize(
    ("restrictions", "expected"),
    [
        ({"3": "VIEW_RESTRICTED"}, "self"),
        ({"2": "VIEW_RESTRICTED"}, "ancestor"),
        ({"1": "VIEW_RESTRICTED"}, "ancestor"),
        ({"3": "EDIT_RESTRICTED", "2": "OPEN"}, "none"),
        ({"3": "SOMETHING_NEW"}, "unknown"),
        ({"2": "SOMETHING_NEW", "3": "VIEW_RESTRICTED"}, "self"),
    ],
)
def test_read_restricted_from_self_and_ancestors(restrictions, expected):
    pages = tree(("2", "가", "1"), ("3", "나", "2"))
    for page in pages:
        page["restriction"] = restrictions.get(page["id"], "OPEN")
    items, _ = _items(Scenario(pages=pages))
    assert _raw(items["3"])["read_restricted"] == expected


def test_each_content_restriction_is_requested_once():
    pages = tree(("2", "가", "1"), ("3", "나", "2"), ("4", "다", "2"))
    _, transport = _items(Scenario(pages=pages))
    assert _count(transport, "/restriction-state") == len(pages)


@pytest.mark.parametrize("status", [403, 404, 429])
def test_restriction_request_failure_is_lookup_failure(status):
    pages = tree(("2", "가", "1"), ("3", "나", "2"), ("4", "다", "1"))
    scenario = Scenario(pages=pages)
    scenario.override(f"{BASE}/pages/2/restriction-state", status=status)
    for _ in range(3):  # 일시적 실패는 재시도를 다 쓴 뒤 조회 실패가 된다
        scenario.queue(f"{BASE}/pages/2/restriction-state", status=status)
    items, _ = _items(scenario)
    assert items["2"].access.status == AccessStatus.UNKNOWN and items["2"].access.raw == ()
    assert items["3"].access.status == AccessStatus.UNKNOWN
    assert items["4"].access.status == AccessStatus.PROVIDED


def test_folder_chain_and_folder_restriction():
    pages = tree(("3", "나", "f1", {"parent_type": "folder"}))
    folders = [{"id": "f1", "title": "폴더", "parent_id": "1", "parent_type": "page", "restriction": "VIEW_RESTRICTED"}]
    items, transport = _items(Scenario(pages=pages, folders=folders))
    assert _raw(items["3"])["read_restricted"] == "ancestor"
    assert items["3"].location == "SCRUM/폴더/나"
    assert _count(transport, "/folders/f1") == 2  # 폴더 조회 1, 보기 제한 1


def test_folder_scope_missing_is_lookup_failure():
    pages = tree(("3", "나", "f1", {"parent_type": "folder"}))
    folders = [{"id": "f1", "parent_id": "1"}]
    scenario = Scenario(pages=pages, folders=folders)
    scenario.override(f"{BASE}/folders/f1", status=403)
    items, _ = _items(scenario)
    assert items["3"].access.status == AccessStatus.UNKNOWN


@pytest.mark.parametrize(
    "page",
    [
        {"id": "3", "title": "나", "parent_id": "77"},  # 목록에 없는 상위 페이지
        {"id": "3", "title": "나", "parent_id": "77", "parent_type": "whiteboard"},
    ],
)
def test_structural_chain_break_is_rule_unknown_not_lookup_failure(page):
    items, _ = _items(Scenario(pages=[*tree(), page]))
    assert items["3"].access.status == AccessStatus.PROVIDED
    assert _raw(items["3"])["read_restricted"] == "unknown"


@pytest.mark.parametrize("space_type", ["collaboration", "knowledge_base", "system"])
def test_space_type_is_passed_through(space_type):
    items, _ = _items(Scenario(space_type=space_type, pages=tree(("2", "가", "1"))))
    assert _raw(items["2"])["space_type"] == space_type


def test_archived_space_status_is_passed_through():
    items, _ = _items(Scenario(space_status="archived", pages=tree(("2", "가", "1"))))
    assert _raw(items["2"])["space_status"] == "archived"
    assert judge_confluence_access(items["2"].access) == AccessScope.UNKNOWN


# ---- 구현 검토 C1: 끊긴 사슬은 제외하지 않고 권한 판정에 맡긴다 ------------------------------------


def test_pages_under_unreadable_folder_are_lookup_failures_not_excluded():
    pages = tree(*[(str(n), f"문서 {n}", "f1", {"parent_type": "folder"}) for n in range(2, 6)])
    scenario = Scenario(pages=pages, folders=[{"id": "f1", "parent_id": "1"}])
    scenario.override(f"{BASE}/folders/f1", status=403)
    items, _ = _items(scenario, config(doc_types={"f1": "설계 문서"}))
    for page_id in ("2", "3", "4", "5"):
        assert items[page_id].exclusion is None
        assert items[page_id].access.status == AccessStatus.UNKNOWN


def test_chain_cut_by_incomplete_listing_is_lookup_failure_not_excluded():
    pages = tree(("2", "자식", "9"), ("9", "부모", "1"))  # ID 순서로 자식이 1쪽, 부모가 2쪽
    scenario = Scenario(pages=pages, page_size=2)
    scenario.override(cf_next_url(), status=503)
    for _ in range(3):
        scenario.queue(cf_next_url(), status=503)
    items, _ = _items(scenario, config(doc_types={"9": "설계 문서"}))
    assert set(items) == {"1", "2"}
    assert items["2"].exclusion is None and items["2"].access.status == AccessStatus.UNKNOWN


def test_true_root_outside_home_is_still_excluded():
    items, _ = _items(Scenario(pages=[*tree(), {"id": "99", "title": "홈 밖", "parent_id": None}]))
    assert items["99"].exclusion == "outside-home"


def test_structural_break_is_not_excluded():
    items, _ = _items(Scenario(pages=[*tree(), {"id": "3", "title": "나", "parent_id": "77"}]))
    assert items["3"].exclusion is None


def cf_next_url():
    from tests.unit.adapters.confluence_scenarios import ROOT

    return ROOT + "/wiki/api/v2/spaces/100/pages?status=current&limit=250&cursor=c1"
