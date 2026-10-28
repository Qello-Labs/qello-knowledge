"""US3 본문(QK-ING-003 FR-013, contracts/confluence-adapter.md `fetch_content`, data-model 6절)."""

import json

from qello_knowledge.adapters.atlassian_adf import RULES_VERSION
from qello_knowledge.domain.source import ContentFormat, FailureType, ItemStatus
from qello_knowledge.security.policy import SecurityPolicy
from qello_knowledge.security.screen import screen_source
from qello_knowledge.sources.collect import fetch_contents, list_all
from tests.unit.adapters.confluence_scenarios import BASE, Scenario, adapter, config, doc, paragraph, session, tree


def _fetch(scenario, source_config=None):
    source_config = source_config or config()
    pages_adapter = adapter()
    transport = scenario.transport()
    sess = session(pages_adapter, transport, source_config)
    listing = list_all(pages_adapter, source_config, sess)
    result = fetch_contents(pages_adapter, source_config, sess, listing.items)
    return listing, result, transport


def test_body_is_converted_with_metadata_fields():
    pages = tree(("2", "설계", "1", {"body": doc(paragraph("내용"))}))
    _, result, transport = _fetch(Scenario(pages=[{**pages[0], "body": doc(paragraph("홈"))}, pages[1]]))
    content = {c.source_id: c for c in result.contents}["2"]
    assert content.content_format == ContentFormat.MARKDOWN
    assert content.body == "# 설계\n\n내용\n"
    assert content.title == "설계" and content.location == "SCRUM/설계" and content.version == "1"
    assert content.locator_extra == {"confluence": {"page_id": "2", "doc_type": None, "meeting": None}}
    assert json.loads(content.fingerprint_extra) == {"doc_type": None, "meeting": None, "rules": RULES_VERSION}
    assert content.conversion_warnings == ()
    assert content.content_hash and content.fetched_at is not None
    assert f"{BASE}/pages/2?body-format=atlas_doc_format" in [r.url for r in transport.requests]


def test_oversized_body_fails_only_that_page():
    big = doc(paragraph("가" * 2000))
    pages = tree(("2", "큰 문서", "1", {"body": big}), ("3", "작은 문서", "1", {"body": doc(paragraph("짧음"))}))
    pages[0]["body"] = doc(paragraph("홈"))
    _, result, _ = _fetch(Scenario(pages=pages), config(max_content_bytes=3000))
    outcomes = {o.source_id: o for o in result.items}
    assert outcomes["2"].status == ItemStatus.PERMANENT_FAILED and outcomes["2"].failure == FailureType.SIZE_EXCEEDED
    assert outcomes["3"].status == ItemStatus.SUCCEEDED


def test_non_doc_body_is_invalid_response():
    pages = tree(("2", "이상한 본문", "1", {"body": {"type": "paragraph"}}))
    pages[0]["body"] = doc(paragraph("홈"))
    _, result, _ = _fetch(Scenario(pages=pages))
    outcome = {o.source_id: o for o in result.items}["2"]
    assert outcome.status == ItemStatus.PERMANENT_FAILED and outcome.failure == FailureType.INVALID_RESPONSE


def test_pages_not_passing_access_are_never_fetched():
    pages = tree(
        ("2", "막힌 문서", "1", {"restriction": "VIEW_RESTRICTED", "body": doc(paragraph("비밀"))}),
        ("3", "열린 문서", "1", {"body": doc(paragraph("공개"))}),
    )
    pages[0]["body"] = doc(paragraph("홈"))
    source_config = config(doc_types={"2": "설계 문서", "3": "설계 문서"})
    pages_adapter = adapter()
    transport = Scenario(pages=pages).transport()
    result = screen_source(
        pages_adapter, source_config, session(pages_adapter, transport, source_config), SecurityPolicy()
    )
    assert [s.item.source_id for s in result.passed] == ["3"]
    fetched = [r.url for r in transport.requests if "body-format" in r.url]
    assert fetched == [f"{BASE}/pages/3?body-format=atlas_doc_format"]


def test_unexpected_conversion_error_fails_only_that_page(monkeypatch):
    import qello_knowledge.adapters.confluence as module

    real = module.convert_adf

    def flaky(adf, **kwargs):
        if kwargs["title"] == "깨진 문서":
            raise TypeError("x")
        return real(adf, **kwargs)

    monkeypatch.setattr(module, "convert_adf", flaky)
    pages = tree(
        ("2", "깨진 문서", "1", {"body": doc(paragraph("가"))}),
        ("3", "멀쩡한 문서", "1", {"body": doc(paragraph("나"))}),
    )
    pages[0]["body"] = doc(paragraph("홈"))
    _, result, _ = _fetch(Scenario(pages=pages))
    outcomes = {o.source_id: o for o in result.items}
    assert outcomes["2"].status == ItemStatus.PERMANENT_FAILED and outcomes["2"].failure == FailureType.INVALID_RESPONSE
    assert outcomes["3"].status == ItemStatus.SUCCEEDED
