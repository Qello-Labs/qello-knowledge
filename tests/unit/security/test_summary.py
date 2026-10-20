"""실행 요약(FR-021, US4-1)."""

from qello_knowledge.domain.security import AccessScope, FilterSummary, SecurityVerdict, Stage, Verdict


def _v(verdict, stage, rule=None, scope=None, n=0):
    extra = {"error_type": "X"} if verdict == Verdict.ERROR else {}
    return SecurityVerdict("docs", str(n), f"docs/{n}.md", "https://fake.invalid", None, verdict, stage, "sec-x",
                           rule=rule, access_scope=scope, **extra)  # fmt: skip


def test_summary_counts_match_verdicts():
    verdicts = [
        *[_v(Verdict.PASSED, Stage.PASSED, "fake-visibility-v1", AccessScope.TEAM, n) for n in range(5)],
        _v(Verdict.PATH_EXCLUDED, Stage.PATH, "env-file", n=5),
        _v(Verdict.PATH_EXCLUDED, Stage.PATH, "infra-state", n=6),
        _v(Verdict.SECRET_BLOCKED, Stage.CONTENT_SECRET, "github-token", n=7),
        _v(Verdict.ACCESS_HELD, Stage.ACCESS, "fake-visibility-v1", AccessScope.UNKNOWN, n=8),
    ]
    summary = FilterSummary.from_verdicts("docs", "sec-x", verdicts)
    assert summary.to_dict() == {
        "source_name": "docs",
        "rules_version": "sec-x",
        "by_verdict": {"ACCESS_HELD": 1, "PASSED": 5, "PATH_EXCLUDED": 2, "SECRET_BLOCKED": 1},
        "by_rule": {"env-file": 1, "fake-visibility-v1": 6, "github-token": 1, "infra-state": 1},
        "by_access_scope": {"TEAM": 5, "UNKNOWN": 1},
    }
    assert sum(summary.by_verdict.values()) == len(verdicts)
