"""Confluence 측정(QK-ING-003 FR-027, SC-004, research R-17). 재생 응답만 쓰고 저장·임베딩은 없다."""

import json
from datetime import UTC, datetime

from qello_knowledge.devtools.measure import (
    PreparedSource,
    measure_confluence,
    prepare_source,
    render_confluence_measurement,
)
from tests.unit.adapters import confluence_scenarios as cf
from tests.unit.sources.conftest import FakeClock

SOURCES = """[[source]]
name = "confluence-scrum"
kind = "confluence_pages"
enabled = false
auth = "ATLASSIAN_API_TOKEN"
allowed_hosts = ["api.atlassian.com"]
[source.scope]
include = ["**"]
space_key = "SCRUM"
space_id = "100"
judge_mode = "site_users"
doc_types = { "2" = "설계 문서", "5" = "설계 문서" }
"""

REVIEW = """source = "confluence-scrum"
reviewed_on = {day}
reviewer_role = "운영 담당"
method = "범위 페이지 열람"
result = "팀원 이름 외 개인 정보 없음"
team_member_names = "허용"
[scope]
include = ["**"]
space_key = "SCRUM"
space_id = "100"
judge_mode = "site_users"
doc_types = {{ "2" = "설계 문서", "5" = "설계 문서" }}
[site_users]
reviewed_on = {day}
user_count = 6
"""


def _prepared(tmp_path, review=True):
    sources = tmp_path / "sources.toml"
    sources.write_text(SOURCES, encoding="utf-8")
    reviews = tmp_path / "reviews"
    reviews.mkdir()
    if review:
        day = datetime.now(UTC).date().isoformat()
        (reviews / "confluence-scrum.toml").write_text(REVIEW.format(day=day), encoding="utf-8")
    return prepare_source("confluence-scrum", sources, reviews, tmp_path / "absent.toml")


TOC = {"type": "extension", "attrs": {"extensionKey": "toc"}}


def _scenario():
    pages = cf.tree(
        ("2", "설계 비밀 제목", "1", {"body": cf.doc(cf.paragraph("내용"), TOC)}),
        ("3", "미분류 제목", "1"),
        ("5", "조회 실패 제목", "1"),
    )  # fmt: skip
    pages[0]["body"] = cf.doc(cf.paragraph("홈"))
    scenario = cf.Scenario(pages=pages)
    scenario.override(f"{cf.BASE}/pages/5/restriction-state", status=403)
    return scenario


def test_disabled_source_is_measured_after_review(tmp_path):
    prepared = _prepared(tmp_path)
    assert isinstance(prepared, PreparedSource) and prepared.config.enabled
    assert prepared.context == {"site_review_valid": {"confluence-scrum": True}}


def test_disabled_source_without_review_is_rejected(tmp_path):
    issues = _prepared(tmp_path, review=False)
    assert ("review", "REVIEW_MISSING") in {(i.field, i.code) for i in issues}


def test_measurement_counts_without_titles_or_addresses(tmp_path):
    prepared = _prepared(tmp_path)
    adapter = cf.adapter(site_review_valid=prepared.context["site_review_valid"]["confluence-scrum"])
    measurement = measure_confluence(prepared, adapter, _scenario().transport(), FakeClock(), chunk=True)
    data = measurement.to_dict()
    assert data["pages"] == 4 and data["listing_complete"] is True
    assert data["unclassified"] == 1 and data["access_lookup_failed"] == 1
    assert data["bodies_fetched"] == 1 and data["total_bytes"] > 0
    assert data["conversion_warnings"] == {"UNSUPPORTED_BLOCK": 1}
    assert data["chunking"]["chunk_count"] >= 1 and data["chunking"]["estimated_neurons"] > 0
    assert set(data["requests_by_endpoint"]) >= {
        "GET /spaces 200",
        "GET /spaces/{id}/pages 200",
        "GET /pages/{id}/restriction-state 200",
        "GET /pages/{id}/restriction-state 403",
        "GET /pages/{id}?body 200",
    }
    for output in (json.dumps(data, ensure_ascii=False), render_confluence_measurement(measurement)):
        for secret in ("제목", "site.invalid", "cloud-test", "내용", "/pages/2", "acct-"):
            assert secret not in output
    assert json.loads(render_confluence_measurement(measurement, json_output=True)) == data
