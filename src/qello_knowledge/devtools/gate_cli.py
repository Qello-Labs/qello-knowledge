"""`qk-dev eval gate`(QK-STO-002 contracts/cli.md 6절). DB·외부 호출 없이 정책과 실행 기록으로 판정한다(FR-019)."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from qello_knowledge.adapters.git_history import GitHistory
from qello_knowledge.gate.judge import FAIL, PASS, GateRequest, judge
from qello_knowledge.gate.policy import load_policy
from qello_knowledge.gate.record import new_gate_id, number, outcome_json, write_gate_record
from qello_knowledge.gate.verify import collect_history, load_record_input

EXIT = {PASS: 0, FAIL: 1}
EXIT_UNDECIDABLE, EXIT_ARGUMENT = 3, 2


def add_gate_parser(actions: argparse._SubParsersAction) -> argparse.ArgumentParser:
    gate = actions.add_parser("gate", help="인덱스 버전 평가 게이트 판정(QK-STO-002). DB·외부 호출 없음")
    gate.add_argument("--policy", type=Path, required=True, help="게이트 정책 파일(eval/gate_policies/<ID>/v<N>.toml)")
    gate.add_argument("--run", action="append", type=Path, required=True, help="QK-EVL-001 실행 기록(여러 번)")
    gate.add_argument("--baseline-target", required=True, help="실행 기록의 기준 평가 대상 이름")
    gate.add_argument("--candidate-target", required=True, help="실행 기록의 후보 평가 대상 이름")
    gate.add_argument("--baseline-version", required=True, help="운영 활성 인덱스 버전(qk-index index status의 active)")
    gate.add_argument("--candidate-version", required=True, help="후보 준비 인덱스 버전(current)")
    gate.add_argument("--out", required=True, help="게이트 기록 경로. {gate_id} 자리표시자를 받는다. 이미 있으면 거부")
    gate.add_argument("--main-ref", default="origin/main", help="정책 병합 확인에 쓸 참조(기본 origin/main)")
    return gate


def _relative(path: Path, root: Path) -> str | None:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return None


def _error(code: str) -> int:
    print(json.dumps({"exit_code": EXIT_ARGUMENT, "error": code}, ensure_ascii=False))
    return EXIT_ARGUMENT


def run_gate(
    args: argparse.Namespace,
    *,
    repo_root: Path | None = None,
    history_factory: Callable[[Path], object] = GitHistory,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> int:
    root = Path(repo_root or Path.cwd())
    policy_path = _relative(args.policy, root)
    if policy_path is None:
        return _error("policy_outside_repository")
    policy, issues = load_policy(args.policy, repo_path=policy_path)
    if policy is None:
        print(json.dumps({"exit_code": EXIT_ARGUMENT, "error": "policy_invalid", "issues": list(issues)}))
        return EXIT_ARGUMENT
    run_paths = []
    for run in args.run:
        rel = _relative(run, root)
        if rel is None:
            return _error("run_outside_repository")
        run_paths.append(rel)
    started = now()
    gate_id = new_gate_id(started)
    out = Path(args.out.replace("{gate_id}", gate_id))
    if out.exists():
        return _error("out_exists")
    records = tuple(load_record_input(root, rel) for rel in run_paths)
    history = history_factory(root)
    facts = collect_history(policy, records, history, args.main_ref)
    request = GateRequest(
        policy,
        records,
        args.baseline_target,
        args.candidate_target,
        args.baseline_version,
        args.candidate_version,
        facts,
    )
    outcome = judge(request)
    data = outcome_json(outcome, request, gate_id=gate_id, judged_at=started)
    out.parent.mkdir(parents=True, exist_ok=True)
    digest = write_gate_record(data, out)
    summary = {
        "gate_record": out.as_posix(),
        "gate_id": gate_id,
        "sha256": digest,
        "verdict": outcome.verdict,
        "undecidable_reasons": list(outcome.undecidable_reasons),
        "violations": data["violations"],
        "sets": [
            {
                "id": s.set_id,
                "judged": s.judged,
                **{
                    m.name: {"baseline": number(m.baseline), "candidate": number(m.candidate), "diff": number(m.diff)}
                    for m in s.metrics
                },
                "guardrails": [{"kind": g.kind, "value": number(g.value), "ok": g.ok} for g in s.guardrails],
                "regressions": len(s.regressions),
                "improvements": len(s.improvements),
            }
            for s in outcome.sets
        ],
    }
    if args.json:
        print(json.dumps(summary, ensure_ascii=False))
    else:
        print(f"gate={gate_id} verdict={outcome.verdict} record={out.as_posix()}")
        for item in summary["sets"]:
            print(
                f"{item['id']}: judged={item['judged']} recall@5 {item['recall_at_5']['baseline']}→"
                f"{item['recall_at_5']['candidate']} mrr {item['mrr']['baseline']}→{item['mrr']['candidate']}"
            )
        for reason in outcome.undecidable_reasons:
            print(f"undecidable: {reason}")
        for violation in data["violations"]:
            print(f"violation: {violation['set']} {violation['kind']} {violation['metric'] or ''}".rstrip())
    return EXIT.get(outcome.verdict, EXIT_UNDECIDABLE)
