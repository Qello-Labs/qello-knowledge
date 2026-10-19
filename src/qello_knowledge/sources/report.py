"""검증된 범위와 필드·오류 코드만 출력한다."""

import json
from pathlib import Path

from qello_knowledge.domain.source_config import SourceConfig
from qello_knowledge.sources.config import UNKNOWN_KIND_MESSAGE, ConfigIssue


def source_report(path: Path, configs: tuple[SourceConfig, ...], issues: tuple[ConfigIssue, ...]) -> dict:
    sources = []
    for config in configs:
        found = [i for i in issues if i.source == config.name]
        row = {
            "name": config.name,
            "kind": config.kind,
            "enabled": config.enabled,
            "status": "INVALID" if found else "OK" if config.enabled else "DISABLED",
        }
        if found:
            row["issues"] = [{"field": i.field, "code": i.code} for i in found]
        elif config.enabled:
            row["scope"] = dict(config.scope.extra) | {
                "include": list(config.scope.include),
                "exclude": list(config.scope.exclude),
            }
        sources.append(row)
    report = {"file": str(path), "ok": not issues, "sources": sources}
    unassigned = [i for i in issues if not any(config.name == i.source for config in configs)]
    if unassigned:
        report["issues"] = [{"field": i.field, "code": i.code} for i in unassigned]
    return report


def render_report(report: dict, json_output: bool = False) -> str:
    if json_output:
        return json.dumps(report, ensure_ascii=False)
    lines = ["자료원 설정 점검: " + report["file"]]
    active = disabled = error_count = 0
    for row in report["sources"]:
        status = row["status"]
        disabled += not row["enabled"]
        active += row["enabled"]
        label = {"OK": "OK", "DISABLED": "비활성", "INVALID": "실패"}[status]
        detail = ""
        if status == "INVALID":
            detail = ", ".join(i["code"] + " " + i["field"] for i in row["issues"])
            error_count += len(row["issues"])
            if any(i["code"] == "UNKNOWN_KIND" for i in row["issues"]):
                detail += " " + UNKNOWN_KIND_MESSAGE
        elif status == "OK":
            scope = row["scope"]
            detail = " ".join(f"{k}={v}" for k, v in scope.items() if k not in {"include", "exclude"})
            detail += f" include={len(scope['include'])} exclude={len(scope['exclude'])}"
        lines.append(f"  {label:<8} {row['name']}  {row['kind']}  {detail}".rstrip())
    for issue in report.get("issues", []):
        lines.append(f"  실패 {issue['code']} {issue['field']}")
        error_count += 1
    result = "통과" if report["ok"] else "실패"
    lines.append(f"결과: {result} (활성 {active}, 비활성 {disabled}, 오류 {error_count})")
    return "\n".join(lines)
