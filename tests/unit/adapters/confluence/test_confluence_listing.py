"""US1 목록(QK-ING-003 FR-001~005, SC-001). 재생 응답만 쓴다."""

from hashlib import sha256

from qello_knowledge.domain.source import ChangeKeyKind, SourceOrigin
from qello_knowledge.sources.collect import list_all
from tests.unit.adapters.confluence_scenarios import BASE, ROOT, SITE, Scenario, adapter, config, session, tree


def _list(scenario, source_config=None, **adapter_changes):
    source_config = source_config or config()
    pages_adapter = adapter(**adapter_changes)
    transport = scenario.transport()
    listing = list_all(pages_adapter, source_config, session(pages_adapter, transport, source_config))
    return listing, transport


def _urls(transport, needle):
    return [r.url for r in transport.requests if needle in r.url]


def test_listing_maps_items_sorted_by_id():
    pages = tree(("12", "회의록", "1"), ("3", "2026-10-14 정기 회의", "12", {"version": 7}))
    listing, _ = _list(Scenario(pages=pages))
    assert listing.complete
    assert [item.source_id for item in listing.items] == ["1", "12", "3"]
    item = {i.source_id: i for i in listing.items}["3"]
    assert item.source_kind == "confluence_pages" and item.item_type == "confluence_page"
    assert item.url == SITE + "/spaces/SCRUM/pages/3"
    assert item.version == "7"
    assert item.change_key == "7:" + sha256("2026-10-14 정기 회의".encode()).hexdigest()[:12]
    assert item.change_key_kind == ChangeKeyKind.VERSION
    assert item.title == "2026-10-14 정기 회의"
    assert item.location == "SCRUM/회의록/2026-10-14 정기 회의"
    assert item.modified_at is not None and item.modified_at.tzinfo is not None
    assert listing.origin == SourceOrigin("100", "SCRUM", None)


def test_same_responses_give_same_listing():
    pages = tree(("2", "가", "1"), ("3", "나", "2"))
    first, _ = _list(Scenario(pages=pages))
    second, _ = _list(Scenario(pages=pages))
    assert first == second


def test_pages_follow_next_links_on_the_gateway_without_duplicates():
    pages = tree(*[(str(n), f"문서 {n}", "1") for n in range(2, 7)])
    listing, transport = _list(Scenario(pages=pages, page_size=2))
    assert sorted(i.source_id for i in listing.items) == sorted(p["id"] for p in pages)
    assert listing.duplicates_dropped == 0 and listing.complete
    listed = _urls(transport, "/pages?")
    assert listed[0] == f"{BASE}/spaces/100/pages?status=current&limit=250"
    assert listed[1] == ROOT + "/wiki/api/v2/spaces/100/pages?status=current&limit=250&cursor=c1"
    assert len(listed) == 3


def test_failed_next_page_makes_listing_incomplete():
    pages = tree(*[(str(n), f"문서 {n}", "1") for n in range(2, 6)])
    scenario = Scenario(pages=pages, page_size=2)
    scenario.override(ROOT + "/wiki/api/v2/spaces/100/pages?status=current&limit=250&cursor=c1", status=404)
    listing, _ = _list(scenario)
    assert not listing.complete
    assert listing.incomplete_reason == "listing_failed"
    assert [i.source_id for i in listing.items] == ["1", "2"]


def test_title_only_change_changes_change_key():
    before, _ = _list(Scenario(pages=tree(("2", "옛 제목", "1"))))
    after, _ = _list(Scenario(pages=tree(("2", "새 제목", "1"))))
    old = {i.source_id: i for i in before.items}["2"]
    new = {i.source_id: i for i in after.items}["2"]
    assert old.version == new.version and old.change_key != new.change_key


def test_location_segments_are_normalized():
    pages = tree(("2", "  A/B  ", "1"), ("3", "", "2"), ("4", "..", "3"), ("5", ".", "4"))
    listing, _ = _list(Scenario(pages=pages))
    locations = {i.source_id: i.location for i in listing.items}
    assert locations["2"] == "SCRUM/A／B"
    assert locations["3"] == "SCRUM/A／B/(제목 없음)"
    assert locations["4"] == "SCRUM/A／B/(제목 없음)/．．"
    assert locations["5"] == "SCRUM/A／B/(제목 없음)/．．/．"


def test_missing_base_link_uses_site_setting_or_stops():
    pages = tree(("2", "가", "1"))
    listing, _ = _list(Scenario(pages=pages, base_link=False), site_base="https://other.invalid/wiki")
    assert listing.complete
    assert {i.source_id: i.url for i in listing.items}["2"] == "https://other.invalid/wiki/spaces/SCRUM/pages/2"
    listing, _ = _list(Scenario(pages=pages, base_link=False))
    assert not listing.complete and listing.items == () and listing.incomplete_reason == "site_base_missing"


def test_space_id_mismatch_stops_before_page_requests():
    listing, transport = _list(Scenario(space_id="999"))
    assert not listing.complete and listing.items == ()
    assert listing.incomplete_reason == "space_id_mismatch"
    assert listing.origin == SourceOrigin("999", "SCRUM", None)
    assert len(transport.requests) == 1


def test_personal_space_type_stops_before_page_requests():
    listing, transport = _list(Scenario(space_type="personal"))
    assert not listing.complete and listing.items == () and listing.incomplete_reason == "personal_space"
    assert len(transport.requests) == 1


def test_space_not_found():
    scenario = Scenario()
    scenario.override(f"{BASE}/spaces?keys=SCRUM", body={"results": [], "_links": {"base": SITE}})
    listing, _ = _list(scenario)
    assert not listing.complete and listing.incomplete_reason == "space_not_found"
    scenario.override(f"{BASE}/spaces?keys=SCRUM", status=404)
    listing, _ = _list(scenario)
    assert not listing.complete and listing.incomplete_reason == "space_not_found"


# ---- US4 분류(FR-020·FR-020a·FR-021a, research R-07) ----------------------------------------------


def _classified(pages, folders=(), **config_changes):
    listing, transport = _list(Scenario(pages=pages, folders=folders), config(**config_changes))
    return {item.source_id: item for item in listing.items}, transport


def test_exclusion_markers():
    pages = [
        *tree(
            ("10", "회의록", "1"),
            ("11", "2026-10-14 정기 회의", "10"),
            ("20", "기타", "1"),
            ("21", "기타 하위", "20"),
            ("30", "ADR", "1"),
            ("31", "옛 ADR", "30"),
            ("40", "설계 문서", "1"),
            ("41", "제외 트리 위", "40"),
            ("42", "제외 트리 아래", "41"),
        ),
        {"id": "99", "title": "홈 밖", "parent_id": None},
    ]
    items, _ = _classified(
        pages, doc_types={"10": "회의록", "30": "색인 안 함", "40": "설계 문서"}, exclude_trees=("41",)
    )
    assert {i: items[i].exclusion for i in items} == {
        "1": "space-home",
        "10": None,
        "11": None,
        "20": "unclassified",
        "21": "unclassified",
        "30": "not-indexed-type",
        "31": "not-indexed-type",
        "40": None,
        "41": "excluded-tree",
        "42": "excluded-tree",
        "99": "outside-home",
    }


def test_excluded_tree_by_folder_id():
    pages = tree(("50", "폴더 안", "f1", {"parent_type": "folder"}))
    folders = [{"id": "f1", "title": "폴더", "parent_id": "1"}]
    items, _ = _classified(pages, folders, doc_types={"f1": "설계 문서"}, exclude_trees=("f1",))
    assert items["50"].exclusion == "excluded-tree"
    items, _ = _classified(pages, folders, doc_types={"f1": "설계 문서"})
    assert items["50"].exclusion is None


def test_renaming_first_level_or_excluded_tree_keeps_classification():
    for first_title, tree_title in (("회의록", "제외"), ("이름 바뀐 회의록", "이름 바뀐 제외")):
        pages = tree(("10", first_title, "1"), ("11", "회의", "10"), ("12", tree_title, "10"), ("13", "아래", "12"))
        items, _ = _classified(pages, doc_types={"10": "회의록"}, exclude_trees=("12",))
        assert items["11"].exclusion is None
        assert items["12"].exclusion == items["13"].exclusion == "excluded-tree"


def test_doc_type_reaches_content_and_meeting_metadata():
    from qello_knowledge.sources.collect import fetch_contents
    from tests.unit.adapters.confluence_scenarios import doc, paragraph

    meeting_table = {
        "type": "table",
        "content": [
            {"type": "tableRow", "content": [
                {"type": "tableCell", "content": [paragraph("일시")]},
                {"type": "tableCell", "content": [paragraph("2026-10-14")]},
            ]},
        ],
    }  # fmt: skip
    pages = tree(("10", "회의록", "1"), ("11", "회의", "10", {"body": doc(meeting_table, paragraph("결정"))}))
    source_config = config(doc_types={"10": "회의록"})
    pages_adapter = adapter()
    transport = Scenario(pages=pages).transport()
    sess = session(pages_adapter, transport, source_config)
    listing = list_all(pages_adapter, source_config, sess)
    meeting_item = [i for i in listing.items if i.source_id == "11"]
    content = fetch_contents(pages_adapter, source_config, sess, meeting_item).contents[0]
    assert content.locator_extra["confluence"] == {
        "page_id": "11",
        "doc_type": "회의록",
        "meeting": {"date": "2026-10-14", "kind": None, "spec_ids": []},
    }


def test_site_setting_without_wiki_path_is_normalized():
    listing, _ = _list(Scenario(pages=tree(("2", "가", "1")), base_link=False), site_base="https://other.invalid")
    assert {i.source_id: i.url for i in listing.items}["2"] == "https://other.invalid/wiki/spaces/SCRUM/pages/2"
