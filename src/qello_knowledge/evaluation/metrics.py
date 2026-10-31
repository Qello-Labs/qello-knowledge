"""지표 계산(QK-EVL-001 spec FR-016~FR-018, research R-09). 입력은 실행 기록 하나뿐이다(FR-020).

- 분모: 지표 대상 질문 가운데 그 대상에서 근거가 모두 미색인(`skipped`)이 아닌 질문. 검색 실패는 분모에 넣고 0으로 센다.
- Recall@5: 첫 근거 순위 ≤ 5인 질문 비율(근거 문서 가운데 하나라도 찾은 비율, Hit@5와 같다).
- MRR: 첫 근거 순위 역수의 평균. 20보다 크거나 없으면 0.
- Precision@5(식별자 세트만): 상위 5건 가운데 근거 항목 수 ÷ 5의 평균(결과가 5건보다 적어도 5로 나눈다).
- 평균 결과 수·상한 도달 비율(키워드 전용만): 결과 수 평균, 결과 수 = 실행 조건 후보 수인 질문 비율.
비율은 `Fraction`으로 계산하고 출력 때만 소수 넷째 자리로 반올림한다.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

from qello_knowledge.evaluation.records import QuestionRecord, QuestionResult, RunRecord

MRR_CUTOFF = 20
OK_STATUSES = ("ok", "no_results")
SKIPPED = "skipped"
BREAKDOWN_KEYS = ("type", "identifier_form", "query_form")


@dataclass(frozen=True)
class Ratio:
    numerator: Fraction
    denominator: int

    @property
    def value(self) -> Fraction | None:
        return None if self.denominator == 0 else Fraction(self.numerator) / self.denominator

    def text(self) -> str:
        value = self.value
        if value is None:
            return "-"
        exact = Decimal(value.numerator) / Decimal(value.denominator)
        return str(exact.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))

    def fraction_text(self) -> str:
        """분자/분모. 분자가 정수가 아니면 소수 넷째 자리로 적는다."""
        numerator = Fraction(self.numerator)
        if numerator.denominator == 1:
            head = str(numerator.numerator)
        else:
            head = str((Decimal(numerator.numerator) / Decimal(numerator.denominator)).quantize(Decimal("0.0001")))
        return f"{head}/{self.denominator}"


@dataclass(frozen=True)
class MetricSet:
    recall_at_5: Ratio
    mrr: Ratio
    top20: Ratio
    precision_at_5: Ratio | None = None
    mean_results: Ratio | None = None
    cap_hit: Ratio | None = None
    excluded: Mapping[str, int] = field(default_factory=dict)
    failures: Mapping[str, int] = field(default_factory=dict)
    omitted: Mapping[str, int] = field(default_factory=dict)
    zero_terms: int = 0


def _excluded_reason(question: QuestionRecord) -> str:
    return "no_answer" if question.type == "no_answer" else "pending"


def metric_set(
    questions: Iterable[QuestionRecord],
    results: Iterable[QuestionResult],
    *,
    mode: str,
    candidates: int,
    identifier_set: bool,
) -> MetricSet:
    """한 대상·한 방식의 결과로 지표를 낸다. `questions`는 같은 부분 집합(분류별 지표)이어야 한다."""
    questions = list(questions)
    excluded = Counter(_excluded_reason(q) for q in questions if not q.metric_target)
    wanted = {q.id for q in questions if q.metric_target}
    counted: list[QuestionResult] = []
    for item in results:
        if item.question not in wanted:
            continue
        if item.status == SKIPPED:
            excluded[item.skipped_reason or SKIPPED] += 1
            continue
        counted.append(item)
    n = len(counted)
    ranks = [r.first_evidence_rank if r.status in OK_STATUSES else None for r in counted]
    recall = Ratio(Fraction(sum(1 for k in ranks if k is not None and k <= 5)), n)
    mrr = Ratio(sum((Fraction(1, k) for k in ranks if k is not None and k <= MRR_CUTOFF), Fraction(0)), n)
    top20 = Ratio(Fraction(sum(1 for k in ranks if k is not None and k <= MRR_CUTOFF)), n)
    precision = None
    if identifier_set:
        hits = sum(
            (Fraction(sum(h.evidence for h in r.top5), 5) for r in counted if r.status in OK_STATUSES), Fraction(0)
        )
        precision = Ratio(hits, n)
    mean_results = cap_hit = None
    if mode == "keyword":
        mean_results = Ratio(Fraction(sum(r.result_count for r in counted)), n)
        cap_hit = Ratio(Fraction(sum(1 for r in counted if r.result_count >= candidates)), n)
    failures = Counter(r.status for r in counted if r.status not in OK_STATUSES)
    omitted = Counter(o.reason for r in counted for o in r.omitted)
    zero_terms = sum(1 for r in counted if mode in ("keyword", "hybrid") and r.keyword_terms == 0)
    return MetricSet(
        recall_at_5=recall,
        mrr=mrr,
        top20=top20,
        precision_at_5=precision,
        mean_results=mean_results,
        cap_hit=cap_hit,
        excluded=dict(excluded),
        failures=dict(failures),
        omitted=dict(omitted),
        zero_terms=zero_terms,
    )


def is_identifier_set(record: RunRecord) -> bool:
    return any(q.query_form is not None for q in record.questions)


def _groups(record: RunRecord) -> dict[tuple[str, str], list[QuestionResult]]:
    groups: dict[tuple[str, str], list[QuestionResult]] = defaultdict(list)
    for target in record.targets:
        for mode in record.conditions.modes:
            groups[(target.database, mode)] = []
    for item in record.results:
        groups[(item.target, item.mode)].append(item)
    return groups


def metrics(record: RunRecord) -> dict[tuple[str, str], MetricSet]:
    """(대상, 방식) → 지표. 순서는 기록의 대상 순서와 실행 조건의 방식 순서다."""
    identifier = is_identifier_set(record)
    return {
        key: metric_set(
            record.questions, items, mode=key[1], candidates=record.conditions.candidates, identifier_set=identifier
        )
        for key, items in _groups(record).items()
    }


def breakdown(record: RunRecord, key: str) -> dict[tuple[str, str, str | None], MetricSet]:
    """분류(`type`, `identifier_form`, `query_form`)별 지표. 정의는 `metrics`와 같다(spec FR-018)."""
    if key not in BREAKDOWN_KEYS:
        raise ValueError(key)
    identifier = is_identifier_set(record)
    values = list(dict.fromkeys(getattr(q, key) for q in record.questions))
    out: dict[tuple[str, str, str | None], MetricSet] = {}
    for (target, mode), items in _groups(record).items():
        for value in values:
            subset = [q for q in record.questions if getattr(q, key) == value]
            out[(target, mode, value)] = metric_set(
                subset, items, mode=mode, candidates=record.conditions.candidates, identifier_set=identifier
            )
    return out


__all__ = ["BREAKDOWN_KEYS", "MetricSet", "Ratio", "breakdown", "is_identifier_set", "metric_set", "metrics"]
