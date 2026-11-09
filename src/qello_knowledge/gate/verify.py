"""정책 이력 확인과 활성화 쪽 게이트 확인(QK-STO-002 research R-09·R-11, contracts/gate-record.md 5절).

저장소 git 이력은 `RepoHistory` 경계로만 읽는다. 활성화는 기록을 그대로 믿지 않고 같은 입력으로 다시 판정한다.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from qello_knowledge.evaluation.records import RecordError, read_record
from qello_knowledge.gate.judge import PASS, GateRequest, HistoryFacts, RecordInput, judge
from qello_knowledge.gate.policy import GatePolicy, load_policy
from qello_knowledge.gate.record import GateRecordError, judged_part, read_gate_record
from qello_knowledge.ports.history import RepoHistory

MAIN_REF = "origin/main"
_VERSION_FILE = re.compile(r"^v([1-9]\d*)\.toml$")


def load_record_input(repo_root: Path, path: str) -> RecordInput:
    full = repo_root / path
    try:
        raw = full.read_bytes()
    except OSError:
        return RecordInput(path, "", None)
    digest = hashlib.sha256(raw).hexdigest()
    try:
        record = read_record(full)
    except (RecordError, KeyError, TypeError, ValueError):
        record = None
    return RecordInput(path, digest, record)


def collect_history(
    policy: GatePolicy, records: Sequence[RecordInput], history: RepoHistory, main_ref: str = MAIN_REF
) -> HistoryFacts:
    merge = history.first_added_commit(main_ref, policy.path)
    on_main = history.file_at(main_ref, policy.path)
    matches = on_main is not None and hashlib.sha256(on_main).hexdigest() == policy.sha256
    directory = str(Path(policy.path).parent.as_posix())
    newer = False
    for path in history.list_paths(main_ref, directory):
        match = _VERSION_FILE.fullmatch(Path(path).name)
        if match and int(match.group(1)) > policy.version:
            newer = True
    contains: dict[str, bool | None] = {}
    for item in records:
        if item.record is None:
            continue
        sha = item.record.conditions.code_commit.sha
        contains[item.record.run_id] = None if sha is None or merge is None else history.is_ancestor(merge, sha)
    head, dirty = history.head()
    return HistoryFacts(main_ref, merge, matches, newer, contains, head, dirty)


@dataclass(frozen=True)
class VerifiedGate:
    gate_id: str
    sha256: str
    verdict: str
    baseline: str | None
    candidate_tokenizer: str | None
    search: Mapping[str, Any]
    covered_sources: tuple[str, ...]
    summary: Mapping[str, Any] = field(default_factory=dict)


def verify_for_activation(
    record_path: Path, *, active: str | None, target: str, history: RepoHistory, repo_root: Path
) -> tuple[VerifiedGate | None, tuple[str, ...]]:
    """활성화 조건 (6)의 게이트 쪽 확인. `(확인한 값, 실패 조건 이름들)`."""
    try:
        data, digest = read_gate_record(record_path)
    except GateRecordError:
        return None, ("gate_integrity",)
    failed: list[str] = []
    if data["verdict"] != PASS:
        failed.append("gate_verdict")
    if data["candidate"].get("index_version") != target:
        failed.append("gate_candidate")
    if data["baseline"].get("index_version") != active:
        failed.append("gate_baseline")
    policy_ref = data["policy"]
    policy, issues = load_policy(repo_root / policy_ref["path"], repo_path=policy_ref["path"])
    if policy is None or issues or policy.sha256 != policy_ref["sha256"]:
        return None, (*failed, "gate_integrity")
    records = [load_record_input(repo_root, run["path"]) for run in data["runs"]]
    if any(item.sha256 != run["sha256"] for item, run in zip(records, data["runs"], strict=True)):
        failed.append("gate_integrity")
    facts = collect_history(policy, records, history, MAIN_REF)
    if facts.policy_merge_commit is None or not facts.policy_matches_main or facts.newer_policy_on_main:
        failed.append("gate_policy")
    request = GateRequest(
        policy,
        tuple(records),
        data["baseline"].get("target"),
        data["candidate"].get("target"),
        active or "",
        target,
        facts,
    )
    outcome = judge(request)
    recorded = {key: data[key] for key in ("verdict", "violations", "sets")}
    if judged_part(outcome) != recorded and "gate_integrity" not in failed:
        failed.append("gate_integrity")
    verified = VerifiedGate(
        gate_id=data["gate_id"],
        sha256=digest,
        verdict=data["verdict"],
        baseline=data["baseline"].get("index_version"),
        candidate_tokenizer=data["candidate"].get("tokenizer"),
        search=dict(data["search"]),
        covered_sources=tuple(data["covered_sources"]),
        summary={
            "policy": {"id": policy.id, "version": policy.version},
            "embedding_model": data["candidate"].get("embedding_model"),
            "sets": [
                {
                    "id": s["id"],
                    "version": s["version"],
                    "judged": s["judged"],
                    "recall_at_5": s["metrics"]["recall_at_5"],
                    "mrr": s["metrics"]["mrr"],
                }
                for s in data["sets"]
            ],
        },
    )
    return verified, tuple(dict.fromkeys(failed))
