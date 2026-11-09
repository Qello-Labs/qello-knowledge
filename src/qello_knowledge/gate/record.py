"""게이트 기록 `qk-sto-002-gate/v1`(QK-STO-002 contracts/gate-record.md, research R-11).

판정 하나에 JSON 파일 하나다. 질문 문장·핵심 사실·라벨 근거 낱말·검색어·청크 본문·접속 정보는 담지 않는다(SC-007).
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction
from pathlib import Path
from typing import Any

from qello_knowledge.gate.judge import GateOutcome, GateRequest, GuardrailResult, MetricCompare, SetResult, TargetInfo

SCHEMA = "qk-sto-002-gate/v1"
LIMITS = ("evaluates the index version settings on a local eval target, not production data",)
PARTIAL_SUFFIX = ".partial"


class GateRecordError(ValueError):
    """기록 파일이 계약과 다르다. 문구에 값이 없다."""


def new_gate_id(now: datetime, token: str | None = None) -> str:
    return f"gate-{now:%Y%m%dT%H%M%SZ}-{token or secrets.token_hex(4)}"


def number(value: Fraction) -> str:
    exact = Decimal(value.numerator) / Decimal(value.denominator)
    return str(exact.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def fraction_text(value: Fraction, denominator: int) -> str:
    numerator = value * denominator
    head = str(numerator.numerator) if numerator.denominator == 1 else number(numerator)
    return f"{head}/{denominator}"


def _metric(m: MetricCompare) -> dict[str, Any]:
    return {
        "baseline": number(m.baseline),
        "candidate": number(m.candidate),
        "diff": number(m.diff),
        "baseline_fraction": fraction_text(m.baseline, m.judged),
        "candidate_fraction": fraction_text(m.candidate, m.judged),
        "max_drop": number(m.max_drop),
        "ok": m.ok,
    }


def _guard(g: GuardrailResult) -> dict[str, Any]:
    return {
        "kind": g.kind,
        "mode": g.mode,
        "judged": g.judged,
        "baseline": number(g.baseline),
        "candidate": number(g.candidate),
        "value": number(g.value),
        "limit": number(g.limit),
        "ok": g.ok,
    }


def set_json(s: SetResult) -> dict[str, Any]:
    return {
        "id": s.set_id,
        "version": s.set_version,
        "judged": s.judged,
        "excluded": [{"question": q, "reason": r} for q, r in s.excluded],
        "metrics": {m.name: _metric(m) for m in s.metrics},
        "guardrails": [_guard(g) for g in s.guardrails],
        "new_failures": list(s.new_failures),
        "regressions": list(s.regressions),
        "improvements": list(s.improvements),
    }


def _target(t: TargetInfo) -> dict[str, Any]:
    return {
        "target": t.target,
        "index_version": t.index_version,
        "expected_index_version": t.expected_index_version,
        "embedding_model": t.embedding_model,
        "tokenizer": t.tokenizer,
        "index_rule": t.index_rule,
    }


def judged_part(outcome: GateOutcome) -> dict[str, Any]:
    """활성화가 다시 판정해 비교하는 부분(contracts/gate-record.md 5절)."""
    return {
        "verdict": outcome.verdict,
        "violations": [{"set": v.set, "kind": v.kind, "mode": v.mode, "metric": v.metric} for v in outcome.violations],
        "sets": [set_json(s) for s in outcome.sets],
    }


def outcome_json(outcome: GateOutcome, request: GateRequest, *, gate_id: str, judged_at: datetime) -> dict[str, Any]:
    policy, history = request.policy, request.history
    runs = []
    for item in request.records:
        record = item.record
        runs.append(
            {
                "run_id": record.run_id if record else None,
                "path": item.path,
                "sha256": item.sha256,
                "code_commit": None
                if record is None
                else {"sha": record.conditions.code_commit.sha, "dirty": record.conditions.code_commit.dirty},
                "set": None
                if record is None
                else {
                    "id": record.conditions.question_set.id,
                    "version": record.conditions.question_set.version,
                    "fingerprint": record.conditions.question_set.fingerprint,
                },
            }
        )
    return {
        "schema": SCHEMA,
        "gate_id": gate_id,
        "judged_at": judged_at.isoformat().replace("+00:00", "Z"),
        **judged_part(outcome),
        "undecidable_reasons": list(outcome.undecidable_reasons),
        "policy": {
            "id": policy.id,
            "version": policy.version,
            "path": policy.path,
            "sha256": policy.sha256,
            "merge_commit": history.policy_merge_commit,
            "main_ref": history.main_ref,
        },
        "baseline": _target(outcome.baseline),
        "candidate": _target(outcome.candidate),
        "runs": runs,
        "query_vectors_differ": outcome.query_vectors_differ,
        "mode": policy.mode,
        "search": dict(policy.search),
        "judged_counts": dict(outcome.judged_counts),
        "covered_sources": list(outcome.covered_sources),
        "judge_commit": {"sha": history.judge_commit, "dirty": history.judge_dirty},
        "limits": list(LIMITS),
    }


def dumps(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def write_gate_record(data: dict[str, Any], path: Path) -> str:
    """기록을 쓰고 파일 SHA-256을 돌려준다. 이미 있는 경로에는 쓰지 않는다."""
    if path.exists():
        raise FileExistsError(str(path))
    text = dumps(data)
    partial = path.with_name(path.name + PARTIAL_SUFFIX)
    partial.write_text(text, encoding="utf-8")
    os.replace(partial, path)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


TOP_KEYS = frozenset(
    {
        "schema",
        "gate_id",
        "judged_at",
        "verdict",
        "undecidable_reasons",
        "violations",
        "policy",
        "baseline",
        "candidate",
        "runs",
        "query_vectors_differ",
        "mode",
        "search",
        "sets",
        "judged_counts",
        "covered_sources",
        "judge_commit",
        "limits",
    }
)


def read_gate_record(path: Path) -> tuple[dict[str, Any], str]:
    """`(기록, 파일 SHA-256)`. 형식이 다르면 `GateRecordError`."""
    try:
        raw = path.read_bytes()
        data = json.loads(raw.decode("utf-8"))
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise GateRecordError("게이트 기록을 읽을 수 없다") from exc
    if not isinstance(data, dict) or data.get("schema") != SCHEMA or set(data) != TOP_KEYS:
        raise GateRecordError("게이트 기록 형식이 다르다")
    return data, hashlib.sha256(raw).hexdigest()
