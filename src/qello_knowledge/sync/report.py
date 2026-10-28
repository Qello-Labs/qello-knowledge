"""본문을 받지 않는 명시적 요약·출력 경계."""

from collections import Counter
from dataclasses import fields
from enum import Enum

from qello_knowledge.domain.redact import FieldKind, safe_text
from qello_knowledge.domain.sync import Action, DocumentOutcome
from qello_knowledge.security.policy import SecurityPolicy


def summary_values(value):
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict) or hasattr(value, "items"):
        return {str(k): summary_values(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [summary_values(v) for v in value]
    if hasattr(value, "__dataclass_fields__"):
        return {f.name: summary_values(getattr(value, f.name)) for f in fields(value)}
    return value


def source_summary(plan, execution):
    context = SecurityPolicy().output_context("unknown")
    origin = (
        None
        if plan.origin is None
        else {
            "origin_id": safe_text(plan.origin.origin_id, FieldKind.TEXT, context),
            "origin_name": safe_text(plan.origin.origin_name, FieldKind.TEXT, context),
        }
    )
    counts = Counter(action.value for doc, action, outcome in execution.outcomes)
    takedowns = Counter(
        doc.takedown_reason.value for doc, action, outcome in execution.outcomes if action == Action.TAKE_DOWN
    )
    failures = [
        {"doc_display": d.display, "stage": d.stage, "failure": d.failure}
        for d, a, o in execution.outcomes
        if o == DocumentOutcome.FAILED
    ]
    security = [
        {"doc_display": d.display, "reason": d.takedown_reason.value, "rule": d.rule, "lines": list(d.lines)}
        for d, a, o in execution.outcomes
        if a == Action.TAKE_DOWN and d.takedown_reason.is_security
    ]
    embedding = {
        "requested": 0,
        "cache_hits": 0,
        "deduplicated": 0,
        "provider_calls": 0,
        "neurons": 0.0,
        "estimated_neurons": 0.0,
        "failures": {},
        "warnings": [],
    }
    for summary in execution.embedding:
        for key in ("requested", "cache_hits", "deduplicated", "provider_calls", "neurons", "estimated_neurons"):
            embedding[key] += getattr(summary, key)
        embedding["failures"] = dict(Counter(embedding["failures"]) + Counter(summary.failures))
        embedding["warnings"] = list(dict.fromkeys([*embedding["warnings"], *summary.warnings]))
    status = "stopped" if execution.holds else "partial" if execution.failures else "succeeded"
    return dict(
        source_name=plan.source_name,
        mode=plan.mode,
        status=status,
        origin=origin,
        origin_version=safe_text(plan.origin_version, FieldKind.TEXT, context) if plan.origin_version else None,
        listing_complete=plan.listing_complete,
        stop_reason=plan.stop.reason.value if plan.stop else None,
        retry_at=plan.stop.retry_at.isoformat() if plan.stop and plan.stop.retry_at else None,
        holds=sorted(h.value for h in execution.holds),
        counts=dict(counts),
        takedowns=dict(takedowns),
        takedown_ratio=dict(plan.takedown_ratio),
        collection=dict(plan.fetch_summary),
        filter=plan.filter_summary.to_dict() if plan.filter_summary else {},
        chunking=summary_values(plan.chunking_summary),
        embedding=embedding,
        failures=failures,
        security_takedowns=security,
        # 아래 두 값은 채워졌을 때만 넣어 GitHub 요약의 키가 그대로이게 한다(QK-ING-003 data-model 10절).
        **({"incomplete_reason": plan.incomplete_reason} if plan.incomplete_reason else {}),
        **({"kind_summary": summary_values(plan.kind_summary)} if plan.kind_summary else {}),
    )


def run_dict(result):
    return {
        **result.summary,
        "run_id": result.run_id,
        "status": result.status,
        "exit_code": result.exit_code,
        "sources": list(result.sources),
    }


def preview_dict(result):
    return dict(
        preview=True,
        sources=list(result.sources),
        embedding_preview=summary_values(result.embedding_preview),
        runnable=result.runnable,
        **result.index_state,
    )


def render(result, disabled_sources=()):
    context = SecurityPolicy().output_context("unknown")
    lines = [f"status={result.status} exit_code={result.exit_code} run_id={result.run_id}"]
    reported = set()
    for source in result.sources:
        name = safe_text(source["source_name"], FieldKind.TEXT, context)
        reported.add(source["source_name"])
        counts = " ".join(f"{action}={count}" for action, count in sorted(source["counts"].items()))
        lines.append(f"{name}: status={source['status']} mode={source['mode']} {counts}".rstrip())
    for name in disabled_sources:
        if name not in reported:
            lines.append(f"{safe_text(name, FieldKind.TEXT, context)}: 비활성")
    return "\n".join(lines)
