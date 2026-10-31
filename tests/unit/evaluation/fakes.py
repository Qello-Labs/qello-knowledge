"""평가 단위 시험용 가짜(QK-EVL-001 tasks T004). 외부 호출과 DB 접속이 없다."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

from qello_knowledge.domain.embedding import BudgetSettings
from qello_knowledge.domain.generation import AnswerUsageToday
from qello_knowledge.domain.source_config import RetryPolicy
from qello_knowledge.embedding.fake import FakeEmbeddingProvider
from qello_knowledge.embedding.service import EmbeddingService
from qello_knowledge.ports.evaluation import TargetDescription, TargetDocument
from tests.unit.fakes import InMemoryUsageLedger, MemoryEmbeddingStore
from tests.unit.retrieval.fakes import FakeRetrievalStore, no_block

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "evaluation" / "question_sets"
GOLDEN = FIXTURES / "fixture-golden" / "v1.toml"
IDENTIFIERS = FIXTURES / "fixture-identifiers" / "v1.toml"
COMMIT = "0" * 39 + "1"
SOURCE = "dnd-backend-docs"


def question_set_file(root: Path, set_id: str, version: int, text: str) -> Path:
    """contracts/question-set.md 1절 위치 규칙대로 `<root>/<set_id>/v<version>.toml`을 만든다."""
    path = root / set_id / f"v{version}.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def description(
    database: str = "qk_eval_baseline_000000000000",
    *,
    index_version: str | None = "iv-4c0bc4fcc642",
    index_rule: str = "kw-index-baseline-v1",
    tokenizer: str | None = "TokenBigramSplitSymbol",
    commits: Mapping[str, str] | None = None,
    model: str | None = "@cf/baai/bge-m3",
    dimension: int | None = 1024,
    sources: Sequence[str] = (SOURCE,),
    unlocated: int = 0,
) -> TargetDescription:
    return TargetDescription(
        database=database,
        index_version=index_version,
        embedding_model=model,
        dimension=dimension,
        index_rule=index_rule,
        tokenizer=tokenizer,
        commits=dict(commits if commits is not None else {SOURCE: COMMIT}),
        synced_at=datetime(2026, 10, 31, 9, 0, tzinfo=UTC),
        sources=tuple(sources),
        unlocated_documents=unlocated,
    )


def document(location: str, url: str | None = None, source: str = SOURCE) -> TargetDocument:
    return TargetDocument(source=source, location=location, source_url=url or f"https://example.invalid/{location}")


@dataclass
class FakeEvalTarget:
    """`EvalTarget` 가짜. 읽은 횟수를 센다. `fail`이면 읽을 때 그 예외를 낸다."""

    description: TargetDescription = field(default_factory=description)
    docs: tuple[TargetDocument, ...] = ()
    store: FakeRetrievalStore = field(default_factory=FakeRetrievalStore)
    fail: Exception | None = None
    reads: int = 0

    def describe(self) -> TargetDescription:
        self.reads += 1
        if self.fail is not None:
            raise self.fail
        return self.description

    def documents(self) -> tuple[TargetDocument, ...]:
        self.reads += 1
        if self.fail is not None:
            raise self.fail
        return self.docs


def usage(day_total: float = 100.0, query_reserve: int = 500) -> AnswerUsageToday:
    return AnswerUsageToday(
        usage_day=date(2026, 10, 31),
        generation_used=day_total / 2,
        query_embedding_used=0.0,
        answer_total=day_total / 2,
        index_used=day_total / 2,
        day_total=day_total,
        query_reserve=query_reserve,
        query_reserve_exceeded=False,
    )


@dataclass
class FakeDayUsageReader:
    """`DayUsageReader` 가짜. 읽은 횟수를 센다."""

    value: AnswerUsageToday | Exception = field(default_factory=usage)
    reads: int = 0

    def today(self) -> AnswerUsageToday:
        self.reads += 1
        if isinstance(self.value, Exception):
            raise self.value
        return self.value


def reusing_service(provider: FakeEmbeddingProvider | None = None, retry: RetryPolicy | None = None):
    """질의 경로 설정(재시도 1회, 대기 없음)의 임베딩 서비스를 `CountingProvider`·`ReusingEmbedder`로 감싼다."""
    from qello_knowledge.evaluation.reuse import CountingProvider, ReusingEmbedder

    counter = CountingProvider(provider or FakeEmbeddingProvider())
    budget = BudgetSettings()
    service = EmbeddingService(
        counter,
        MemoryEmbeddingStore(),
        InMemoryUsageLedger(budget),
        budget,
        no_block,
        retry_policy=retry or RetryPolicy(max_retries=1),
        sleep=lambda seconds: None,
    )
    return ReusingEmbedder(service), counter


def question_record(
    qid: str,
    *,
    form: str | None = "original",
    identifier: str | None = "camel",
    metric: bool = True,
    qtype: str = "code",
    label: str = "done",
    evidence=(("dnd-backend-docs", "docs/A.md"),),
):
    from qello_knowledge.evaluation.records import EvidenceRef, QuestionRecord

    return QuestionRecord(
        id=qid,
        type=qtype,
        label=label,
        origin="synthetic",
        identifier_form=identifier if form in ("original", "partial") else None,
        query_form=form,
        evidence=tuple(EvidenceRef(*e) for e in evidence),
        metric_target=metric,
    )


def result(
    qid: str,
    *,
    target: str = "qk_eval_a",
    mode: str = "keyword",
    rank: int | None = None,
    count: int = 0,
    top: tuple[bool, ...] = (),
    status: str | None = None,
    omitted=(),
    terms: int = 1,
    digest: str | None = None,
):
    """손으로 정한 순위 하나. `top`은 상위 5건의 근거 여부."""
    from qello_knowledge.evaluation.records import OmittedRecord, QuestionResult, TopHit

    status = status or ("ok" if count else "no_results")
    hits = tuple(TopHit(n, "dnd-backend-docs", f"docs/hit-{n}.md", ev) for n, ev in enumerate(top, start=1))
    return QuestionResult(
        question=qid,
        target=target,
        mode=mode,
        status=status,
        skipped_reason="evidence_unindexed" if status == "skipped" else None,
        omitted=tuple(OmittedRecord(*o) for o in omitted),
        keyword_terms=terms,
        result_count=count,
        first_evidence_rank=rank,
        top5=hits,
        unindexed_evidence=0,
        result_digest=digest if digest is not None else (("d" * 64) if count else None),
    )


def run_record(
    questions,
    results,
    *,
    targets=(("qk_eval_a", "A"),),
    candidates: int = 20,
    run_id: str | None = None,
    complete: bool = True,
    **conditions,
):
    """비교·지표 시험용 실행 기록. 조건은 키워드 인자로 바꾼다."""
    from qello_knowledge.evaluation.records import (
        SCHEMA,
        CodeCommit,
        FilterRecord,
        LedgerRecord,
        RunConditions,
        RunRecord,
        SetRef,
        TargetRecord,
        UsageRecord,
    )

    values = dict(
        question_set=SetRef("fixture-identifiers", 1, "f" * 64, True),
        label_commits={"dnd-backend-docs": COMMIT},
        modes=("vector", "hybrid", "keyword"),
        query_rule="kw-query-v1",
        candidates=candidates,
        rrf_k=60,
        filters=FilterRecord((), ()),
        embedding_model="@cf/baai/bge-m3",
        query_vector_reuse=True,
        usage_target=targets[0][0],
        ledger=LedgerRecord("none", None, None, None, None, None, None),
        started_at="2026-10-31T09:00:00Z",
        finished_at="2026-10-31T09:01:00Z",
        code_commit=CodeCommit("c" * 40, False),
    )
    values.update(conditions)
    target_records = tuple(
        TargetRecord(
            database=name,
            candidate=candidate,
            index_version="iv-8b7e93b22051" if candidate == "B" else "iv-4c0bc4fcc642",
            index_rule="kw-index-idsplit-v1" if candidate == "B" else "kw-index-baseline-v1",
            tokenizer="TokenBigramSplitSymbolAlpha" if candidate == "C" else "TokenBigramSplitSymbol",
            embedding_model="@cf/baai/bge-m3",
            dimension=1024,
            commits={"dnd-backend-docs": COMMIT},
            synced_at="2026-10-31T08:00:00Z",
            documents=3,
        )
        for name, candidate in targets
    )
    return RunRecord(
        schema=SCHEMA,
        run_id=run_id or "evl-20261031T090000Z-0000abcd",
        complete=complete,
        stop_reason=None if complete else "provider_quota",
        conditions=RunConditions(**values),
        targets=target_records,
        questions=tuple(questions),
        results=tuple(results),
        usage=UsageRecord(provider_calls=0, neurons=0.0, measured_neurons=0.0, estimated_neurons=0.0),
    )


__all__ = [
    "COMMIT",
    "GOLDEN",
    "IDENTIFIERS",
    "SOURCE",
    "FakeDayUsageReader",
    "FakeEvalTarget",
    "description",
    "document",
    "question_record",
    "question_set_file",
    "result",
    "reusing_service",
    "run_record",
    "usage",
]
