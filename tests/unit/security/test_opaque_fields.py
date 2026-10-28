"""종류별 출력 규칙(QK-ING-003 research R-15). 기본값에서는 지금 판정 기록과 같다."""

from qello_knowledge.domain.security import AccessScope, SecurityVerdict, Stage, Verdict
from qello_knowledge.security.kinds import KINDS, KindSecurityPolicy, judge_fake_visibility
from qello_knowledge.security.policy import SecurityPolicy


def _verdict(verdict=Verdict.ACCESS_HELD, scope=AccessScope.UNKNOWN):
    return SecurityVerdict(
        "docs",
        "123",
        "SPACE/회의록/2026-10-14 정기 회의",
        "https://site.invalid/wiki/spaces/SPACE/pages/123",
        "2026-10-14 정기 회의",
        verdict,
        Stage.ACCESS if verdict == Verdict.ACCESS_HELD else Stage.PASSED,
        "sec-test",
        access_scope=scope,
    )


def test_new_kind_fields_default_off():
    spec = KindSecurityPolicy("x", "x-v1", judge_fake_visibility, (), False)
    assert spec.opaque_item_fields is False
    assert spec.lookup_failure_threshold is None
    assert all(
        not k.opaque_item_fields and k.lookup_failure_threshold is None
        for k in KINDS.values()
        if k.kind != "confluence_pages"
    )


def test_opaque_kind_blanks_title_location_and_url_for_every_verdict():
    kinds = dict(KINDS) | {"opaque": KindSecurityPolicy("opaque", "o-v1", judge_fake_visibility, (), False, True)}
    policy = SecurityPolicy(kinds=kinds)
    context = policy.output_context("opaque")
    assert context.opaque_item_fields is True
    for verdict, scope in ((Verdict.ACCESS_HELD, AccessScope.UNKNOWN), (Verdict.PASSED, AccessScope.TEAM)):
        record = _verdict(verdict, scope).to_dict(context)
        assert record["title"] is None and record["location"] is None and record["url"] is None
        assert record["source_id"] == "123"


def test_github_record_is_unchanged():
    policy = SecurityPolicy()
    context = policy.output_context("github_repo_files")
    assert context.opaque_item_fields is False
    record = _verdict().to_dict(context)
    assert record["title"] is not None and record["location"] is not None


def test_policy_version_is_unchanged_without_new_kind_values():
    kinds = {k: v for k, v in KINDS.items() if k in {"github_repo_files", "fake"}}
    same = {
        k: KindSecurityPolicy(v.kind, v.rule_name, v.judge, v.public_link_hosts, v.source_id_is_path)
        for k, v in kinds.items()
    }
    assert SecurityPolicy(kinds=kinds).version == SecurityPolicy(kinds=same).version
    opaque = dict(same) | {
        "fake": KindSecurityPolicy("fake", "fake-visibility-v1", judge_fake_visibility, ("fake.invalid",), False, True)
    }
    assert SecurityPolicy(kinds=opaque).version != SecurityPolicy(kinds=same).version
