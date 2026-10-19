"""조립 함수 `screen_source`. 재생 전송의 요청 기록으로 추가 본문 조회 0건을 확인한다."""

import pytest

from qello_knowledge.domain.security import AccessScope, Stage, Verdict
from qello_knowledge.domain.source_config import SourceScope
from qello_knowledge.security.exceptions import SecretException
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
