"""보안 규칙 점검 출력. 예외 항목의 경로와 사유는 출력하지 않고 항목 번호·필드·오류 코드만 보인다."""

from __future__ import annotations

import json
from pathlib import Path

from qello_knowledge.security.exceptions import PolicyIssue
from qello_knowledge.security.policy import SecurityPolicy


def security_report(path: Path, policy: SecurityPolicy | None, issues: tuple[PolicyIssue, ...]) -> dict:
    report = {"file": str(path), "ok": not issues, "issues": [{"where": _where(i), "code": i.code} for i in issues]}
    if policy is not None:
        report |= {
            "rules_version": policy.version,
            "secret_rules": len(policy.rules),
            "exclusion_categories": len({e.category for e in policy.exclusions}) + 1,  # path-invalid 포함
            "exceptions": len(policy.exceptions),
            "access_rules": {kind: spec.rule_name for kind, spec in policy.kinds.items()},
        }
    return report


def _where(issue: PolicyIssue) -> str:
    return issue.field if issue.entry is None else f"exception[{issue.entry}].{issue.field}"


def render_security_report(report: dict, json_output: bool = False) -> str:
    if json_output:
        return json.dumps(report, ensure_ascii=False)
    lines = ["보안 규칙 점검: " + report["file"]]
    if report["ok"]:
        rules = ", ".join(f"{kind}={name}" for kind, name in report["access_rules"].items())
        lines += [
            f"  규칙 버전   {report['rules_version']}",
            f"  비밀값 규칙 {report['secret_rules']}개, 기본 제외 범주 {report['exclusion_categories']}개, "
            f"예외 {report['exceptions']}건",
            f"  접근 규칙   {rules}",
            "결과: 통과",
        ]
    else:
        lines += [f"  실패  {issue['where']}  {issue['code']}" for issue in report["issues"]]
        lines.append(f"결과: 실패 (오류 {len(report['issues'])})")
    return "\n".join(lines)
