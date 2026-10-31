"""비교 조건, 공통 질문 집합, Markdown 표.

QK-EVL-001 spec US4-2~US4-6, FR-024·FR-025, SC-007, research R-11, tasks T032.
"""

from __future__ import annotations

import tomllib
from dataclasses import replace

import pytest

from qello_knowledge.evaluation.compare import (
    DIFFERENT_RUNS_NOTE,
    HYBRID_NOTE,
    ComparisonRefused,
    build_comparison,
    render_tables,
)
from qello_knowledge.evaluation.records import FilterRecord, SetRef
from tests.unit.evaluation.fakes import GOLDEN, IDENTIFIERS, question_record, result, run_record

T, F = True, False
TARGETS = (("qk_eval_a", "A"), ("qk_eval_b", "B"), ("qk_eval_c", "C"))


def _results(qid: str, *, keyword_rank: dict[str, int | None], digest: dict[str, str] | None = None, overrides=None):
    out = []
    for name, _ in TARGETS:
        for mode in ("vector", "hybrid", "keyword"):
            rank = keyword_rank[name] if mode == "keyword" else 1
            values = dict(target=name, mode=mode, rank=rank, count=5 if rank else 0, top=(T,) if rank == 1 else (F,))
            if mode == "vector":
                values["digest"] = (digest or {}).get(name, "a" * 64)
            values.update((overrides or {}).get((name, mode), {}))
            out.append(result(qid, **values))
    return out


def _record(**conditions):
    questions = [
        question_record("q1"),
        question_record("q2", identifier="snake"),
        question_record("q3", form="partial"),
    ]
    results = (
        _results("q1", keyword_rank={"qk_eval_a": None, "qk_eval_b": 1, "qk_eval_c": 2})
        + _results("q2", keyword_rank={"qk_eval_a": 1, "qk_eval_b": 1, "qk_eval_c": 1}, digest={"qk_eval_c": "b" * 64})
        + _results(
            "q3",
            keyword_rank={"qk_eval_a": 1, "qk_eval_b": 1, "qk_eval_c": 1},
            overrides={
                ("qk_eval_b", "keyword"): {"status": "keyword_search_failed", "rank": None, "count": 0},
                ("qk_eval_c", "hybrid"): {"omitted": [("vector", "query_embedding_failed", "transient")]},
            },
        )
    )
    return run_record(questions, results, targets=TARGETS, **conditions)


def test_same_run_comparison_uses_common_questions() -> None:
    table = build_comparison([_record()])
    assert not table.different_runs
    keyword = table.common["keyword"]
    assert keyword.questions == ("q1", "q2")  # q1의 A `no_results`는 남는다(FR-025)
    assert keyword.excluded == (("q3", "keyword_search_failed (qk_eval_b)"),)
    hybrid = table.common["hybrid"]
    assert hybrid.questions == ("q1", "q2") and hybrid.excluded == (
        ("q3", "omitted:query_embedding_failed (qk_eval_c)"),
    )
    assert table.vector_differs == ("q2",)
    a = table.metrics[("qk_eval_a", "keyword")]
    assert (a.top20.numerator, a.top20.denominator) == (1, 2)
    b = table.metrics[("qk_eval_b", "keyword")]
    assert b.top20.text() == "1.0000" and b.precision_at_5 is not None


@pytest.mark.parametrize(
    ("item", "change"),
    [
        ("question_set", {"question_set": SetRef("fixture-identifiers", 2, "f" * 64, True)}),
        ("question_set", {"question_set": SetRef("fixture-identifiers", 1, "e" * 64, True)}),
        ("embedding_model", {"embedding_model": "@cf/other"}),
        ("query_rule", {"query_rule": "kw-query-raw"}),
        ("candidates", {"candidates": 10}),
        ("rrf_k", {"rrf_k": 30}),
        ("filters", {"filters": FilterRecord(("github_repo",), ())}),
    ],
)
def test_one_condition_difference_is_refused(item: str, change: dict) -> None:
    other = _record(run_id="evl-20261031T100000Z-0000beef", **change)
    with pytest.raises(ComparisonRefused) as refused:
        build_comparison([_record(), other])
    assert [m.item for m in refused.value.mismatches] == [item]
    assert len(refused.value.mismatches[0].values) == 2


def test_commit_difference_is_refused() -> None:
    record = _record()
    moved = replace(
        record,
        run_id="evl-20261031T100000Z-0000beef",
        targets=tuple(replace(t, commits={"dnd-backend-docs": "f" * 40}) for t in record.targets),
    )
    with pytest.raises(ComparisonRefused) as refused:
        build_comparison([record, moved])
    assert [m.item for m in refused.value.mismatches] == ["commits"]


def test_incomplete_record_is_refused() -> None:
    with pytest.raises(ComparisonRefused) as refused:
        build_comparison([_record(complete=False)])
    assert refused.value.incomplete == ("evl-20261031T090000Z-0000abcd",)


def test_different_runs_are_marked() -> None:
    first = _record()
    second = _record(run_id="evl-20261031T100000Z-0000beef")
    table = build_comparison([first, second], targets=["qk_eval_a"])
    assert table.different_runs
    assert [key for key, _ in table.columns] == [
        ("evl-20261031T090000Z-0000abcd", "qk_eval_a"),
        ("evl-20261031T100000Z-0000beef", "qk_eval_a"),
    ]
    text = render_tables(table)
    assert DIFFERENT_RUNS_NOTE in text


def test_single_target_has_no_comparison_table() -> None:
    table = build_comparison([_record()], targets=["qk_eval_a"])
    text = render_tables(table)
    assert "## 대상별" in text and "## 비교" not in text


def test_rendered_tables_have_fractions_notes_and_no_question_text() -> None:
    table = build_comparison([_record()])
    text = render_tables(table, breakdowns=("identifier_form", "query_form"))
    assert "## 비교" in text and HYBRID_NOTE in text and "벡터 순위 다름: q2" in text
    assert "1/2=0.5000" in text  # 분자/분모=값
    assert "### identifier_form(공통 질문 집합)" in text and "### query_form(공통 질문 집합)" in text
    assert "q3: keyword_search_failed (qk_eval_b)" in text
    for path in (GOLDEN, IDENTIFIERS):
        for q in tomllib.loads(path.read_text("utf-8"))["question"]:
            assert q["text"] not in text


def test_single_target_breakdown_uses_all_questions() -> None:
    text = render_tables(build_comparison([_record()], targets=["qk_eval_a"]), breakdowns=("identifier_form",))
    assert "### identifier_form(대상별)" in text
