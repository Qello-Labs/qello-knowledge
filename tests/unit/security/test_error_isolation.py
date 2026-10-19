"""판정 실패는 막는 쪽으로(FR-004, SC-007). 예외 난 자료만 ERROR이고 나머지는 판정된다."""

from qello_knowledge.domain.security import Verdict
from qello_knowledge.security import screen as screen_module
from qello_knowledge.security.kinds import KINDS, KindSecurityPolicy
from qello_knowledge.security.policy import SecurityPolicy


def _flaky_judge(access):
    raise KeyError("판정 중 오류 메시지는 기록에 남지 않는다")


def test_access_rule_error_blocks_only_that_kind(screen):
    broken = KindSecurityPolicy("fake", "broken", _flaky_judge, ("fake.invalid",), False)
    result, _ = screen("security_access", policy=SecurityPolicy(kinds={**KINDS, "fake": broken}))
    assert {v.verdict for v in result.verdicts} == {Verdict.ERROR}
    assert {v.error_type for v in result.verdicts} == {"KeyError"}
    assert result.passed == ()


def test_content_check_error_isolated_to_one_document(screen, monkeypatch):
    real = screen_module.find_secrets

    def explode_on_clean(text, skip=frozenset()):
        if text == "# Clean\n\nNothing to hide.":
            raise RuntimeError("x")
        return real(text, skip)

    monkeypatch.setattr(screen_module, "find_secrets", explode_on_clean)
    result, _ = screen("security_secrets")
    by_location = {v.location: v for v in result.verdicts}
    assert by_location["docs/clean.md"].verdict == Verdict.ERROR
    assert by_location["docs/clean.md"].error_type == "RuntimeError"
    assert "docs/clean.md" not in {p.item.location for p in result.passed}
    assert by_location["docs/placeholder.md"].verdict == Verdict.PASSED
    assert len(result.verdicts) == 9
    assert all("판정 중" not in repr(v) for v in result.verdicts)
