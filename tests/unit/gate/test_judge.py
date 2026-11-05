"""게이트 판정(QK-STO-002 SC-003, research R-10, FR-015~FR-017). 손 계산 값은 tests/fixtures/gate/README.md와 같다."""

from dataclasses import replace
from fractions import Fraction

import pytest

from qello_knowledge.gate.judge import judge
from qello_knowledge.gate.policy import parse_policy
from tests.unit.gate.gate_builders import (
    BASE,
    CAND,
    FP_IDENT,
    IDENT,
    V1,
    V2,
    facts,
    golden,
    policy,
    question,
    record,
    request,
    result,
    target,
)

G1 = '\n[[guardrails]]\nkind = "G1"\nset = "golden-syn"\nlimit = "0"\n'


def _metrics(outcome):
    (s,) = outcome.sets
    return {m.name: (m.baseline, m.candidate, m.diff, m.judged) for m in s.metrics}


def test_mrr_drop_fails_with_zero_allowance_and_passes_with_allowance():
    r = golden([1, 2, 6, None], [1, 3, 4, None])
    outcome = judge(request(r, pol=policy(min_judged=4)))
    assert outcome.verdict == "fail"
    assert _metrics(outcome) == {
        "recall_at_5": (Fraction(1, 2), Fraction(3, 4), Fraction(1, 4), 4),
        "mrr": (Fraction(5, 12), Fraction(19, 48), Fraction(-1, 48), 4),
    }
    assert [(v.set, v.kind, v.mode, v.metric) for v in outcome.violations] == [
        ("golden-syn", "metric", "hybrid", "mrr")
    ]
    passed = judge(request(r, pol=policy(min_judged=4, drop_mrr="0.05")))
    assert passed.verdict == "pass" and passed.violations == ()
    assert passed.sets[0].improvements == ("q3",) and passed.sets[0].regressions == ()


def test_metric_drop_fails_and_records_regression():
    outcome = judge(request(golden([1, 1], [6, 1])))
    assert outcome.verdict == "fail" and outcome.sets[0].regressions == ("q1",)
    assert _metrics(outcome)["recall_at_5"][:2] == (Fraction(1), Fraction(1, 2))


def test_candidate_only_failures_count_as_misses_and_trip_g1():
    r = golden([1, 1, 1], [1, None, None], cand_status={"q2": "store_unavailable", "q3": "skipped"})
    outcome = judge(request(r, pol=policy(drop_recall="1", drop_mrr="1", extra=G1)))
    assert _metrics(outcome)["recall_at_5"][:2] == (Fraction(1), Fraction(1, 3))
    (s,) = outcome.sets
    assert s.judged == 3 and s.new_failures == ("q2", "q3")
    (g1,) = s.guardrails
    assert (g1.kind, g1.value, g1.limit, g1.ok) == ("G1", Fraction(2), Fraction(0), False)
    assert [v.kind for v in outcome.violations] == ["G1"]


def test_hybrid_omission_in_candidate_is_not_normal():
    r = golden([1, 1], [1, 1], cand_omitted={"q1"})
    outcome = judge(request(r, pol=policy(drop_recall="1", drop_mrr="1", extra=G1)))
    assert outcome.sets[0].new_failures == ("q1",) and outcome.verdict == "fail"


def test_baseline_abnormal_questions_are_excluded_with_reason():
    r = golden([1, None, None], [1, 1, 1], base_status={"q2": "store_unavailable", "q3": "skipped"})
    outcome = judge(request(r, pol=policy(min_judged=1)))
    (s,) = outcome.sets
    assert outcome.verdict == "pass" and s.judged == 1
    assert s.excluded == (("q2", "baseline_failed:store_unavailable"), ("q3", "baseline_skipped"))


IDENT_POLICY = """schema = "qk-sto-002-gate-policy/v1"
id = "syn-policy"
version = 1
mode = "hybrid"

[tokenizers]
baseline = "TokenBigramSplitSymbol"
candidate = "TokenBigramSplitSymbol"

[[sets]]
id = "ident-syn"
version = 1
fingerprint = "{fp}"
min_judged = 1
max_drop = {{ recall_at_5 = "0", mrr = "0" }}

[[guardrails]]
kind = "{kind}"
set = "ident-syn"
limit = "{limit}"
"""


def _ident_policy(kind, limit):
    import tomllib

    text = IDENT_POLICY.format(fp=FP_IDENT, kind=kind, limit=limit)
    value, issues = parse_policy(
        tomllib.loads(text), raw=text.encode(), repo_path="eval/gate_policies/syn-policy/v1.toml"
    )
    assert not issues
    return value


def _ident_record(*, cand_evidence=1, base_count=10, cand_count=10, base_keyword_status="ok"):
    qs = [question(f"i{i}", query_form="partial") for i in (1, 2)]
    rs = []
    for q in qs:
        rs.append(result(q.id, BASE, "hybrid", 1))
        rs.append(result(q.id, CAND, "hybrid", 1))
        rs.append(result(q.id, BASE, "keyword", 1, count=base_count, status=base_keyword_status))
        rs.append(result(q.id, CAND, "keyword", 1, count=cand_count, evidence=cand_evidence))
    return record(IDENT, fingerprint=FP_IDENT, questions=qs, results=rs, modes=("hybrid", "keyword"))


def test_g2_identifier_precision_drop():
    outcome = judge(request(_ident_record(cand_evidence=0), pol=_ident_policy("G2", "0")))
    (g2,) = outcome.sets[0].guardrails
    assert (g2.baseline, g2.candidate, g2.value, g2.judged) == (Fraction(1, 5), Fraction(0), Fraction(1, 5), 2)
    assert [v.kind for v in outcome.violations] == ["G2"]


def test_g3_keyword_cap_increase_and_failed_candidate_counts_as_cap():
    outcome = judge(request(_ident_record(base_count=10, cand_count=20), pol=_ident_policy("G3", "0.25")))
    (g3,) = outcome.sets[0].guardrails
    assert (g3.baseline, g3.candidate, g3.value) == (Fraction(0), Fraction(1), Fraction(1))
    assert [v.kind for v in outcome.violations] == ["G3"]
    ok = judge(request(_ident_record(base_count=10, cand_count=10), pol=_ident_policy("G3", "0")))
    assert ok.verdict == "pass"


def test_guardrail_without_judged_questions_is_undecidable():
    r = _ident_record(base_keyword_status="store_unavailable")
    outcome = judge(request(r, pol=_ident_policy("G3", "0")))
    assert outcome.verdict == "undecidable" and "too_few_judged" in outcome.undecidable_reasons


def _two_records(base_model, cand_model, base_target_model, cand_target_model):
    base = golden([1, 1], [1, 1], model=base_model)
    base = replace(
        base,
        targets=(target(BASE, V1, model=base_target_model),),
        results=tuple(r for r in base.results if r.target == BASE),
    )
    cand = golden([1, 1], [1, 1], model=cand_model, run_id="evl-20261105T000000Z-00000002")
    cand = replace(
        cand,
        targets=(target(CAND, V2, rule="kw-index-idsplit-v1", model=cand_target_model),),
        results=tuple(r for r in cand.results if r.target == CAND),
    )
    return base, cand


def test_different_embedding_models_need_different_index_versions():
    base, cand = _two_records("m-old", "m-new", "m-old", "m-new")
    outcome = judge(request(base, cand))
    assert outcome.verdict == "pass" and outcome.query_vectors_differ is True
    base, cand = _two_records("m-old", "m-new", "m-same", "m-same")
    assert "condition_mismatch" in judge(request(base, cand)).undecidable_reasons


def _undecidable(**kw):
    return judge(request(golden([1, 1], [1, 1], **kw))).undecidable_reasons


@pytest.mark.parametrize(
    ("build", "reason"),
    [
        (lambda: request(golden([1, 1], [1, 1], complete=False)), "record_incomplete"),
        (lambda: request(golden([1, 1], [1, 1], set_id="other-set")), "set_missing"),
        (lambda: request(golden([1, 1], [1, 1], confirmed=False)), "set_unconfirmed"),
        (lambda: request(golden([1, 1], [1, 1], fingerprint="f" * 64)), "set_mismatch"),
        (lambda: request(golden([1, 1], [1, 1], targets=(target(BASE, V1),))), "target_missing"),
        (lambda: request(golden([1, 1], [1, 1]), baseline_version="iv-other"), "index_version_mismatch"),
        (lambda: request(golden([1, 1], [1, 1], query_rule="kw-query-raw")), "search_settings_mismatch"),
        (lambda: request(golden([1, 1], [1, 1], modes=("keyword",))), "mode_missing"),
        (
            lambda: request(golden([1, 1], [1, 1], targets=(target(BASE, V1), target(CAND, V2, rule="unknown")))),
            "index_rule_unknown",
        ),
        (
            lambda: request(
                golden(
                    [1, 1],
                    [1, 1],
                    targets=(target(BASE, V1), target(CAND, V2, tokenizer="TokenBigramSplitSymbolAlpha")),
                )
            ),
            "tokenizer_mismatch",
        ),
        (lambda: request(golden([1, 1], [1, 1]), history=facts(policy_merge_commit=None)), "policy_unmerged"),
        (lambda: _with_history(policy_matches_main=False), "policy_changed"),
        (lambda: request(golden([1, 1], [1, 1], code=None)), "code_commit_unknown"),
        (lambda: request(golden([1, 1], [1, 1]), history=facts(record_contains_policy={})), "code_before_policy"),
        (lambda: request(golden([1, 1], [1, 1], dirty=True)), "dirty_code"),
        (lambda: request(golden([1, 1], [1, 1]), pol=policy(min_judged=5)), "too_few_judged"),
        (
            lambda: request(
                golden([1, 1], [1, 1], modes=("hybrid", "keyword")),
                pol=policy(extra='\n[[guardrails]]\nkind = "G2"\nset = "golden-syn"\nlimit = "0"\n'),
            ),
            "guardrail_set_kind",
        ),
        (
            lambda: request(golden([1, 1], [1, 1]), golden([1, 1], [1, 1], run_id="evl-20261105T000000Z-00000009")),
            "set_duplicate",
        ),
    ],
)
def test_undecidable_reasons(build, reason):
    outcome = judge(build())
    assert outcome.verdict == "undecidable" and outcome.undecidable_reasons == (reason,)
    assert outcome.sets == () and outcome.violations == ()


def _with_history(**kw):
    r = golden([1, 1], [1, 1])
    return request(r, history=facts((r,), **kw))


def test_unreadable_record_and_condition_mismatch():
    from qello_knowledge.gate.judge import GateRequest, RecordInput

    base_request = request(golden([1, 1], [1, 1]))
    broken = GateRequest(
        base_request.policy, (RecordInput("runs/x.json", "", None),), BASE, CAND, V1, V2, base_request.history
    )
    assert "record_schema" in judge(broken).undecidable_reasons
    t_base = target(BASE, V1)
    t_cand = replace(target(CAND, V2, rule="kw-index-idsplit-v1"), commits={"docs": "z" * 40})
    assert "condition_mismatch" in judge(request(golden([1, 1], [1, 1], targets=(t_base, t_cand)))).undecidable_reasons


def test_undecidable_keeps_judged_counts():
    outcome = judge(request(golden([1, 1], [1, 1]), pol=policy(min_judged=5)))
    assert outcome.judged_counts == {"golden-syn": 2}
    assert outcome.covered_sources == ("docs",)
