"""게이트 판정(QK-STO-002 FR-015~FR-017, research R-10). 정책·실행 기록·이력 사실만 받는 순수 함수다.

지표 정의는 QK-EVL-001과 같다(`OK_STATUSES`, `MRR_CUTOFF`). 판정 질문은 기준 대상에서 정상인 지표 대상 질문이고,
후보에서 정상이 아니면 놓침(Recall@5 0, 역순위 0)으로 센다. 가드레일도 같은 질문 집합으로 계산한다.
외부 호출과 DB 접근이 없다(FR-019).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from fractions import Fraction

from qello_knowledge.evaluation.metrics import MRR_CUTOFF, OK_STATUSES, SKIPPED, is_identifier_set
from qello_knowledge.evaluation.records import SCHEMA as RUN_SCHEMA
from qello_knowledge.evaluation.records import QuestionResult, RunRecord, TargetRecord
from qello_knowledge.gate.policy import GatePolicy, Guardrail, SetRule

PASS, FAIL, UNDECIDABLE = "pass", "fail", "undecidable"


@dataclass(frozen=True)
class RecordInput:
    path: str
    sha256: str
    record: RunRecord | None  # 읽기·스키마 실패면 None


@dataclass(frozen=True)
class HistoryFacts:
    main_ref: str
    policy_merge_commit: str | None
    policy_matches_main: bool
    newer_policy_on_main: bool
    record_contains_policy: Mapping[str, bool | None]  # 실행 ID → 코드 커밋이 병합 커밋을 포함하는지(없으면 None)
    judge_commit: str | None = None
    judge_dirty: bool = False


@dataclass(frozen=True)
class GateRequest:
    policy: GatePolicy
    records: tuple[RecordInput, ...]
    baseline_target: str
    candidate_target: str
    baseline_version: str
    candidate_version: str
    history: HistoryFacts


@dataclass(frozen=True)
class MetricCompare:
    name: str
    baseline: Fraction
    candidate: Fraction
    judged: int
    max_drop: Fraction
    ok: bool

    @property
    def diff(self) -> Fraction:
        return self.candidate - self.baseline


@dataclass(frozen=True)
class GuardrailResult:
    kind: str
    mode: str
    judged: int
    baseline: Fraction
    candidate: Fraction
    value: Fraction
    limit: Fraction
    ok: bool


@dataclass(frozen=True)
class SetResult:
    set_id: str
    set_version: int
    judged: int
    excluded: tuple[tuple[str, str], ...]
    metrics: tuple[MetricCompare, ...]
    guardrails: tuple[GuardrailResult, ...]
    new_failures: tuple[str, ...]
    regressions: tuple[str, ...]
    improvements: tuple[str, ...]


@dataclass(frozen=True)
class Violation:
    set: str
    kind: str
    mode: str
    metric: str | None


@dataclass(frozen=True)
class TargetInfo:
    target: str
    index_version: str | None
    expected_index_version: str
    embedding_model: str | None
    tokenizer: str | None
    index_rule: str | None


@dataclass(frozen=True)
class GateOutcome:
    verdict: str
    undecidable_reasons: tuple[str, ...]
    violations: tuple[Violation, ...]
    sets: tuple[SetResult, ...]
    judged_counts: Mapping[str, int]
    query_vectors_differ: bool
    covered_sources: tuple[str, ...]
    baseline: TargetInfo
    candidate: TargetInfo
    used_records: tuple[RecordInput, ...] = field(default_factory=tuple)


def normal(result: QuestionResult | None) -> bool:
    return result is not None and result.status in OK_STATUSES and not result.omitted


def _rank(result: QuestionResult | None) -> int | None:
    return result.first_evidence_rank if normal(result) else None


def _exclusion(result: QuestionResult | None) -> str:
    if result is None:
        return "baseline_failed:missing"
    if result.status == SKIPPED:
        return "baseline_skipped"
    if result.status not in OK_STATUSES:
        return f"baseline_failed:{result.status}"
    return "baseline_omitted"


def _target(record: RunRecord, name: str) -> TargetRecord | None:
    return next((t for t in record.targets if t.database == name), None)


def _results(record: RunRecord, target: str, mode: str) -> dict[str, QuestionResult]:
    return {r.question: r for r in record.results if r.target == target and r.mode == mode}


def _conditions(record: RunRecord, target: TargetRecord) -> dict:
    c = record.conditions
    return {
        "question_set": (c.question_set.id, c.question_set.version, c.question_set.fingerprint),
        "commits": tuple(sorted(target.commits.items())),
        "query_rule": c.query_rule,
        "candidates": c.candidates,
        "rrf_k": c.rrf_k,
        "filters": (tuple(c.filters.source_kinds), tuple(c.filters.artifact_kinds)),
    }


@dataclass
class _Pair:
    rule: SetRule
    base_record: RunRecord
    cand_record: RunRecord
    base_target: TargetRecord
    cand_target: TargetRecord


def _judged(pair: _Pair, mode: str, baseline: str) -> tuple[list[str], list[tuple[str, str]]]:
    base = _results(pair.base_record, baseline, mode)
    judged, excluded = [], []
    for q in pair.base_record.questions:
        if not q.metric_target:
            continue
        if normal(base.get(q.id)):
            judged.append(q.id)
        else:
            excluded.append((q.id, _exclusion(base.get(q.id))))
    return judged, excluded


def _recall_mrr(ranks: Sequence[int | None], n: int) -> tuple[Fraction, Fraction]:
    recall = Fraction(sum(1 for k in ranks if k is not None and k <= 5), n)
    mrr = sum((Fraction(1, k) for k in ranks if k is not None and k <= MRR_CUTOFF), Fraction(0)) / n
    return recall, mrr


def _precision(result: QuestionResult | None) -> Fraction:
    if not normal(result):
        return Fraction(0)
    return Fraction(sum(1 for h in result.top5 if h.evidence), 5)


def _cap(result: QuestionResult | None, candidates: int, *, failed_is_cap: bool) -> bool:
    if not normal(result):
        return failed_is_cap  # 후보 실패는 후보에게 가장 나쁜 값(research R-10)
    return result.result_count >= candidates


def _guardrail(guard: Guardrail, pair: _Pair, request: GateRequest, judged_main: list[str]) -> GuardrailResult | None:
    if guard.kind == "G1":
        cand = _results(pair.cand_record, request.candidate_target, guard.mode)
        failures = [q for q in judged_main if not normal(cand.get(q))]
        value = Fraction(len(failures))
        ok = value <= guard.limit
        return GuardrailResult("G1", guard.mode, len(judged_main), Fraction(0), value, value, guard.limit, ok)
    judged, _ = _judged(pair, guard.mode, request.baseline_target)
    if not judged:
        return None
    base = _results(pair.base_record, request.baseline_target, guard.mode)
    cand = _results(pair.cand_record, request.candidate_target, guard.mode)
    n = len(judged)
    if guard.kind == "G2":
        b = sum((_precision(base[q]) for q in judged), Fraction(0)) / n
        c = sum((_precision(cand.get(q)) for q in judged), Fraction(0)) / n
        value = b - c
    else:
        k = pair.base_record.conditions.candidates
        b = Fraction(sum(_cap(base[q], k, failed_is_cap=False) for q in judged), n)
        c = Fraction(sum(_cap(cand.get(q), k, failed_is_cap=True) for q in judged), n)
        value = c - b
    return GuardrailResult(guard.kind, guard.mode, n, b, c, value, guard.limit, value <= guard.limit)


def _info(name: str, expected: str, target: TargetRecord | None) -> TargetInfo:
    if target is None:
        return TargetInfo(name, None, expected, None, None, None)
    return TargetInfo(name, target.index_version, expected, target.embedding_model, target.tokenizer, target.index_rule)


def judge(request: GateRequest) -> GateOutcome:
    policy, history = request.policy, request.history
    reasons: set[str] = set()
    if history.policy_merge_commit is None:
        reasons.add("policy_unmerged")
    if not history.policy_matches_main:
        reasons.add("policy_changed")
    records = []
    for item in request.records:
        record = item.record
        if record is None or record.schema != RUN_SCHEMA:
            reasons.add("record_schema")
            continue
        records.append((item, record))
        if not record.complete:
            reasons.add("record_incomplete")
        commit = record.conditions.code_commit
        if commit.sha is None:
            reasons.add("code_commit_unknown")
        elif history.policy_merge_commit is not None and history.record_contains_policy.get(record.run_id) is not True:
            # 병합 커밋이 없으면 이 비교를 할 수 없다(사유는 policy_unmerged 하나).
            reasons.add("code_before_policy")
        if commit.dirty:
            reasons.add("dirty_code")
        c = record.conditions
        if (c.query_rule, c.candidates, c.rrf_k) != (
            policy.search["query_rule"],
            policy.search["candidates"],
            policy.search["rrf_k"],
        ):
            reasons.add("search_settings_mismatch")

    pairs: list[_Pair] = []
    vectors_differ = False
    base_target_rec = cand_target_rec = None
    used: list[RecordInput] = []
    for rule in policy.sets:
        same_id = [(i, r) for i, r in records if r.conditions.question_set.id == rule.id]
        matching = [(i, r) for i, r in same_id if r.conditions.question_set.version == rule.version]
        if not matching:
            reasons.add("set_mismatch" if same_id else "set_missing")
            continue
        with_base = [(i, r) for i, r in matching if _target(r, request.baseline_target)]
        with_cand = [(i, r) for i, r in matching if _target(r, request.candidate_target)]
        if len(with_base) > 1 or len(with_cand) > 1:
            reasons.add("set_duplicate")
            continue
        if not with_base or not with_cand:
            reasons.add("target_missing")
            continue
        (bi, base_record), (ci, cand_record) = with_base[0], with_cand[0]
        for item, record in {id(bi): (bi, base_record), id(ci): (ci, cand_record)}.values():
            used.append(item)
            if not record.conditions.question_set.confirmed:
                reasons.add("set_unconfirmed")
            if record.conditions.question_set.fingerprint != rule.fingerprint:
                reasons.add("set_mismatch")
        base_target = _target(base_record, request.baseline_target)
        cand_target = _target(cand_record, request.candidate_target)
        base_target_rec, cand_target_rec = base_target, cand_target
        if base_target.index_version != request.baseline_version:
            reasons.add("index_version_mismatch")
        if cand_target.index_version != request.candidate_version:
            reasons.add("index_version_mismatch")
        if "unknown" in (base_target.index_rule, cand_target.index_rule):
            reasons.add("index_rule_unknown")
        if base_target.tokenizer != policy.baseline_tokenizer or cand_target.tokenizer != policy.candidate_tokenizer:
            reasons.add("tokenizer_mismatch")
        if _conditions(base_record, base_target) != _conditions(cand_record, cand_target):
            reasons.add("condition_mismatch")
        if base_record.conditions.embedding_model != cand_record.conditions.embedding_model:
            # 다른 실행 기록이고 두 인덱스 버전의 임베딩 모델이 다를 때만 허용한다(FR-015 (4)).
            if base_record is not cand_record and base_target.embedding_model != cand_target.embedding_model:
                vectors_differ = True
            else:
                reasons.add("condition_mismatch")
        modes = {policy.mode, *(g.mode for g in policy.guardrails if g.set == rule.id)}
        for record in (base_record, cand_record):
            if not modes <= set(record.conditions.modes):
                reasons.add("mode_missing")
        for guard in policy.guardrails:
            if guard.set == rule.id and guard.kind == "G2" and not is_identifier_set(base_record):
                reasons.add("guardrail_set_kind")
        pairs.append(_Pair(rule, base_record, cand_record, base_target, cand_target))

    judged_counts: dict[str, int] = {}
    set_results: list[SetResult] = []
    violations: list[Violation] = []
    computable = not (reasons & {"mode_missing", "record_schema"})
    if computable:
        for pair in pairs:
            judged, excluded = _judged(pair, policy.mode, request.baseline_target)
            judged_counts[pair.rule.id] = len(judged)
            if len(judged) < pair.rule.min_judged or not judged:
                reasons.add("too_few_judged")
                continue
            base = _results(pair.base_record, request.baseline_target, policy.mode)
            cand = _results(pair.cand_record, request.candidate_target, policy.mode)
            base_ranks = [_rank(base[q]) for q in judged]
            cand_ranks = [_rank(cand.get(q)) for q in judged]
            n = len(judged)
            (br, bm), (cr, cm) = _recall_mrr(base_ranks, n), _recall_mrr(cand_ranks, n)
            metrics = []
            for name, b, c in (("recall_at_5", br, cr), ("mrr", bm, cm)):
                drop = pair.rule.max_drop[name]
                metrics.append(MetricCompare(name, b, c, n, drop, c - b >= -drop))
            guards = []
            for guard in policy.guardrails:
                if guard.set != pair.rule.id:
                    continue
                if guard.kind == "G2" and not is_identifier_set(pair.base_record):
                    continue  # 이미 guardrail_set_kind로 판정 불가다
                result = _guardrail(guard, pair, request, judged)
                if result is None:
                    reasons.add("too_few_judged")
                    continue
                guards.append(result)
            hit = [((b or 99) <= 5, (c or 99) <= 5) for b, c in zip(base_ranks, cand_ranks, strict=True)]
            regressions = tuple(q for q, (b, c) in zip(judged, hit, strict=True) if b and not c)
            improvements = tuple(q for q, (b, c) in zip(judged, hit, strict=True) if c and not b)
            new_failures = tuple(q for q in judged if not normal(cand.get(q)))
            set_results.append(
                SetResult(
                    pair.rule.id,
                    pair.rule.version,
                    n,
                    tuple(excluded),
                    tuple(metrics),
                    tuple(guards),
                    new_failures,
                    regressions,
                    improvements,
                )
            )
            violations += [Violation(pair.rule.id, "metric", policy.mode, m.name) for m in metrics if not m.ok]
            violations += [Violation(pair.rule.id, g.kind, g.mode, None) for g in guards if not g.ok]

    covered = sorted({name for _, r in records for name in r.conditions.label_commits})
    baseline = _info(request.baseline_target, request.baseline_version, base_target_rec)
    candidate = _info(request.candidate_target, request.candidate_version, cand_target_rec)
    if reasons:
        return GateOutcome(
            UNDECIDABLE,
            tuple(sorted(reasons)),
            (),
            (),
            judged_counts,
            vectors_differ,
            tuple(covered),
            baseline,
            candidate,
            tuple(used),
        )
    return GateOutcome(
        FAIL if violations else PASS,
        (),
        tuple(violations),
        tuple(set_results),
        judged_counts,
        vectors_differ,
        tuple(covered),
        baseline,
        candidate,
        tuple(used),
    )
