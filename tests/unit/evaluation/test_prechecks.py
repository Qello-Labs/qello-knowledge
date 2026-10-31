"""실행 전 검사와 비용 관문(QK-EVL-001 spec FR-012·FR-013, SC-005, research R-05·R-07, tasks T020).

거부되면 가짜 제공자 호출과 장부 읽기가 0이다. 실행 전 검사는 제공자를 부르지 않으므로 장부 읽기 수로 순서를 본다.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from qello_knowledge.domain.embedding import MODELS
from qello_knowledge.domain.source_config import RetryPolicy
from qello_knowledge.embedding.estimate import estimated_neurons
from qello_knowledge.evaluation.prechecks import (
    Candidate,
    candidate_for,
    cost_preview,
    precheck,
    questions_to_embed,
)
from qello_knowledge.evaluation.question_set import QuestionSet, check_question_set
from qello_knowledge.ports.evaluation import LedgerUnavailable, TargetUnavailable
from tests.unit.evaluation.fakes import (
    COMMIT,
    GOLDEN,
    FakeDayUsageReader,
    FakeEvalTarget,
    description,
    document,
    question_set_file,
    usage,
)

MODEL = MODELS["@cf/baai/bge-m3"]
RETRY = RetryPolicy(max_retries=1)
DOCS = (document("docs/A.md"), document("docs/B.md"))


@pytest.fixture
def golden(tmp_path: Path) -> QuestionSet:
    question_set, _ = check_question_set(question_set_file(tmp_path, "fixture-golden", 1, GOLDEN.read_text("utf-8")))
    assert question_set is not None
    return question_set


def _targets(*items: FakeEvalTarget, names: tuple[str, ...] | None = None) -> list[tuple[str, FakeEvalTarget]]:
    names = names or tuple(f"qk_eval_t{n}" for n in range(len(items)))
    return list(zip(names, items, strict=True))


@pytest.mark.parametrize(
    ("rule", "tokenizer", "candidate"),
    [
        ("kw-index-baseline-v1", "TokenBigramSplitSymbol", Candidate.A),
        ("kw-index-idsplit-v1", "TokenBigramSplitSymbol", Candidate.B),
        ("kw-index-baseline-v1", "TokenBigramSplitSymbolAlpha", Candidate.C),
        ("kw-index-idsplit-v1", "TokenBigramSplitSymbolAlpha", None),
        ("kw-index-baseline-v1", "TokenNgram", None),
        ("unknown", "TokenBigramSplitSymbol", None),
    ],
)
def test_candidate_for(rule: str, tokenizer: str, candidate: Candidate | None) -> None:
    assert candidate_for(rule, tokenizer) is candidate


def test_matching_targets_pass_with_candidates(golden: QuestionSet) -> None:
    a = FakeEvalTarget(description("qk_eval_a"), DOCS)
    b = FakeEvalTarget(
        description("qk_eval_b", index_version="iv-8b7e93b22051", index_rule="kw-index-idsplit-v1"), DOCS
    )
    c = FakeEvalTarget(description("qk_eval_c", tokenizer="TokenBigramSplitSymbolAlpha"), DOCS)
    result = precheck(golden, _targets(a, b, c, names=("qk_eval_a", "qk_eval_b", "qk_eval_c")))
    assert result.ok and result.reason is None
    assert [t.candidate for t in result.targets] == [Candidate.A, Candidate.B, Candidate.C]
    assert [t.documents for t in result.targets] == [DOCS, DOCS, DOCS]


FAILURES = [
    ("target_not_eval", lambda: _targets(FakeEvalTarget(docs=DOCS), names=("postgres",))),
    ("target_unreachable", lambda: _targets(FakeEvalTarget(fail=TargetUnavailable("x")))),
    ("no_active_index", lambda: _targets(FakeEvalTarget(description(index_version=None, index_rule="unknown"), DOCS))),
    (
        "index_rule_unknown",
        lambda: _targets(FakeEvalTarget(description(index_version="iv-x", index_rule="unknown"), DOCS)),
    ),
    ("tokenizer_unreadable", lambda: _targets(FakeEvalTarget(description(tokenizer=None), DOCS))),
    ("tokenizer_unknown", lambda: _targets(FakeEvalTarget(description(tokenizer="TokenNgram"), DOCS))),
    (
        "source_url_duplicate",
        lambda: _targets(
            FakeEvalTarget(
                docs=(document("docs/A.md", "https://x.invalid/1"), document("docs/B.md", "https://x.invalid/1"))
            )
        ),
    ),
    (
        "source_missing",
        lambda: _targets(FakeEvalTarget(description(sources=("other",), commits={"other": COMMIT}), DOCS)),
    ),
    ("commit_mismatch", lambda: _targets(FakeEvalTarget(description(commits={"dnd-backend-docs": "f" * 40}), DOCS))),
    ("document_location_missing", lambda: _targets(FakeEvalTarget(description(unlocated=2), DOCS))),
    (
        "model_mismatch",
        lambda: _targets(FakeEvalTarget(docs=DOCS), FakeEvalTarget(description(dimension=768), DOCS)),
    ),
]


@pytest.mark.parametrize(("reason", "make"), FAILURES, ids=[f[0] for f in FAILURES])
def test_precheck_failures_stop_before_ledger(golden: QuestionSet, reason: str, make) -> None:
    targets = make()
    result = precheck(golden, targets)
    assert not result.ok and result.reason == reason
    assert result.target in {name for name, _ in targets}


def test_set_invalid_reads_no_target() -> None:
    target = FakeEvalTarget(docs=DOCS)
    result = precheck(None, _targets(target))
    assert result.reason == "set_invalid" and target.reads == 0


def test_name_check_happens_before_any_read(golden: QuestionSet) -> None:
    first = FakeEvalTarget(docs=DOCS)
    result = precheck(golden, _targets(first, FakeEvalTarget(docs=DOCS), names=("qk_eval_a", "postgres")))
    assert result.reason == "target_not_eval" and first.reads == 0


def test_first_failure_stops_later_reads(golden: QuestionSet) -> None:
    later = FakeEvalTarget(docs=DOCS)
    result = precheck(golden, _targets(FakeEvalTarget(fail=TargetUnavailable("x")), later))
    assert result.reason == "target_unreachable" and later.reads == 0


# --- 비용 관문 ---


def _preview(golden: QuestionSet, ledger: FakeDayUsageReader | None, **overrides):
    result = precheck(golden, _targets(FakeEvalTarget(docs=DOCS)))
    values = dict(
        needs_embedding=True,
        ledger_is_production=True,
        allow_remote_read=True,
        allow_query_embedding=True,
        max_neurons=10.0,
        daily_allowance=10_000,
    )
    values.update(overrides)
    questions = questions_to_embed(golden, result.targets)
    return questions, cost_preview(questions, RETRY, MODEL, ledger, **values)


def test_preview_counts_questions_calls_and_neurons(golden: QuestionSet) -> None:
    ledger = FakeDayUsageReader(usage(day_total=1_000.0, query_reserve=3_000))
    questions, preview = _preview(golden, ledger)
    assert [q.id for q in questions] == ["g01", "g02"]  # 지표 대상만(no_answer·pending 제외)
    assert preview.questions == 2 and preview.max_calls == 4
    expected = sum(estimated_neurons([q.text], MODEL) for q in questions) * 2
    assert preview.estimated_neurons == pytest.approx(expected)
    assert preview.remaining == 9_000 and preview.query_reserve == 3_000 and preview.day_usage is not None
    assert preview.blocked_reason is None and ledger.reads == 1


def test_questions_unindexed_in_every_target_are_not_embedded(golden: QuestionSet) -> None:
    result = precheck(golden, _targets(FakeEvalTarget(docs=(document("docs/A.md"),))))
    assert [q.id for q in questions_to_embed(golden, result.targets)] == ["g01"]


@pytest.mark.parametrize(
    ("overrides", "ledger_value", "reason", "reads"),
    [
        ({"allow_remote_read": False}, None, "remote_read_not_allowed", 0),
        ({"ledger_is_production": False}, None, "ledger_not_production", 0),
        ({}, LedgerUnavailable("x"), "ledger_unreadable", 1),
        ({"daily_allowance": 1}, None, "over_remaining", 1),
        ({"allow_query_embedding": False, "max_neurons": None}, None, "approval_missing", 1),
        ({"max_neurons": 0.0}, None, "over_max_neurons", 1),
    ],
)
def test_blocked_previews(golden: QuestionSet, overrides, ledger_value, reason: str, reads: int) -> None:
    ledger = FakeDayUsageReader(ledger_value if ledger_value is not None else usage(day_total=100.0))
    _, preview = _preview(golden, ledger, **overrides)
    assert preview.blocked_reason == reason and ledger.reads == reads
    if reason == "approval_missing":
        assert preview.remaining == 9_900 and preview.max_calls == 4 and preview.estimated_neurons > 0


def test_keyword_only_does_not_read_ledger(golden: QuestionSet) -> None:
    ledger = FakeDayUsageReader()
    _, preview = _preview(golden, ledger, needs_embedding=False, allow_remote_read=False, allow_query_embedding=False)
    assert preview.blocked_reason is None and ledger.reads == 0
    assert preview.max_calls == 0 and preview.estimated_neurons == 0 and preview.day_usage is None
