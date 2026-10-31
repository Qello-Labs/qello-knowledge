"""평가 실행 순서, 근거 미색인, 질문별 실패, 실행 멈춤(QK-EVL-001 spec FR-014~FR-022, research R-08).

바깥 반복은 질문, 안쪽은 대상(요청 순서), 그 안은 방식(`vector`, `hybrid`, `keyword` 순)이다. 질문 하나의 질의 벡터를
그 질문의 모든 검색에 쓰고 질문이 끝나면 버린다. 멈추면 그 질문의 결과는 버리고 앞 질문까지만 기록한다(FR-021).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from qello_knowledge.domain.embedding import EmbedFailureKind
from qello_knowledge.domain.retrieval import RetrievalMode, RetrievalRequest, RetrievalResult, RetrievalSettings
from qello_knowledge.domain.source_config import RetryPolicy
from qello_knowledge.domain.store import NO_FILTER, SearchFilter
from qello_knowledge.evaluation.prechecks import CostPreview, PreparedTarget, unindexed_count
from qello_knowledge.evaluation.question_set import Question, QuestionSet
from qello_knowledge.evaluation.records import (
    SCHEMA,
    CodeCommit,
    EvidenceRef,
    FilterRecord,
    LedgerRecord,
    OmittedRecord,
    QuestionRecord,
    QuestionResult,
    RunConditions,
    RunRecord,
    SetRef,
    TargetRecord,
    TopHit,
    UsageRecord,
)
from qello_knowledge.evaluation.reuse import CountingProvider, ReusingEmbedder
from qello_knowledge.ports.retrieval import RetrievalStore
from qello_knowledge.retrieval import RetrievalDeps, retrieve

MODE_ORDER = (RetrievalMode.VECTOR, RetrievalMode.HYBRID, RetrievalMode.KEYWORD)
DIGEST_DEPTH = 20
STOP_REASONS = (
    "provider_quota",
    "query_embedding_unavailable",
    "store_unavailable",
    "index_version_changed",
    "interrupted",
)
_VERSION_STOPS = ("index_version_changed", "no_active_index")


@dataclass(frozen=True)
class RunRequest:
    question_set: QuestionSet
    targets: tuple[str, ...]
    modes: tuple[RetrievalMode, ...] = MODE_ORDER
    settings: RetrievalSettings = field(default_factory=RetrievalSettings)
    filters: SearchFilter = NO_FILTER
    usage_target: str | None = None
    retry: RetryPolicy = field(default_factory=lambda: RetryPolicy(max_retries=1))
    allow_query_embedding: bool = False
    max_neurons: float | None = None
    allow_remote_read: bool = False


class _Stop(Exception):  # noqa: N818 - 실행 멈춤 신호
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def result_digest(rows: Sequence[tuple[int, str, str]]) -> str:
    """상위 20건 (순위, 자료원, 위치) 열의 SHA-256(contracts/run-record.md 5절)."""
    payload = json.dumps([list(r) for r in rows[:DIGEST_DEPTH]], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _skipped(question: Question, target: str, mode: RetrievalMode) -> QuestionResult:
    return QuestionResult(
        question=question.id,
        target=target,
        mode=mode.value,
        status="skipped",
        skipped_reason="evidence_unindexed",
        omitted=(),
        keyword_terms=0,
        result_count=0,
        first_evidence_rank=None,
        top5=(),
        unindexed_evidence=len(question.evidence),
        result_digest=None,
    )


def _result(
    question: Question, target: PreparedTarget, mode: RetrievalMode, found: RetrievalResult, by_url: Mapping[str, tuple]
) -> QuestionResult:
    evidence = {(e.source, e.location) for e in question.evidence}
    rows: list[tuple[int, str, str]] = []
    for hit in found.hits:
        doc = by_url.get(hit.provenance.source_url)
        if doc is None:  # 실행 전에 읽은 문서 표에 없다: 대상이 실행 중 바뀌었다
            raise _Stop("index_version_changed")
        rows.append((hit.rank, doc[0], doc[1]))
    first = next((rank for rank, source, location in rows if (source, location) in evidence), None)
    top5 = tuple(TopHit(rank, s, loc, (s, loc) in evidence) for rank, s, loc in rows[:5])
    summary = found.summary
    return QuestionResult(
        question=question.id,
        target=target.name,
        mode=mode.value,
        status=found.status,
        skipped_reason=None,
        omitted=tuple(OmittedRecord(o.search, o.reason.value, o.detail) for o in summary.omitted),
        keyword_terms=summary.keyword_terms,
        result_count=len(found.hits),
        first_evidence_rank=first,
        top5=top5,
        unindexed_evidence=unindexed_count(question, target),
        result_digest=result_digest(rows) if found.status == "ok" and rows else None,
    )


def _check_stop(found: RetrievalResult, target: PreparedTarget) -> None:
    if found.status == "store_unavailable":
        raise _Stop("store_unavailable")
    if found.status in _VERSION_STOPS:
        raise _Stop("index_version_changed")
    version = found.summary.index_version
    if version is not None and version != target.description.index_version:
        raise _Stop("index_version_changed")


def _check_embedding(embedder: ReusingEmbedder, text: str) -> None:
    outcome = embedder.outcome(text)
    if outcome is None:
        return
    if outcome.kind == "error":
        raise _Stop("query_embedding_unavailable")
    if outcome.kind == "item_failure" and outcome.value == EmbedFailureKind.PROVIDER_QUOTA.value:
        raise _Stop("provider_quota")


def _question_record(question: Question) -> QuestionRecord:
    return QuestionRecord(
        id=question.id,
        type=question.type.value,
        label=question.label.value,
        origin=question.origin.value if question.origin else None,
        identifier_form=question.identifier_form.value if question.identifier_form else None,
        query_form=question.query_form.value if question.query_form else None,
        evidence=tuple(EvidenceRef(e.source, e.location) for e in question.evidence),
        metric_target=question.is_metric_target,
    )


def _target_record(target: PreparedTarget) -> TargetRecord:
    d = target.description
    return TargetRecord(
        database=target.name,
        candidate=target.candidate.value,
        index_version=d.index_version,
        index_rule=d.index_rule,
        tokenizer=d.tokenizer,
        embedding_model=d.embedding_model,
        dimension=d.dimension,
        commits=dict(d.commits),
        synced_at=_iso(d.synced_at),
        documents=len(target.documents),
    )


def _ledger(preview: CostPreview, request: RunRequest, needs_embedding: bool) -> LedgerRecord:
    if not needs_embedding:
        return LedgerRecord("none", None, None, None, None, None, None)
    usage = preview.day_usage
    return LedgerRecord(
        target="remote",
        usage_day=usage.usage_day.isoformat() if usage else None,
        day_total=usage.day_total if usage else None,
        remaining=preview.remaining,
        estimated_neurons=preview.estimated_neurons,
        max_calls=preview.max_calls,
        max_neurons=request.max_neurons,
    )


def run(
    request: RunRequest,
    targets: Sequence[PreparedTarget],
    stores: Mapping[str, RetrievalStore],
    embedder: ReusingEmbedder,
    counter: CountingProvider | None,
    *,
    preview: CostPreview,
    clock: Callable[[], datetime],
    run_id: str,
    code_commit: tuple[str | None, bool],
) -> RunRecord:
    """실행 전 검사와 비용 관문을 통과한 대상으로 평가를 돌린다(spec FR-015). 기록 쓰기는 부르는 쪽이 한다."""
    started = clock()
    modes = tuple(m for m in MODE_ORDER if m in request.modes)
    needs_embedding = any(m is not RetrievalMode.KEYWORD for m in modes)
    deps = {
        t.name: RetrievalDeps(
            store=stores[t.name], embedder=embedder, model_version=t.description.embedding_model or ""
        )
        for t in targets
    }
    by_url = {t.name: {d.source_url: (d.source, d.location) for d in t.documents} for t in targets}
    results: list[QuestionResult] = []
    stop: str | None = None
    for question in request.question_set.questions:
        if not question.is_metric_target:
            continue
        text = question.text.strip()
        unindexed = {t.name: unindexed_count(question, t) == len(question.evidence) for t in targets}
        done: list[QuestionResult] = []
        try:
            for target in targets:
                for mode in modes:
                    if unindexed[target.name]:
                        done.append(_skipped(question, target.name, mode))
                        continue
                    found = retrieve(
                        RetrievalRequest(question.text, mode=mode, filters=request.filters, want_context=False),
                        deps[target.name],
                        request.settings,
                    )
                    if mode is not RetrievalMode.KEYWORD:
                        _check_embedding(embedder, text)
                    _check_stop(found, target)
                    done.append(_result(question, target, mode, found, by_url[target.name]))
        except _Stop as halted:
            stop = halted.reason
        except KeyboardInterrupt:
            stop = "interrupted"
        finally:
            embedder.forget(text)
        if stop is not None:
            break
        results.extend(done)
    question_set = request.question_set
    settings = request.settings
    conditions = RunConditions(
        question_set=SetRef(question_set.id, question_set.version, question_set.fingerprint, question_set.confirmed),
        label_commits=question_set.label_commits,
        modes=tuple(m.value for m in modes),
        query_rule=settings.query_rule,
        candidates=settings.candidates,
        rrf_k=settings.rrf_k,
        filters=FilterRecord(tuple(request.filters.source_kinds), tuple(request.filters.artifact_kinds)),
        embedding_model=targets[0].description.embedding_model if targets else None,
        query_vector_reuse=True,
        usage_target=request.usage_target,
        ledger=_ledger(preview, request, needs_embedding),
        started_at=_iso(started) or "",
        finished_at=_iso(clock()) or "",
        code_commit=CodeCommit(*code_commit),
    )
    usage = UsageRecord(
        provider_calls=counter.calls if counter else 0,
        neurons=counter.neurons if counter else 0.0,
        measured_neurons=counter.measured_neurons if counter else 0.0,
        estimated_neurons=counter.estimated_neurons if counter else 0.0,
    )
    return RunRecord(
        schema=SCHEMA,
        run_id=run_id,
        complete=stop is None,
        stop_reason=stop,
        conditions=conditions,
        targets=tuple(_target_record(t) for t in targets),
        questions=tuple(_question_record(q) for q in question_set.questions),
        results=tuple(results),
        usage=usage,
    )


__all__ = ["DIGEST_DEPTH", "MODE_ORDER", "STOP_REASONS", "RunRequest", "result_digest", "run"]
