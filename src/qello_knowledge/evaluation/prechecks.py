"""실행 전 검사, 후보 판별, 비용 미리 보기(QK-EVL-001 spec FR-012·FR-013, research R-05·R-07).

검사 순서: 세트 → 대상 이름 → 대상별 읽기 → 임베딩 모델·차원 → 자료원·고정 커밋 → (임베딩이 드는 방식이 있을 때만) 장부.
하나라도 어긋나면 외부 호출 없이 멈춘다. 장부가 운영인지는 접속 정보를 해석하는 조립 쪽이 판단해 넘긴다.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum

from qello_knowledge.domain.embedding import ModelSpec
from qello_knowledge.domain.generation import AnswerUsageToday
from qello_knowledge.domain.keyword_rules import INDEX_BASELINE, INDEX_IDSPLIT
from qello_knowledge.domain.source_config import RetryPolicy
from qello_knowledge.embedding.estimate import estimated_neurons
from qello_knowledge.evaluation.question_set import Question, QuestionSet
from qello_knowledge.evaluation.reuse import call_limit
from qello_knowledge.ports.evaluation import (
    DayUsageReader,
    EvalTarget,
    LedgerUnavailable,
    TargetDescription,
    TargetDocument,
    TargetUnavailable,
)

EVAL_PREFIX = "qk_eval_"
# 키워드 색인 토크나이저 이름(QK-RET-001 research R-11). 후보 A·B는 기준선, 후보 C는 Alpha다.
KEYWORD_BASELINE = "TokenBigramSplitSymbol"
KEYWORD_ALPHA = "TokenBigramSplitSymbolAlpha"

# contracts/cli.md 2절 종료 1의 사유 이름
PRECHECK_REASONS = (
    "set_invalid",
    "target_not_eval",
    "target_unreachable",
    "no_active_index",
    "index_rule_unknown",
    "tokenizer_unreadable",
    "tokenizer_unknown",
    "source_url_duplicate",
    "document_location_missing",
    "source_missing",
    "commit_mismatch",
    "model_mismatch",
)
# data-model 3절 `CostPreview.blocked_reason`
BLOCKED_REASONS = (
    "approval_missing",
    "ledger_not_production",
    "remote_read_not_allowed",
    "ledger_unreadable",
    "over_remaining",
    "over_max_neurons",
)


class Candidate(StrEnum):
    A = "A"
    B = "B"
    C = "C"


_CANDIDATES = {
    (INDEX_BASELINE, KEYWORD_BASELINE): Candidate.A,
    (INDEX_IDSPLIT, KEYWORD_BASELINE): Candidate.B,
    (INDEX_BASELINE, KEYWORD_ALPHA): Candidate.C,
}


def candidate_for(index_rule: str, tokenizer: str | None) -> Candidate | None:
    """(색인 쪽 규칙, 토크나이저)로 후보를 정한다. 검색 요약의 규칙 표시는 쓰지 않는다(A·C가 같다)."""
    return _CANDIDATES.get((index_rule, tokenizer or ""))


@dataclass(frozen=True)
class PreparedTarget:
    name: str
    description: TargetDescription
    documents: tuple[TargetDocument, ...]
    candidate: Candidate


@dataclass(frozen=True)
class PrecheckResult:
    ok: bool
    reason: str | None = None
    target: str | None = None  # 어긋난 대상(대상 사이 검사면 둘째 대상)
    targets: tuple[PreparedTarget, ...] = ()


def _refuse(reason: str, target: str | None = None) -> PrecheckResult:
    return PrecheckResult(ok=False, reason=reason, target=target)


def _prepare(name: str, target: EvalTarget) -> PreparedTarget | PrecheckResult:
    try:
        described = target.describe()
        documents = tuple(target.documents())
    except TargetUnavailable:
        return _refuse("target_unreachable", name)
    if described.index_version is None:
        return _refuse("no_active_index", name)
    if described.index_rule == "unknown":
        return _refuse("index_rule_unknown", name)
    if described.tokenizer is None:
        return _refuse("tokenizer_unreadable", name)
    candidate = candidate_for(described.index_rule, described.tokenizer)
    if candidate is None:
        return _refuse("tokenizer_unknown", name)
    if any(n > 1 for n in Counter(d.source_url for d in documents).values()):
        return _refuse("source_url_duplicate", name)
    if described.unlocated_documents:  # 검색 결과에 나와도 문서 표에서 찾을 수 없다(research R-04)
        return _refuse("document_location_missing", name)
    return PreparedTarget(name, described, documents, candidate)


def precheck(question_set: QuestionSet | None, targets: Sequence[tuple[str, EvalTarget]]) -> PrecheckResult:
    if question_set is None:
        return _refuse("set_invalid")
    for name, _ in targets:
        if not name.startswith(EVAL_PREFIX):
            return _refuse("target_not_eval", name)
    prepared: list[PreparedTarget] = []
    for name, target in targets:
        item = _prepare(name, target)
        if isinstance(item, PrecheckResult):
            return item
        prepared.append(item)
    first = prepared[0].description
    for item in prepared[1:]:
        if (item.description.embedding_model, item.description.dimension) != (first.embedding_model, first.dimension):
            return _refuse("model_mismatch", item.name)
    for item in prepared:
        for name, commit in question_set.label_commits.items():
            if name not in item.description.sources:
                return _refuse("source_missing", item.name)
            if item.description.commits.get(name) != commit:
                return _refuse("commit_mismatch", item.name)
    return PrecheckResult(ok=True, targets=tuple(prepared))


def unindexed_count(question: Question, target: PreparedTarget) -> int:
    indexed = {(d.source, d.location) for d in target.documents}
    return sum((e.source, e.location) not in indexed for e in question.evidence)


def questions_to_embed(question_set: QuestionSet, targets: Sequence[PreparedTarget]) -> tuple[Question, ...]:
    """질의 임베딩을 부를 질문: 지표 대상 가운데 모든 대상에서 근거가 모두 미색인인 질문을 뺀 것(research R-08)."""
    return tuple(
        q
        for q in question_set.questions
        if q.is_metric_target and any(unindexed_count(q, t) < len(q.evidence) for t in targets)
    )


@dataclass(frozen=True)
class CostPreview:
    questions: int
    max_calls: int
    estimated_neurons: float
    day_usage: AnswerUsageToday | None
    remaining: float | None
    query_reserve: int | None
    blocked_reason: str | None = None
    ledger_read: bool = False


def cost_preview(
    questions: Sequence[Question],
    retry: RetryPolicy,
    model: ModelSpec,
    ledger: DayUsageReader | None,
    *,
    needs_embedding: bool,
    ledger_is_production: bool,
    allow_remote_read: bool,
    allow_query_embedding: bool,
    max_neurons: float | None,
    daily_allowance: float,
) -> CostPreview:
    """research R-07. 막히면 `blocked_reason`이 있고 질의 임베딩을 부르지 않는다. 키워드 전용이면 장부를 읽지 않는다."""
    if not needs_embedding:
        return CostPreview(
            questions=0, max_calls=0, estimated_neurons=0.0, day_usage=None, remaining=None, query_reserve=None
        )
    attempts = retry.max_retries + 1
    estimate = sum(estimated_neurons([q.text.strip()], model) for q in questions) * attempts
    base = dict(questions=len(questions), max_calls=call_limit(len(questions), retry), estimated_neurons=estimate)
    empty = dict(day_usage=None, remaining=None, query_reserve=None)
    if not allow_remote_read:
        return CostPreview(**base, **empty, blocked_reason="remote_read_not_allowed")
    if not ledger_is_production or ledger is None:
        return CostPreview(**base, **empty, blocked_reason="ledger_not_production")
    try:
        usage = ledger.today()
    except LedgerUnavailable:
        return CostPreview(**base, **empty, blocked_reason="ledger_unreadable", ledger_read=True)
    remaining = daily_allowance - usage.day_total
    values = dict(**base, day_usage=usage, remaining=remaining, query_reserve=usage.query_reserve, ledger_read=True)
    if estimate > remaining:
        return CostPreview(**values, blocked_reason="over_remaining")
    if not allow_query_embedding:
        return CostPreview(**values, blocked_reason="approval_missing")
    if max_neurons is None or estimate > max_neurons:
        return CostPreview(**values, blocked_reason="over_max_neurons")
    return CostPreview(**values)


__all__ = [
    "KEYWORD_ALPHA",
    "KEYWORD_BASELINE",
    "BLOCKED_REASONS",
    "PRECHECK_REASONS",
    "Candidate",
    "CostPreview",
    "PrecheckResult",
    "PreparedTarget",
    "candidate_for",
    "cost_preview",
    "precheck",
    "questions_to_embed",
    "unindexed_count",
]
