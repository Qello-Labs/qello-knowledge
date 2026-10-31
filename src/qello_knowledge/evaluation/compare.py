"""비교 조건 검사, 공통 질문 집합, Markdown 표(QK-EVL-001 spec FR-024·FR-025, US4-2~US4-6, research R-11).

- 비교 조건(세트 ID·버전·파일 지문, 자료원별 고정 커밋, 임베딩 모델, 질의 쪽 규칙, 후보 수, RRF 상수, 검색 필터)이
  하나라도 다르면 다른 항목 이름과 기록별 값을 모아 거부한다. 미완료 기록은 받지 않는다(FR-021).
- 공통 질문 집합: 방식마다 모든 대상에서 지표 대상이고, 실패·근거 미색인이 아니며(`no_results`는 남김),
  하이브리드 생략이 없는 질문.
- 벡터 전용 결과 지문이 대상 사이에 다른 질문은 "벡터 순위 다름"으로 표시한다.
표에는 질문 문장·검색어 낱말·청크 본문이 없다. 질문 ID와 수치만 있다.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from qello_knowledge.evaluation.metrics import BREAKDOWN_KEYS, MetricSet, Ratio, is_identifier_set, metric_set
from qello_knowledge.evaluation.records import QuestionResult, RunRecord

HYBRID_NOTE = (
    "하이브리드 차이는 벡터 전용 결과 지문이 후보 사이에 같은 질문에서만 키워드 규칙의 효과로 읽는다. "
    "벡터 순위 다름 질문은 원인 확인 대상(근사 색인 등)이다."
)
DIFFERENT_RUNS_NOTE = (
    "질의 벡터 다름: 서로 다른 실행의 기록이라 질의 벡터가 같지 않다. "
    "벡터 전용·하이브리드 차이를 키워드 규칙의 효과로 읽지 않는다."
)
RECALL_NOTE = "Recall@5는 근거 문서 가운데 하나라도 상위 5건에 든 질문의 비율이다(Hit@5와 같다)."
OK_STATUSES = ("ok", "no_results")


@dataclass(frozen=True)
class ConditionMismatch:
    item: str
    values: tuple[tuple[str, Any], ...]  # (실행 ID, 값)


class ComparisonRefused(Exception):  # noqa: N818 - 비교 거부
    def __init__(self, mismatches: Sequence[ConditionMismatch] = (), incomplete: Sequence[str] = ()) -> None:
        self.mismatches = tuple(mismatches)
        self.incomplete = tuple(incomplete)
        super().__init__("비교 조건이 맞지 않는다")


@dataclass(frozen=True)
class CommonSet:
    questions: tuple[str, ...]
    excluded: tuple[tuple[str, str], ...]  # (질문 ID, 사유)


@dataclass(frozen=True)
class ComparisonTable:
    columns: tuple[tuple[tuple[str, str], str], ...]  # ((실행 ID, 데이터베이스), 표 이름)
    candidates: Mapping[str, str]  # 표 이름 → 후보
    modes: tuple[str, ...]
    identifier_set: bool
    candidates_limit: int
    target_metrics: Mapping[tuple[str, str], MetricSet]  # 대상별 지표(공통 집합 아님, US3)
    metrics: Mapping[tuple[str, str], MetricSet]  # 공통 질문 집합 지표
    common: Mapping[str, CommonSet]
    vector_differs: tuple[str, ...]
    different_runs: bool
    breakdown_source: Mapping[str, Any] = field(default_factory=dict)


def _conditions(record: RunRecord, targets: Iterable[str]) -> dict[str, Any]:
    c = record.conditions
    commits = {}
    for t in record.targets:
        if t.database in targets:
            commits[t.database] = dict(t.commits)
    unique = {tuple(sorted(v.items())) for v in commits.values()}
    return {
        "question_set": (c.question_set.id, c.question_set.version, c.question_set.fingerprint),
        "commits": unique.pop() if len(unique) == 1 else tuple(sorted(unique)),
        "embedding_model": c.embedding_model,
        "query_rule": c.query_rule,
        "candidates": c.candidates,
        "rrf_k": c.rrf_k,
        "filters": (tuple(c.filters.source_kinds), tuple(c.filters.artifact_kinds)),
    }


def compare_conditions(
    records: Sequence[RunRecord], targets: Mapping[str, Sequence[str]]
) -> tuple[ConditionMismatch, ...]:
    values = [(r.run_id, _conditions(r, targets[r.run_id])) for r in records]
    mismatches = []
    for item in values[0][1]:
        seen = [(run_id, v[item]) for run_id, v in values]
        if len({repr(v) for _, v in seen}) > 1:
            mismatches.append(ConditionMismatch(item, tuple(seen)))
    return tuple(mismatches)


def _failure(item: QuestionResult) -> str | None:
    if item.status == "skipped":
        return "skipped"
    if item.status not in OK_STATUSES:
        return item.status
    if item.omitted:
        return "omitted:" + ",".join(o.reason for o in item.omitted)
    return None


def build_comparison(records: Sequence[RunRecord], targets: Sequence[str] | None = None) -> ComparisonTable:
    """실행 기록 하나 이상의 대상들을 공통 질문 집합으로 나란히 둔다. 조건이 다르면 `ComparisonRefused`."""
    incomplete = [r.run_id for r in records if not r.complete]
    if incomplete:
        raise ComparisonRefused(incomplete=incomplete)
    selected = {r.run_id: [t.database for t in r.targets if not targets or t.database in targets] for r in records}
    mismatches = compare_conditions(records, selected)
    if mismatches:
        raise ComparisonRefused(mismatches)
    keys = [(r.run_id, name) for r in records for name in selected[r.run_id]]
    names = [name for _, name in keys]
    label = {k: (k[1] if names.count(k[1]) == 1 else f"{k[1]}@{k[0]}") for k in keys}
    candidate = {
        label[(r.run_id, t.database)]: t.candidate
        for r in records
        for t in r.targets
        if (r.run_id, t.database) in label
    }
    first = records[0]
    modes = tuple(m for m in first.conditions.modes if all(m in r.conditions.modes for r in records))
    identifier = is_identifier_set(first)
    limit = first.conditions.candidates
    metric_ids = [q.id for q in first.questions if q.metric_target]
    by_key: dict[tuple[str, str, str], dict[str, QuestionResult]] = {}
    for record in records:
        for item in record.results:
            by_key.setdefault((record.run_id, item.target, item.mode), {})[item.question] = item
    common: dict[str, CommonSet] = {}
    target_metrics: dict[tuple[str, str], MetricSet] = {}
    common_metrics: dict[tuple[str, str], MetricSet] = {}
    for mode in modes:
        kept, excluded = [], []
        for qid in metric_ids:
            reasons = []
            for key in keys:
                item = by_key.get((*key, mode), {}).get(qid)
                reason = "missing" if item is None else _failure(item)
                if reason is not None:
                    reasons.append(f"{reason} ({label[key]})")
            if reasons:
                excluded.append((qid, "; ".join(reasons)))
            else:
                kept.append(qid)
        common[mode] = CommonSet(tuple(kept), tuple(excluded))
        for key in keys:
            items = list(by_key.get((*key, mode), {}).values())
            target_metrics[(label[key], mode)] = metric_set(
                first.questions, items, mode=mode, candidates=limit, identifier_set=identifier
            )
            subset = [q for q in first.questions if q.id in kept]
            common_metrics[(label[key], mode)] = metric_set(
                subset, [i for i in items if i.question in kept], mode=mode, candidates=limit, identifier_set=identifier
            )
    vector_differs: list[str] = []
    if "vector" in modes and len(keys) > 1:
        for qid in metric_ids:
            digests = {by_key.get((*key, "vector"), {}).get(qid) for key in keys}
            values = {d.result_digest for d in digests if d is not None and d.status == "ok"}
            if len(values) > 1:
                vector_differs.append(qid)
    return ComparisonTable(
        columns=tuple((k, label[k]) for k in keys),
        candidates=candidate,
        modes=modes,
        identifier_set=identifier,
        candidates_limit=limit,
        target_metrics=target_metrics,
        metrics=common_metrics,
        common=common,
        vector_differs=tuple(vector_differs),
        different_runs=len(records) > 1,
        breakdown_source={"questions": first.questions, "by_key": by_key, "keys": keys, "label": label},
    )


def _cell(ratio: Ratio | None) -> str:
    return "해당 없음" if ratio is None else f"{ratio.fraction_text()}={ratio.text()}"


def _counts(values: Mapping[str, int]) -> str:
    return ", ".join(f"{k} {v}" for k, v in sorted(values.items())) or "-"


def _metric_row(name: str, mode: str, m: MetricSet) -> str:
    cells = [
        name,
        mode,
        _cell(m.recall_at_5),
        _cell(m.mrr),
        _cell(m.top20),
        _cell(m.precision_at_5),
        _cell(m.mean_results),
        _cell(m.cap_hit),
        _counts(m.excluded),
        _counts(m.failures),
        _counts(m.omitted),
        str(m.zero_terms),
    ]
    return "| " + " | ".join(cells) + " |"


_HEADER = (
    "| 대상 | 방식 | Recall@5 | MRR | 상위 20건 | Precision@5 "
    "| 평균 결과 수 | 상한 도달 | 제외 | 실패 | 생략 | 낱말 0개 |\n"
    "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"
)


def render_tables(table: ComparisonTable, breakdowns: Sequence[str] = ()) -> str:
    """`qk-dev eval tables` 출력. 리포트 4절에 그대로 붙인다."""
    lines = ["## 대상별", "", _HEADER]
    for _, name in table.columns:
        for mode in table.modes:
            lines.append(_metric_row(f"{name}({table.candidates[name]})", mode, table.target_metrics[(name, mode)]))
    lines += ["", RECALL_NOTE]
    if len(table.columns) > 1:
        lines += ["", "## 비교(공통 질문 집합)", "", _HEADER]
        for mode in table.modes:
            for _, name in table.columns:
                lines.append(_metric_row(f"{name}({table.candidates[name]})", mode, table.metrics[(name, mode)]))
        lines += ["", "### 공통 질문 집합", ""]
        for mode in table.modes:
            common = table.common[mode]
            lines.append(f"- {mode}: {len(common.questions)}문항, 뺀 질문 {len(common.excluded)}")
            lines += [f"  - {qid}: {reason}" for qid, reason in common.excluded]
        lines += ["", "벡터 순위 다름: " + (", ".join(table.vector_differs) or "없음"), "", HYBRID_NOTE]
        if table.different_runs:
            lines += ["", DIFFERENT_RUNS_NOTE]
    for key in breakdowns:
        if key not in BREAKDOWN_KEYS:
            raise ValueError(key)
        scope = "공통 질문 집합" if len(table.columns) > 1 else "대상별"
        lines += ["", f"### {key}({scope})", "", _HEADER.replace("| 대상 |", "| 대상·분류 |")]
        source = table.breakdown_source
        kept_by_mode = {mode: set(table.common[mode].questions) for mode in table.modes}
        values = list(dict.fromkeys(getattr(q, key) for q in source["questions"] if q.metric_target))
        for mode in table.modes:
            for k in source["keys"]:
                name = source["label"][k]
                items = list(source["by_key"].get((*k, mode), {}).values())
                use_common = len(table.columns) > 1
                for value in values:
                    subset = [
                        q
                        for q in source["questions"]
                        if getattr(q, key) == value and (not use_common or q.id in kept_by_mode[mode])
                    ]
                    m = metric_set(
                        subset,
                        [i for i in items if i.question in {q.id for q in subset}],
                        mode=mode,
                        candidates=table.candidates_limit,
                        identifier_set=table.identifier_set,
                    )
                    lines.append(_metric_row(f"{name}({table.candidates[name]}) {value or '-'}", mode, m))
    return "\n".join(lines) + "\n"


__all__ = [
    "DIFFERENT_RUNS_NOTE",
    "HYBRID_NOTE",
    "RECALL_NOTE",
    "CommonSet",
    "ComparisonRefused",
    "ComparisonTable",
    "ConditionMismatch",
    "build_comparison",
    "compare_conditions",
    "render_tables",
]
