"""지표 계산(QK-EVL-001 spec FR-016~FR-018, SC-003, research R-09, tasks T022).

손으로 정한 순위 사례의 기대값과 소수 넷째 자리까지 비교한다. 입력은 실행 기록뿐이다(FR-020).
"""

from __future__ import annotations

from fractions import Fraction

from qello_knowledge.evaluation.metrics import breakdown, metrics
from tests.unit.evaluation.fakes import question_record, result, run_record

T, F = True, False
# (질문, 첫 근거 순위, 결과 수, 상위 5건 근거 여부, 상태)
CASES = [
    ("q01", 1, 30, (T, T, T, T, T), None),  # 근거 1위, 상위 5건 모두 근거(Precision 5/5)
    ("q02", 5, 30, (F, F, F, F, T), None),  # 5위
    ("q03", 6, 30, (F, F, F, F, F), None),  # 6위, 상위 5건 근거 0
    ("q04", 20, 30, (F, F, F, F, F), None),  # 20위
    ("q05", 21, 30, (F, F, F, F, F), None),  # 21위(MRR 0, 상위 20건 밖)
    ("q06", None, 0, (), None),  # 결과 없음
    ("q07", None, 0, (), "keyword_search_failed"),  # 검색 실패: 분모에 넣고 0
    ("q08", 2, 30, (F, T, T, T, F), None),  # 같은 문서 청크 여러 개(3/5)
    ("q09", 3, 30, (F, F, T, F, F), None),  # 근거 여럿 가운데 하나만 나옴
]


def _record(mode: str = "hybrid", **kwargs):
    questions = [question_record(q) for q, *_ in CASES]
    results = [result(q, mode=mode, rank=r, count=c, top=top, status=s) for q, r, c, top, s in CASES]
    return run_record(questions, results, **kwargs)


def test_hand_ranked_cases() -> None:
    m = metrics(_record())[("qk_eval_a", "hybrid")]
    assert (m.recall_at_5.numerator, m.recall_at_5.denominator) == (4, 9)
    assert m.recall_at_5.text() == "0.4444"
    assert m.mrr.numerator == Fraction(1) + Fraction(1, 5) + Fraction(1, 6) + Fraction(1, 20) + Fraction(
        1, 2
    ) + Fraction(1, 3)
    assert m.mrr.text() == "0.2500"
    assert (m.top20.numerator, m.top20.denominator) == (6, 9) and m.top20.text() == "0.6667"
    assert m.precision_at_5 is not None
    assert m.precision_at_5.numerator == Fraction(5 + 1 + 3 + 1, 5) and m.precision_at_5.text() == "0.2222"
    assert dict(m.failures) == {"keyword_search_failed": 1}
    assert m.mean_results is None and m.cap_hit is None  # 키워드 전용만


def test_keyword_mean_results_and_cap_hit() -> None:
    questions = [question_record(f"k{n}") for n in range(4)]
    results = [
        result("k0", rank=1, count=20, top=(T,)),
        result("k1", rank=2, count=10, top=(F, T)),
        result("k2", count=0, terms=0),  # 낱말 0개: 결과 0건, 낱말 수 0
        result("k3", status="keyword_search_failed"),
    ]
    m = metrics(run_record(questions, results, candidates=20))[("qk_eval_a", "keyword")]
    assert m.mean_results is not None and (m.mean_results.numerator, m.mean_results.denominator) == (30, 4)
    assert m.mean_results.text() == "7.5000"
    assert m.cap_hit is not None and m.cap_hit.text() == "0.2500"
    assert m.zero_terms == 1


def test_excluded_questions_are_counted_by_reason() -> None:
    questions = [
        question_record("a"),
        question_record("b", qtype="no_answer", metric=False, evidence=()),
        question_record("c", label="pending", metric=False),
        question_record("d"),
    ]
    results = [result("a", rank=1, count=1, top=(T,)), result("d", status="skipped")]
    m = metrics(run_record(questions, results))[("qk_eval_a", "keyword")]
    assert m.recall_at_5.denominator == 1
    assert dict(m.excluded) == {"no_answer": 1, "pending": 1, "evidence_unindexed": 1}


def test_hybrid_omissions_are_counted() -> None:
    questions = [question_record("a"), question_record("b")]
    results = [
        result(
            "a", mode="hybrid", rank=1, count=3, top=(T,), omitted=[("vector", "query_embedding_failed", "transient")]
        ),
        result("b", mode="hybrid", rank=2, count=3, top=(F, T)),
    ]
    m = metrics(run_record(questions, results))[("qk_eval_a", "hybrid")]
    assert dict(m.omitted) == {"query_embedding_failed": 1} and m.recall_at_5.text() == "1.0000"


def test_golden_type_record_has_no_precision() -> None:
    questions = [question_record("a", form=None)]
    m = metrics(run_record(questions, [result("a", rank=1, count=1, top=(T,))]))[("qk_eval_a", "keyword")]
    assert m.precision_at_5 is None


def test_empty_denominator_reads_as_dash() -> None:
    questions = [question_record("a")]
    m = metrics(run_record(questions, [result("a", status="skipped")]))[("qk_eval_a", "keyword")]
    assert m.recall_at_5.denominator == 0 and m.recall_at_5.value is None and m.recall_at_5.text() == "-"


def test_breakdown_uses_the_same_definition() -> None:
    questions = [question_record("a", identifier="camel"), question_record("b", identifier="snake")]
    results = [result("a", rank=1, count=1, top=(T,)), result("b", rank=7, count=10, top=(F,) * 5)]
    split = breakdown(run_record(questions, results), "identifier_form")
    assert split[("qk_eval_a", "keyword", "camel")].recall_at_5.text() == "1.0000"
    assert split[("qk_eval_a", "keyword", "snake")].recall_at_5.text() == "0.0000"
    assert split[("qk_eval_a", "keyword", "snake")].top20.text() == "1.0000"
