"""실행 기록 `qk-evl-001-run/v1`(QK-EVL-001 contracts/run-record.md, research R-10).

질문 문장, 핵심 사실, 라벨 근거 낱말, 검색어 낱말, 청크 본문, 청크 ID, 질의 벡터, 점수, 접속 정보는 두지 않는다.
읽기는 계약의 키 목록과 정확히 같은지 확인한다. 지표·비교표는 이 기록만으로 다시 계산한다(spec FR-020).
"""

from __future__ import annotations

import json
import os
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, NamedTuple

SCHEMA = "qk-evl-001-run/v1"
PARTIAL_SUFFIX = ".partial"


class RecordError(ValueError):
    """기록 파일이 계약과 다르다. 문구에 값이 없다."""


class SetRef(NamedTuple):
    id: str
    version: int
    fingerprint: str
    confirmed: bool


class FilterRecord(NamedTuple):
    source_kinds: tuple[str, ...]
    artifact_kinds: tuple[str, ...]


class CodeCommit(NamedTuple):
    sha: str | None
    dirty: bool


class LedgerRecord(NamedTuple):
    target: str  # "remote" | "none"
    usage_day: str | None
    day_total: float | None
    remaining: float | None
    estimated_neurons: float | None
    max_calls: int | None
    max_neurons: float | None


class EvidenceRef(NamedTuple):
    source: str
    location: str


class OmittedRecord(NamedTuple):
    search: str
    reason: str
    detail: str | None


class TopHit(NamedTuple):
    rank: int
    source: str
    location: str
    evidence: bool


@dataclass(frozen=True)
class RunConditions:
    question_set: SetRef
    label_commits: Mapping[str, str]
    modes: tuple[str, ...]
    query_rule: str
    candidates: int
    rrf_k: int
    filters: FilterRecord
    embedding_model: str | None
    query_vector_reuse: bool
    usage_target: str | None
    ledger: LedgerRecord
    started_at: str
    finished_at: str
    code_commit: CodeCommit


@dataclass(frozen=True)
class TargetRecord:
    database: str
    candidate: str
    index_version: str | None
    index_rule: str
    tokenizer: str | None
    embedding_model: str | None
    dimension: int | None
    commits: Mapping[str, str]
    synced_at: str | None
    documents: int


@dataclass(frozen=True)
class QuestionRecord:
    id: str
    type: str
    label: str
    origin: str | None
    identifier_form: str | None
    query_form: str | None
    evidence: tuple[EvidenceRef, ...]
    metric_target: bool


@dataclass(frozen=True)
class QuestionResult:
    question: str
    target: str
    mode: str
    status: str  # ok | no_results | skipped | RetrievalFailure 값
    skipped_reason: str | None
    omitted: tuple[OmittedRecord, ...]
    keyword_terms: int
    result_count: int
    first_evidence_rank: int | None
    top5: tuple[TopHit, ...]
    unindexed_evidence: int
    result_digest: str | None


@dataclass(frozen=True)
class UsageRecord:
    provider_calls: int
    neurons: float
    measured_neurons: float
    estimated_neurons: float


@dataclass(frozen=True)
class RunRecord:
    schema: str
    run_id: str
    complete: bool
    stop_reason: str | None
    conditions: RunConditions
    targets: tuple[TargetRecord, ...]
    questions: tuple[QuestionRecord, ...]
    results: tuple[QuestionResult, ...]
    usage: UsageRecord


def new_run_id(now: datetime, token: str | None = None) -> str:
    return f"evl-{now:%Y%m%dT%H%M%SZ}-{token or secrets.token_hex(4)}"


def _tuple(value: NamedTuple) -> dict[str, Any]:
    return {k: (list(v) if isinstance(v, tuple) else v) for k, v in value._asdict().items()}


def record_to_json(record: RunRecord) -> dict[str, Any]:
    c = record.conditions
    return {
        "schema": record.schema,
        "run_id": record.run_id,
        "complete": record.complete,
        "stop_reason": record.stop_reason,
        "conditions": {
            "question_set": _tuple(c.question_set),
            "label_commits": dict(c.label_commits),
            "modes": list(c.modes),
            "query_rule": c.query_rule,
            "candidates": c.candidates,
            "rrf_k": c.rrf_k,
            "filters": _tuple(c.filters),
            "embedding_model": c.embedding_model,
            "query_vector_reuse": c.query_vector_reuse,
            "usage_target": c.usage_target,
            "ledger": _tuple(c.ledger),
            "started_at": c.started_at,
            "finished_at": c.finished_at,
            "code_commit": _tuple(c.code_commit),
        },
        "targets": [{**t.__dict__, "commits": dict(t.commits)} for t in record.targets],
        "questions": [{**q.__dict__, "evidence": [_tuple(e) for e in q.evidence]} for q in record.questions],
        "results": [
            {**r.__dict__, "omitted": [_tuple(o) for o in r.omitted], "top5": [_tuple(h) for h in r.top5]}
            for r in record.results
        ],
        "usage": dict(record.usage.__dict__),
    }


def _keys(data: Any, expected: set[str]) -> dict[str, Any]:
    if not isinstance(data, dict) or set(data) != expected:
        raise RecordError("실행 기록의 키가 계약과 다르다")
    return data


def _fields(kind: type) -> set[str]:
    return set(getattr(kind, "_fields", None) or kind.__dataclass_fields__)


def _named(kind: type, data: Any) -> Any:
    values = _keys(data, _fields(kind))
    return kind(**{k: (tuple(v) if isinstance(v, list) else v) for k, v in values.items()})


def _int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _opt(value: Any, check) -> bool:
    return value is None or check(value)


def _str(value: Any) -> bool:
    return isinstance(value, str)


def _num(value: Any) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool)


def _check_values(record: RunRecord) -> None:
    """지표·비교 계산이 쓰는 값의 형식. 어긋나면 `RecordError`(contracts/cli.md 3절 종료 2)."""
    c = record.conditions
    ok = (
        all(_str(v) for v in (record.run_id, c.query_rule, c.started_at, c.finished_at))
        and isinstance(record.complete, bool)
        and _opt(record.stop_reason, _str)
        and _int(c.candidates)
        and _int(c.rrf_k)
        and all(_str(m) for m in c.modes)
        and all(_str(k) and _str(v) for k, v in c.label_commits.items())
        and _str(c.question_set.id)
        and _int(c.question_set.version)
        and _str(c.question_set.fingerprint)
    )
    ok = ok and all(
        _str(t.database)
        and _str(t.candidate)
        and _int(t.documents)
        and all(_str(k) and _str(v) for k, v in t.commits.items())
        for t in record.targets
    )
    ok = ok and all(
        _str(q.id)
        and _str(q.type)
        and _str(q.label)
        and isinstance(q.metric_target, bool)
        and all(_opt(v, _str) for v in (q.origin, q.identifier_form, q.query_form))
        and all(_str(e.source) and _str(e.location) for e in q.evidence)
        for q in record.questions
    )
    ok = ok and all(
        all(_str(v) for v in (r.question, r.target, r.mode, r.status))
        and all(_int(v) for v in (r.keyword_terms, r.result_count, r.unindexed_evidence))
        and _opt(r.first_evidence_rank, _int)
        and _opt(r.skipped_reason, _str)
        and _opt(r.result_digest, _str)
        and all(_str(o.search) and _str(o.reason) and _opt(o.detail, _str) for o in r.omitted)
        and all(_int(h.rank) and _str(h.source) and _str(h.location) and isinstance(h.evidence, bool) for h in r.top5)
        for r in record.results
    )
    u = record.usage
    ok = ok and _int(u.provider_calls) and all(_num(v) for v in (u.neurons, u.measured_neurons, u.estimated_neurons))
    if not ok:
        raise RecordError("실행 기록 값의 형식이 계약과 다르다")


def record_from_json(data: Any) -> RunRecord:
    top = _keys(data, _fields(RunRecord))
    if top["schema"] != SCHEMA:
        raise RecordError("실행 기록 스키마가 다르다")
    try:
        c = _keys(top["conditions"], _fields(RunConditions))
        conditions = RunConditions(
            question_set=_named(SetRef, c["question_set"]),
            label_commits=dict(c["label_commits"]),
            modes=tuple(c["modes"]),
            query_rule=c["query_rule"],
            candidates=c["candidates"],
            rrf_k=c["rrf_k"],
            filters=_named(FilterRecord, c["filters"]),
            embedding_model=c["embedding_model"],
            query_vector_reuse=c["query_vector_reuse"],
            usage_target=c["usage_target"],
            ledger=_named(LedgerRecord, c["ledger"]),
            started_at=c["started_at"],
            finished_at=c["finished_at"],
            code_commit=_named(CodeCommit, c["code_commit"]),
        )
        targets = tuple(
            TargetRecord(**{**_keys(t, _fields(TargetRecord)), "commits": dict(t["commits"])}) for t in top["targets"]
        )
        questions = tuple(
            QuestionRecord(
                **{
                    **_keys(q, _fields(QuestionRecord)),
                    "evidence": tuple(_named(EvidenceRef, e) for e in q["evidence"]),
                }
            )
            for q in top["questions"]
        )
        results = tuple(
            QuestionResult(
                **{
                    **_keys(r, _fields(QuestionResult)),
                    "omitted": tuple(_named(OmittedRecord, o) for o in r["omitted"]),
                    "top5": tuple(_named(TopHit, h) for h in r["top5"]),
                }
            )
            for r in top["results"]
        )
        usage = UsageRecord(**_keys(top["usage"], _fields(UsageRecord)))
    except (TypeError, AttributeError, ValueError) as exc:
        raise RecordError("실행 기록 형식이 계약과 다르다") from exc
    record = RunRecord(
        schema=top["schema"],
        run_id=top["run_id"],
        complete=top["complete"],
        stop_reason=top["stop_reason"],
        conditions=conditions,
        targets=targets,
        questions=questions,
        results=results,
        usage=usage,
    )
    _check_values(record)
    return record


def write_record(record: RunRecord, path: Path) -> None:
    """이미 있는 경로에는 쓰지 않는다. 임시 이름에 쓴 뒤 이름을 바꾼다(contracts/run-record.md 7절)."""
    if path.exists():
        raise FileExistsError(str(path))
    partial = path.with_name(path.name + PARTIAL_SUFFIX)
    text = json.dumps(record_to_json(record), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    partial.write_text(text, encoding="utf-8")
    os.replace(partial, path)


def read_record(path: Path) -> RunRecord:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise RecordError("실행 기록을 읽을 수 없다") from exc
    return record_from_json(data)


__all__ = [
    "PARTIAL_SUFFIX",
    "SCHEMA",
    "CodeCommit",
    "EvidenceRef",
    "FilterRecord",
    "LedgerRecord",
    "OmittedRecord",
    "QuestionRecord",
    "QuestionResult",
    "RecordError",
    "RunConditions",
    "RunRecord",
    "SetRef",
    "TargetRecord",
    "TopHit",
    "UsageRecord",
    "new_run_id",
    "read_record",
    "record_from_json",
    "record_to_json",
    "write_record",
]
