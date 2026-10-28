"""응답 분류(QK-ING-003 FR-026, SC-008, research R-16). 공통 기본 분류를 그대로 쓴다."""

from qello_knowledge.domain.source import FailureType, ItemStatus, StopReason
from qello_knowledge.sources.collect import fetch_contents, list_all
from tests.unit.adapters.confluence_scenarios import BASE, Scenario, adapter, config, doc, paragraph, session, tree
from tests.unit.sources.conftest import FakeClock


def _run(scenario, clock=None):
    source_config = config()
    pages_adapter = adapter()
    transport = scenario.transport()
    sess = session(pages_adapter, transport, source_config, clock)
    listing = list_all(pages_adapter, source_config, sess)
    return listing, fetch_contents(pages_adapter, source_config, sess, listing.items), transport


def _pages():
    pages = tree(("2", "가", "1", {"body": doc(paragraph("가"))}), ("3", "나", "1", {"body": doc(paragraph("나"))}))
    pages[0]["body"] = doc(paragraph("홈"))
    return pages


def test_rate_limit_is_transient_and_waits_for_retry_after():
    scenario = Scenario(pages=_pages())
    url = f"{BASE}/spaces/100/pages?status=current&limit=250"
    first = scenario.exchanges.pop(next(i for i, e in enumerate(scenario.exchanges) if e["url"] == url))
    scenario.queue(url, status=429, headers={"Retry-After": "7"})
    scenario.exchanges[-1]["responses"].extend(first["responses"])
    clock = FakeClock()
    listing, _, _ = _run(scenario, clock)
    assert listing.complete and 7 in clock.sleeps


def test_auth_failure_stops_the_source_without_further_requests():
    scenario = Scenario(pages=_pages())
    scenario.override(f"{BASE}/spaces?keys=SCRUM", status=401)
    listing, result, transport = _run(scenario)
    assert listing.stop is not None and listing.stop.reason == StopReason.AUTH_FAILED
    assert len(transport.requests) == 1 and listing.items == ()
    assert result.contents == ()


def test_one_page_access_denied_fails_only_that_page():
    scenario = Scenario(pages=_pages())
    scenario.override(f"{BASE}/pages/2?body-format=atlas_doc_format", status=403)
    _, result, _ = _run(scenario)
    outcomes = {o.source_id: o for o in result.items}
    assert outcomes["2"].status == ItemStatus.PERMANENT_FAILED and outcomes["2"].failure == FailureType.ACCESS_DENIED
    assert outcomes["3"].status == ItemStatus.SUCCEEDED


def test_listing_denied_is_incomplete():
    scenario = Scenario(pages=_pages())
    scenario.override(f"{BASE}/spaces/100/pages?status=current&limit=250", status=403)
    listing, _, _ = _run(scenario)
    assert not listing.complete and listing.incomplete_reason == "listing_failed"
