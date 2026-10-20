"""조립 함수 `screen_source`. 재생 전송의 요청 기록으로 추가 본문 조회 0건을 확인한다."""

import pytest

from qello_knowledge.domain.security import AccessScope, Stage, Verdict
from qello_knowledge.domain.source_config import SourceScope
from qello_knowledge.security.exceptions import SecretException
from qello_knowledge.security.kinds import KINDS
from qello_knowledge.security.policy import SecurityPolicy
from tests.unit.security.helpers import content_requests, fake_config, team_policy
from tests.unit.synthetic_secrets import SYNTHETIC


def _by_location(result):
    return {v.location: v for v in result.verdicts}


# --- US1: 비밀값 ---


def test_body_secret_blocks_the_whole_document(screen):
    result, _ = screen("security_secrets")
    verdict = _by_location(result)["docs/body-secret.md"]
    assert (verdict.verdict, verdict.stage, verdict.rule, verdict.field) == (
        Verdict.SECRET_BLOCKED,
        Stage.CONTENT_SECRET,
        "github-token",
        "body",
    )
    assert verdict.lines == (4,)
    assert "docs/body-secret.md" not in {p.item.location for p in result.passed}


def test_placeholder_and_clean_documents_pass_as_team(screen):
    result, _ = screen("security_secrets")
    passed = {p.item.location: p for p in result.passed}
    assert set(passed) == {"docs/clean.md", "docs/placeholder.md"}
    assert all(p.access_scope == AccessScope.TEAM for p in passed.values())


@pytest.mark.parametrize(
    ("source_id", "field", "rule"),
    [
        ("4", "location", "slack-token"),
        ("5", "title", "aws-access-key"),
        (SYNTHETIC["github-classic"], "source_id", "github-token"),
        ("9", "url", "openai-key"),
        ("intranet-qk.md", "source_id", "identifier-address"),
    ],
)
def test_item_metadata_is_blocked_before_any_content_request(screen, source_id, field, rule):
    result, transport = screen("security_secrets")
    verdict = next(v for v in result.verdicts if v.source_id == source_id)
    assert (verdict.verdict, verdict.stage, verdict.field, verdict.rule) == (
        Verdict.SECRET_BLOCKED,
        Stage.ITEM_SECRET,
        field,
        rule,
    )
    assert not [url for url in content_requests(transport) if url.endswith("/items/" + source_id)]


def test_fetch_failure_is_a_judgement_error(screen):
    result, _ = screen("security_secrets")
    verdict = _by_location(result)["docs/missing.md"]
    assert (verdict.verdict, verdict.stage, verdict.error_type) == (
        Verdict.ERROR,
        Stage.FETCH,
        "fetch:PERMANENT_FAILED:NOT_FOUND",
    )


def test_every_listed_item_gets_exactly_one_verdict_and_contents_are_cleared(screen):
    result, _ = screen("security_secrets")
    assert len(result.verdicts) == 9 == len({v.source_id for v in result.verdicts})
    assert sum(result.summary.by_verdict.values()) == 9
    assert result.fetch.contents == ()


def test_partial_listing_stays_incomplete(screen):
    result, _ = screen("security_partial")
    assert result.fetch.listing_complete is False
    assert [p.item.location for p in result.passed] == ["docs/a.md"]


@pytest.mark.parametrize("kind", sorted(SYNTHETIC))
def test_required_kind_in_body_is_blocked(screen, kind):
    result, _ = screen("security_one", secrets={"TARGET": SYNTHETIC[kind]})
    assert result.passed == ()
    assert result.verdicts[0].verdict == Verdict.SECRET_BLOCKED


def test_exception_scope_is_limited_to_its_own_source(screen):
    exception = SecretException("docs", "docs/body-secret.md", "github-token", "시험")
    policy = team_policy(exceptions=frozenset({exception}))
    own, _ = screen("security_secrets", policy=policy)
    other, _ = screen("security_secrets", policy=policy, config=fake_config(name="docs2"))
    assert _by_location(own)["docs/body-secret.md"].verdict == Verdict.PASSED
    assert _by_location(other)["docs/body-secret.md"].verdict == Verdict.SECRET_BLOCKED


# --- US2: 접근 범위 (SC-004) ---


def test_only_public_items_pass_and_held_items_are_never_fetched(screen):
    result, transport = screen("security_access", policy=SecurityPolicy())
    verdicts = _by_location(result)
    assert verdicts["docs/public.md"].verdict == Verdict.PASSED
    assert verdicts["docs/public.md"].access_raw == (("visibility", "public"),)
    assert verdicts["docs/public.md"].rule == "fake-visibility-v1"
    held = {loc: v for loc, v in verdicts.items() if loc != "docs/public.md"}
    assert {v.verdict for v in held.values()} == {Verdict.ACCESS_HELD}
    assert held["docs/restricted.md"].access_scope == AccessScope.RESTRICTED
    assert {held[k].access_scope for k in ("docs/private.md", "docs/none.md", "docs/odd.md")} == {AccessScope.UNKNOWN}
    assert all(v.stage == Stage.ACCESS and v.rule == "fake-visibility-v1" for v in held.values())
    assert content_requests(transport) == ["https://fake.invalid/items/1"]


def test_unregistered_kind_is_held_as_unknown(screen):
    result, transport = screen("security_access", policy=SecurityPolicy(kinds={}))
    assert {v.verdict for v in result.verdicts} == {Verdict.ACCESS_HELD}
    assert {v.access_scope for v in result.verdicts} == {AccessScope.UNKNOWN}
    assert {v.rule for v in result.verdicts} == {"unregistered-kind"}
    assert content_requests(transport) == []


# --- US3: 경로 제외 (SC-003) ---


def test_default_and_human_exclusions_never_fetch(screen):
    config = fake_config(scope=SourceScope(("**",), ("docs/people/**",)))
    result, transport = screen("security_paths", config=config)
    verdicts = _by_location(result)
    excluded = {loc: v for loc, v in verdicts.items() if v.verdict == Verdict.PATH_EXCLUDED}
    assert set(verdicts) - set(excluded) == {".env.example", "infra/prod.tfvars.example", "docs/ok.md"}
    assert all(v.stage == Stage.PATH for v in excluded.values())
    assert excluded["infra/terraform.tfstate.example"].rule == "infra-state"
    assert excluded["DOCS/People/x.md"].rule == "source-exclude"
    # 대소문자까지 같은 사람 지정 경로는 ING-001 list_all이 먼저 빼서 판정 기록이 없다.
    assert "docs/people/contacts.md" not in verdicts
    assert sorted(content_requests(transport)) == [
        "https://fake.invalid/items/e1",
        "https://fake.invalid/items/e2",
        "https://fake.invalid/items/ok",
    ]
    assert {p.item.location for p in result.passed} == {".env.example", "infra/prod.tfvars.example", "docs/ok.md"}


# --- 구현 리뷰 반영(2026-10-20) ---


def test_exception_never_releases_a_secret_identifier(screen, caplog):
    import json
    import logging

    caplog.set_level(logging.INFO)
    token = SYNTHETIC["github-classic"]
    exception = SecretException("docs", "docs/id.md", "github-token", "시험")
    result, transport = screen("security_secrets", policy=team_policy(exceptions=frozenset({exception})))
    verdict = next(v for v in result.verdicts if v.location == "docs/id.md")
    assert (verdict.verdict, verdict.field) == (Verdict.SECRET_BLOCKED, "source_id")
    assert token not in caplog.text + json.dumps(result.fetch.to_dict())
    assert not [u for u in content_requests(transport) if token in u]


def test_access_evidence_is_kept_after_the_access_stage(screen):
    result, _ = screen("security_secrets")
    verdicts = _by_location(result)
    for location in ("docs/body-secret.md", "docs/missing.md", "docs/title.md"):
        assert verdicts[location].access_scope == AccessScope.TEAM
        assert verdicts[location].access_raw == (("visibility", "public"),)
    assert result.summary.by_access_scope[AccessScope.TEAM] == 9


def test_listing_stop_is_kept(screen):
    from qello_knowledge.domain.source import StopReason

    result, _ = screen("security_listing_stop")
    assert result.fetch.listing_complete is False
    assert result.fetch.stop is not None and result.fetch.stop.reason == StopReason.WAIT_TOO_LONG


@pytest.mark.parametrize(
    ("scenario", "expected"),
    [
        ("security_exhausted", {"1": "fetch:TRANSIENT_EXHAUSTED:SERVER_ERROR"}),
        (
            "security_auth_failed",
            {"1": "fetch:SKIPPED:AUTH_FAILED", "2": "fetch:SKIPPED:none", "3": "fetch:SKIPPED:none"},
        ),
    ],
)
def test_every_fetch_failure_kind_is_a_judgement_error(screen, scenario, expected):
    result, _ = screen(scenario)
    errors = {v.source_id: v.error_type for v in result.verdicts if v.verdict == Verdict.ERROR}
    assert errors == expected
    assert len(result.verdicts) == len(result.fetch.items)


def test_content_with_unexpected_identifier_is_isolated():
    from dataclasses import replace as dc_replace

    from qello_knowledge.domain.source import ContentFormat, SourceContent
    from qello_knowledge.security.screen import screen_contents

    good = SourceContent("1", "# ok", ContentFormat.MARKDOWN, "v1", "docs/1.md", "t")
    orphan = dc_replace(good, source_id="orphan")
    item = _item_for("1")
    passed, verdicts = screen_contents([orphan, good], {"1": item}, fake_config(), team_policy())
    assert [p.item.source_id for p in passed] == ["1"]
    assert [v.verdict for v in verdicts] == [Verdict.PASSED]


def _item_for(source_id):
    from datetime import UTC, datetime

    from qello_knowledge.domain.source import AccessInfo, AccessStatus, ChangeKeyKind, SourceItem

    access = AccessInfo(AccessStatus.PROVIDED, (("visibility", "public"),))
    return SourceItem(
        "docs", "fake", source_id, f"https://fake.invalid/view/{source_id}", "v1", ChangeKeyKind.VERSION, "v1",
        datetime(2026, 1, 1, tzinfo=UTC), "markdown_file", "t", f"docs/{source_id}.md", None, access, None,
    )  # fmt: skip


# --- 구현 재리뷰 반영(2026-10-20) ---


def test_content_returned_under_another_listed_id_is_not_attributed_to_it(screen, monkeypatch):
    from dataclasses import replace as dc_replace

    from qello_knowledge.adapters.fake import FakeSourceAdapter

    real = FakeSourceAdapter.fetch_content

    def swapped(self, session, config, item):
        content = real(self, session, config, item)
        return dc_replace(content, source_id="1") if item.source_id == "2" else content

    monkeypatch.setattr(FakeSourceAdapter, "fetch_content", swapped)
    exception = SecretException("docs", "docs/clean.md", "github-token", "시험")
    result, _ = screen("security_secrets", policy=team_policy(exceptions=frozenset({exception})))
    assert "docs/body-secret.md" not in {p.item.location for p in result.passed}
    assert all(p.content.location == p.item.location for p in result.passed)
    assert len(result.verdicts) == 9 == len({v.source_id for v in result.verdicts})
    mismatch = next(v for v in result.verdicts if v.source_id == "2")
    assert (mismatch.verdict, mismatch.error_type) == (Verdict.ERROR, "fetch:SUCCEEDED:content-mismatch")


def test_metadata_check_error_after_access_keeps_evidence(screen, monkeypatch):
    from qello_knowledge.security import screen as screen_module

    real = screen_module.find_secrets

    def explode(text, skip=frozenset()):
        if text == "docs/clean.md":
            raise RuntimeError("x")
        return real(text, skip)

    monkeypatch.setattr(screen_module, "find_secrets", explode)
    result, _ = screen("security_secrets")
    verdict = _by_location(result)["docs/clean.md"]
    assert (verdict.verdict, verdict.stage, verdict.access_scope) == (
        Verdict.ERROR,
        Stage.ITEM_SECRET,
        AccessScope.TEAM,
    )
    assert verdict.access_raw == (("visibility", "public"),)
    assert sum(result.summary.by_access_scope.values()) == len(result.verdicts) == 9


def test_path_identifier_with_ip_next_to_dot_is_blocked_before_fetch():
    from qello_knowledge.security.screen import screen_items

    item = _item_for("x")
    item = type(item)(**{**item.__dict__, "source_id": "docs/file.2001:db8::1.md", "location": "docs/x.md"})
    path_kind = KINDS["fake"].__class__("fake", "test-all-team", lambda a: AccessScope.TEAM, ("fake.invalid",), True)
    policy = team_policy(kinds={"fake": path_kind})
    passed, verdicts = screen_items([item], fake_config(), policy)
    assert passed == ()
    assert (verdicts[0].field, verdicts[0].rule) == ("source_id", "identifier-address")
    assert "2001:db8" not in str(verdicts[0].to_dict(policy.output_context("fake")))
