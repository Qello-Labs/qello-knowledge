"""Confluence 개인 정보 확인 기록(QK-ING-003 FR-021·FR-025·FR-025a·FR-012, data-model 3절, SC-007).

기록은 합성 값만 쓰고 시험 안에서 임시 폴더에 만든다(파일 이름이 자료원 이름과 같아야 한다).
"""

from datetime import date, timedelta
from hashlib import sha256

import pytest

from qello_knowledge.sources.config import load_sources
from qello_knowledge.sources.scope_review import check_scope, confluence_review_context, load_checked_sources

SOURCES = """[[source]]
name = "confluence-scrum"
kind = "confluence_pages"
enabled = {enabled}
auth = "ATLASSIAN_API_TOKEN"
[source.scope]
include = ["**"]
space_key = "SCRUM"
space_id = "12345"
judge_mode = "site_users"
doc_types = {{ "111" = "회의록" }}
exclude_trees = ["333"]
"""

REVIEW = """source = "confluence-scrum"
reviewed_on = 2026-11-01
reviewer_role = "운영 담당"
method = "범위 페이지 열람"
result = "{result}"
{names}
[scope]
include = ["**"]
space_key = "SCRUM"
space_id = "12345"
judge_mode = "site_users"
doc_types = {{ "111" = "회의록" }}
exclude_trees = ["333"]
{site}
{moved}
"""

SITE = """[site_users]
reviewed_on = {day}
user_count = 6
"""


def _setup(tmp_path, *, enabled=True, result="팀원 이름 외 개인 정보 없음", names=True, site=True, moved="", day=None,
           review_text=None):  # fmt: skip
    sources = tmp_path / "sources.toml"
    sources.write_text(SOURCES.format(enabled="true" if enabled else "false"), encoding="utf-8")
    reviews = tmp_path / "reviews"
    reviews.mkdir()
    text = review_text or REVIEW.format(
        result=result,
        names='team_member_names = "허용"' if names else "",
        site=SITE.format(day=day or "2026-11-01") if site else "",
        moved=moved,
    )
    (reviews / "confluence-scrum.toml").write_text(text, encoding="utf-8")
    return sources, reviews


def _codes(tmp_path, **kwargs):
    sources, reviews = _setup(tmp_path, **kwargs)
    _, issues = load_checked_sources(sources, reviews)
    return {(issue.field, issue.code) for issue in issues}


def test_valid_review_passes(tmp_path):
    assert _codes(tmp_path) == set()


def test_missing_review_for_enabled_source(tmp_path):
    sources, reviews = _setup(tmp_path)
    (reviews / "confluence-scrum.toml").unlink()
    _, issues = load_checked_sources(sources, reviews)
    assert {(i.field, i.code) for i in issues} == {("review", "REVIEW_MISSING")}


def test_disabled_source_needs_no_review(tmp_path):
    sources, reviews = _setup(tmp_path, enabled=False)
    (reviews / "confluence-scrum.toml").unlink()
    _, issues = load_checked_sources(sources, reviews)
    assert issues == ()


def test_team_member_names_permission_is_required(tmp_path):
    assert ("review.team_member_names", "REVIEW_INVALID") in _codes(tmp_path, names=False)


def test_site_users_record_is_required_in_site_users_mode(tmp_path):
    assert ("review.site_users", "REVIEW_INVALID") in _codes(tmp_path, site=False)


@pytest.mark.parametrize("result", ["개인 정보 없음", "개인 정보 경로 제외함", "기타"])
def test_github_result_values_are_not_accepted(tmp_path, result):
    assert ("review.result", "REVIEW_INVALID") in _codes(tmp_path, result=result)


def test_moved_trees_must_be_listed_in_exclude_trees(tmp_path):
    good = '[[moved_to_exclude]]\nid = "333"\nreason = "연락처가 적힌 페이지"\n'
    assert _codes(tmp_path, result="개인 정보 트리 제외함", moved=good) == set()


def test_moved_tree_not_in_config_is_mismatch(tmp_path):
    bad = '[[moved_to_exclude]]\nid = "444"\nreason = "연락처"\n'
    assert ("review.moved_to_exclude[0]", "REVIEW_SCOPE_MISMATCH") in _codes(
        tmp_path, result="개인 정보 트리 제외함", moved=bad
    )


def test_tree_exclusion_result_requires_moved_rows(tmp_path):
    assert ("review.moved_to_exclude", "REVIEW_INVALID") in _codes(tmp_path, result="개인 정보 트리 제외함")


def test_scope_difference_is_mismatch(tmp_path):
    sources, reviews = _setup(tmp_path)
    text = (
        (reviews / "confluence-scrum.toml").read_text(encoding="utf-8").replace('"111" = "회의록"', '"111" = "용어집"')
    )
    (reviews / "confluence-scrum.toml").write_text(text, encoding="utf-8")
    _, issues = load_checked_sources(sources, reviews)
    assert ("review.scope", "REVIEW_SCOPE_MISMATCH") in {(i.field, i.code) for i in issues}


def test_names_and_mail_keys_are_rejected(tmp_path):
    sources, reviews = _setup(tmp_path)
    path = reviews / "confluence-scrum.toml"
    path.write_text('reviewer_name = "팀원A"\n' + path.read_text(encoding="utf-8"), encoding="utf-8")
    _, issues = load_checked_sources(sources, reviews)
    assert ("review", "REVIEW_INVALID") in {(i.field, i.code) for i in issues}
    assert "팀원A" not in str(issues)


def test_review_context_for_site_users(tmp_path):
    sources, reviews = _setup(tmp_path, day="2026-11-01")
    configs, _ = load_sources(sources)
    digest = sha256((reviews / "confluence-scrum.toml").read_bytes()).hexdigest()
    valid, material = confluence_review_context(configs, reviews, today=date(2026, 11, 1) + timedelta(days=90))
    assert valid == {"confluence-scrum": True}
    assert material == {"confluence-scrum": "site_users:" + digest}
    valid, _ = confluence_review_context(configs, reviews, today=date(2026, 11, 1) + timedelta(days=91))
    assert valid == {"confluence-scrum": False}


def test_review_context_ignores_disabled_sources(tmp_path):
    sources, reviews = _setup(tmp_path, enabled=False)
    configs, _ = load_sources(sources)
    assert confluence_review_context(configs, reviews, today=date(2026, 11, 2)) == ({}, {})


def test_github_reviews_are_unchanged():
    configs, _ = load_sources(__import__("pathlib").Path("config/sources.toml"))
    github = [c for c in configs if c.kind == "github_repo_files"]
    assert check_scope(github, __import__("pathlib").Path("config/source_reviews")) == ()


def test_future_site_review_date_is_not_valid(tmp_path):
    sources, reviews = _setup(tmp_path, day="2026-12-01")
    configs, _ = load_sources(sources)
    valid, _ = confluence_review_context(configs, reviews, today=date(2026, 11, 1))
    assert valid == {"confluence-scrum": False}
