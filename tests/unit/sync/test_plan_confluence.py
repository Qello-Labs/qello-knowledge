"""Confluence 계획 확장(QK-ING-003 FR-030·FR-031, research R-04·R-05, contracts/sync-security.md)."""

from qello_knowledge.domain.sync import Action, HoldReason, TakedownReason
from qello_knowledge.ports.sync import StoredDocument
from qello_knowledge.sync.plan import SyncTarget, plan_source
from qello_knowledge.sync.run import SyncOptions, current_spec
from tests.unit.adapters import confluence_scenarios as cf
from tests.unit.sync.helpers import harness


def stored(source_id, **changes):
    values = dict(
        artifact_id=int(source_id),
        source_id=source_id,
        source_name="confluence-scrum",
        source_kind="confluence_pages",
        location=f"SCRUM/문서 {source_id}",
        access_scope="team",
        status="active",
    )
    return StoredDocument(**(values | changes))


def plan(scenario, documents, *, confirm=False, doc_types=None, **adapter_changes):
    h = harness(docs={})
    # 홈 바로 아래 페이지를 모두 분류해 둔다. 미분류는 PATH 단계에서 빠지기 때문이다(US4).
    first = {page["id"]: "설계 문서" for page in scenario.pages if page.get("parent_id") == "1"}
    source_config = cf.config(doc_types=first if doc_types is None else doc_types)
    adapter = cf.adapter(**({"site_review_valid": False} | adapter_changes))
    transport = scenario.transport()
    target = SyncTarget(
        source_config.name,
        source_config.kind,
        config=source_config,
        adapter=adapter,
        session=cf.session(adapter, transport, source_config),
    )
    rows = {doc.source_id: doc for doc in documents}
    result = plan_source(target, h.deps, rows, current_spec(h.deps).id, SyncOptions(confirm_takedown=confirm))
    return result, transport


def decision(result, source_id):
    return next((d for d in result.decisions if d.source_id == source_id), None)


def _missing_requests(transport):
    return [r.url for r in transport.requests if "status=archived" in r.url]


def test_gone_page_is_security_takedown_not_general():
    scenario = cf.Scenario(pages=cf.tree()).missing("9", status=404)
    result, _ = plan(scenario, [stored("9")])
    found = decision(result, "9")
    assert Action.TAKE_DOWN in found.actions and found.takedown_reason == TakedownReason.SECURITY_ACCESS
    assert result.takedown_ratio["general"] == 0


def test_other_space_page_is_gone():
    scenario = cf.Scenario(pages=cf.tree()).missing("9", body={"id": "9", "status": "current", "spaceId": "555"})
    result, _ = plan(scenario, [stored("9")])
    assert decision(result, "9").takedown_reason == TakedownReason.SECURITY_ACCESS


def test_archived_page_is_general_source_missing():
    scenario = cf.Scenario(pages=cf.tree()).missing("9", body={"id": "9", "status": "archived", "spaceId": "100"})
    result, _ = plan(scenario, [stored("9")])
    assert decision(result, "9").takedown_reason == TakedownReason.SOURCE_MISSING


def test_present_page_is_kept_and_listing_marked_incomplete():
    scenario = cf.Scenario(pages=cf.tree()).missing("9", body={"id": "9", "status": "current", "spaceId": "100"})
    result, _ = plan(scenario, [stored("9")])
    assert decision(result, "9") is None
    assert HoldReason.COLLECTION_INCOMPLETE in result.holds
    assert result.listing_complete is False and result.incomplete_reason == "missing_check_present"


def test_uncertain_page_is_kept():
    scenario = cf.Scenario(pages=cf.tree())
    for _ in range(4):
        scenario.queue(f"{cf.BASE}/pages/9?{cf.STATUS_QUERY}", status=500)
    result, _ = plan(scenario, [stored("9")])
    assert decision(result, "9") is None
    assert HoldReason.COLLECTION_INCOMPLETE not in result.holds


def test_run_stop_during_check_keeps_pages_and_marks_incomplete():
    scenario = cf.Scenario(pages=cf.tree()).missing("8", status=401).missing("9", status=404)
    result, transport = plan(scenario, [stored("8"), stored("9")])
    assert decision(result, "8") is None and decision(result, "9") is None
    assert HoldReason.COLLECTION_INCOMPLETE in result.holds
    assert result.incomplete_reason == "missing_check_stopped"
    assert len(_missing_requests(transport)) == 1


def test_settled_access_takedown_is_not_checked_again():
    settled = stored("9", status="deleted", takedown_reason=TakedownReason.SECURITY_ACCESS, access_scope=None)
    result, transport = plan(cf.Scenario(pages=cf.tree()), [settled])
    assert decision(result, "9") is None
    assert _missing_requests(transport) == []


def _pages_with_failures(count, failures):
    pages = cf.tree(*[(str(n), f"문서 {n}", "1") for n in range(2, count + 1)])
    scenario = cf.Scenario(pages=pages)
    for page_id in failures:
        scenario.override(f"{cf.BASE}/pages/{page_id}/restriction-state", status=403)
    return scenario


def test_lookup_failures_over_threshold_hide_without_deleting_bodies():
    scenario = _pages_with_failures(11, ("2", "3"))  # 11개 중 2개 = 18%
    result, _ = plan(scenario, [stored("2"), stored("3"), stored("4")])
    for source_id in ("2", "3"):
        found = decision(result, source_id)
        assert Action.TAKE_DOWN in found.actions and found.takedown_reason == TakedownReason.SECURITY_ACCESS
        assert found.delete_bodies is False
    # 규칙상 미확인(기록 만료)인 "4"는 실패로 세지 않고 보통 보안 내림처럼 비율 검사의 삭제 수에 들어간다.
    assert decision(result, "4").takedown_reason == TakedownReason.SECURITY_ACCESS
    assert result.takedown_ratio["purge"] == 1 and HoldReason.TAKEDOWN_RATIO in result.holds
    assert HoldReason.COLLECTION_INCOMPLETE in result.holds
    assert result.listing_complete is False and result.incomplete_reason == "access_lookup_threshold"


def test_confirmed_run_does_not_purge_lookup_failed_pages():
    scenario = _pages_with_failures(11, ("2", "3"))
    pending = stored("2", status="deleted", takedown_reason=TakedownReason.SECURITY_ACCESS, purge_pending=("iv-old",))
    result, _ = plan(scenario, [pending, stored("3")], confirm=True)
    assert Action.PURGE not in decision(result, "2").actions
    assert decision(result, "2").delete_bodies is False


def test_lookup_failures_within_threshold_delete_bodies():
    scenario = _pages_with_failures(11, ("2",))  # 11개 중 1개 = 9%
    result, _ = plan(scenario, [stored("2")])
    assert result.incomplete_reason is None
    assert decision(result, "2").takedown_reason == TakedownReason.SECURITY_ACCESS


def test_listing_incomplete_reason_is_carried():
    result, _ = plan(cf.Scenario(space_type="personal"), [stored("9")])
    assert result.listing_complete is False and result.incomplete_reason == "personal_space"
    assert decision(result, "9") is None


def test_fingerprint_uses_extra_and_chunks_carry_confluence_locator():
    from qello_knowledge.sync.keys import chunk_input_hash

    pages = cf.tree(("2", "설계", "1", {"body": cf.doc(cf.paragraph("내용"))}))
    pages[0]["body"] = cf.doc(cf.paragraph("홈"))
    result, _ = plan(cf.Scenario(pages=pages), [], site_review_valid=True)
    found = decision(result, "2")
    assert found.chunked is not None
    for draft in found.chunked.drafts:
        assert draft.chunk.locator["confluence"] == {"page_id": "2", "doc_type": "설계 문서", "meeting": None}
        assert set(draft.chunk.locator) == {"path", "lines", "confluence"}
    from qello_knowledge.adapters.atlassian_adf import RULES_VERSION
    from qello_knowledge.domain.source import content_hash
    from qello_knowledge.sources.kinds import canonical_json

    digest = content_hash("# 설계\n\n내용\n")
    extra = canonical_json({"rules": RULES_VERSION, "doc_type": "설계 문서", "meeting": None})
    assert found.fingerprint == chunk_input_hash(digest, "SCRUM/설계", "설계", extra=extra)
    assert found.fingerprint != chunk_input_hash(digest, "SCRUM/설계", "설계")


def test_locator_key_conflict_is_an_error():
    import pytest

    from qello_knowledge.sync.plan import merge_locator

    with pytest.raises(ValueError):
        merge_locator({"path": "a", "lines": [1, 2]}, {"path": "b"})
    assert merge_locator({"path": "a"}, None) == {"path": "a"}


def test_secret_blocked_page_is_still_hidden_and_purged_when_lookups_fail():
    from tests.unit.synthetic_secrets import SYNTHETIC

    pages = cf.tree(*[(str(n), f"문서 {n}", "1", {"body": cf.doc(cf.paragraph(f"본문 {n}"))}) for n in range(2, 13)])
    pages[0]["body"] = cf.doc(cf.paragraph("홈"))
    pages[3]["body"] = cf.doc(cf.paragraph("토큰 " + SYNTHETIC["github-classic"]))  # 문서 4
    scenario = cf.Scenario(pages=pages)
    for page_id in ("2", "3"):  # 12개 중 2개 = 16.7%
        scenario.override(f"{cf.BASE}/pages/{page_id}/restriction-state", status=403)
    result, _ = plan(scenario, [stored(str(n)) for n in range(2, 13)], site_review_valid=True)
    assert result.incomplete_reason == "access_lookup_threshold"
    secret = decision(result, "4")
    assert secret.takedown_reason == TakedownReason.SECURITY_SECRET and secret.delete_bodies is True
    assert all(decision(result, i).delete_bodies is False for i in ("2", "3"))
    assert HoldReason.TAKEDOWN_RATIO not in result.holds and result.takedown_ratio["purge"] == 1


def test_incomplete_listing_keeps_bodies_of_cut_off_pages():
    pages = cf.tree(("2", "자식", "9"), ("9", "부모", "1"))
    scenario = cf.Scenario(pages=pages, page_size=2)
    url = cf.ROOT + "/wiki/api/v2/spaces/100/pages?status=current&limit=250&cursor=c1"
    for _ in range(4):
        scenario.queue(url, status=503)
    scenario.exchanges = [e for e in scenario.exchanges if not (e["url"] == url and e["responses"][0]["status"] == 200)]
    result, _ = plan(scenario, [stored("2")], doc_types={"9": "설계 문서"}, site_review_valid=True)
    found = decision(result, "2")
    assert found.takedown_reason == TakedownReason.SECURITY_ACCESS and found.delete_bodies is False
    assert result.listing_complete is False and result.incomplete_reason == "listing_failed"


def test_results_checked_before_a_run_stop_are_kept():
    scenario = cf.Scenario(pages=cf.tree()).missing("8", status=404).missing("9", status=401)
    result, _ = plan(scenario, [stored("8"), stored("9")])
    assert decision(result, "8").takedown_reason == TakedownReason.SECURITY_ACCESS
    assert decision(result, "9") is None
    assert result.incomplete_reason == "missing_check_stopped"
    assert result.kind_summary["missing_checks"] == {"GONE": 1, "NOT_CHECKED": 1}


TOC = {"type": "extension", "attrs": {"extensionKey": "toc"}}


def test_kind_summary_and_report_fields():
    from types import SimpleNamespace

    from qello_knowledge.sync.report import source_summary

    pages = cf.tree(
        ("2", "설계", "1", {"body": cf.doc(cf.paragraph("내용"), TOC)}),
        ("3", "그림만", "1", {"body": cf.doc({"type": "mediaSingle", "content": []})}),
        ("20", "미분류", "1"),
    )  # fmt: skip
    pages[0]["body"] = cf.doc(cf.paragraph("홈"))
    scenario = cf.Scenario(pages=pages)
    scenario.override(f"{cf.BASE}/pages/3/restriction-state", status=200, body={"state": "OPEN"})
    result, _ = plan(scenario, [], doc_types={"2": "설계 문서", "3": "설계 문서"}, site_review_valid=True)
    assert result.kind_summary == {
        "unclassified": 1,
        "access_lookup_failed": 0,
        "conversion_warnings": {"UNSUPPORTED_BLOCK": 1},
        "missing_checks": {},
        "empty_bodies": 1,
    }
    summary = source_summary(result, SimpleNamespace(outcomes=[], embedding=[], holds=set(), failures=0))
    assert summary["kind_summary"]["unclassified"] == 1 and "incomplete_reason" not in summary
