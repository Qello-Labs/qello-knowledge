"""질문 세트 파일 읽기·검증·지문(QK-EVL-001 spec FR-001~FR-007, contracts/question-set.md, research R-02·R-03).

검증은 모든 오류를 모아 (질문 ID, 필드, 규칙 이름)으로 돌려준다. 질문 문장·핵심 사실·라벨 근거 낱말과
비밀값 규칙에 걸린 값은 오류·경고·`repr`에 넣지 않는다(FR-006).
"""

from __future__ import annotations

import hashlib
import re
import tomllib
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from qello_knowledge.domain.retrieval import RetrievalSettings
from qello_knowledge.domain.secret_rules import find_secrets
from qello_knowledge.ports.evaluation import TargetDocument


class QuestionType(StrEnum):
    CODE = "code"
    DOC = "doc"
    MEETING = "meeting"
    SYNTHESIS = "synthesis"
    NO_ANSWER = "no_answer"


class LabelStatus(StrEnum):
    DONE = "done"
    PENDING = "pending"


class QuestionOrigin(StrEnum):
    TEAM = "team"
    SYNTHETIC = "synthetic"


class IdentifierForm(StrEnum):
    CAMEL = "camel"
    PASCAL = "pascal"
    ACRONYM = "acronym"
    DIGIT = "digit"
    SNAKE = "snake"
    KEBAB = "kebab"
    URL_PATH = "url_path"


class QueryForm(StrEnum):
    ORIGINAL = "original"
    PARTIAL = "partial"
    SENTENCE = "sentence"


# contracts/question-set.md 4절. 출력과 시험이 같은 이름을 쓴다.
RULES = (
    "toml_invalid",
    "unknown_field",
    "required_missing",
    "bad_format",
    "set_path_mismatch",
    "confirmed_date",
    "source_duplicate",
    "question_id_duplicate",
    "bad_enum",
    "text_empty",
    "text_too_long",
    "text_secret",
    "evidence_unknown_source",
    "evidence_bad_location",
    "evidence_duplicate",
    "evidence_required",
    "evidence_forbidden",
    "form_mixed",
    "form_fields",
)

SET_ID = re.compile(r"[a-z0-9]+(-[a-z0-9]+)*")
QUESTION_ID = re.compile(r"[A-Za-z0-9_-]{1,40}")
COMMIT = re.compile(r"[0-9a-f]{40}")
_SET_FIELDS = {"id", "version", "created", "confirmed", "confirmed_on", "labeling", "origin", "shortfall", "sources"}
_SET_REQUIRED = ("id", "version", "created", "confirmed", "labeling", "sources")
_QUESTION_FIELDS = {
    "id",
    "text",
    "type",
    "label",
    "evidence",
    "facts",
    "origin",
    "query_form",
    "identifier_form",
    "label_terms",
    "original_number",
}
_QUESTION_REQUIRED = ("id", "text", "type", "label", "evidence")
_ID_FORMS = (QueryForm.ORIGINAL, QueryForm.PARTIAL)


@dataclass(frozen=True)
class SourceLabel:
    name: str
    label_commit: str


@dataclass(frozen=True)
class Evidence:
    source: str
    location: str


@dataclass(frozen=True)
class OriginSet:
    id: str
    version: int
    document: str


@dataclass(frozen=True)
class Question:
    id: str
    text: str = field(repr=False)
    type: QuestionType
    label: LabelStatus
    evidence: tuple[Evidence, ...]
    facts: str | None = field(default=None, repr=False)
    origin: QuestionOrigin | None = None
    identifier_form: IdentifierForm | None = None
    query_form: QueryForm | None = None
    label_terms: tuple[str, ...] = field(default=(), repr=False)
    original_number: str | None = None

    @property
    def is_metric_target(self) -> bool:
        return self.label is LabelStatus.DONE and self.type is not QuestionType.NO_ANSWER


@dataclass(frozen=True)
class QuestionSet:
    id: str
    version: int
    sources: tuple[SourceLabel, ...]
    labeling: str
    created: date
    confirmed: bool
    confirmed_on: date | None
    origin_set: OriginSet | None
    shortfall: Mapping[IdentifierForm, int]
    questions: tuple[Question, ...]
    fingerprint: str

    @property
    def label_commits(self) -> dict[str, str]:
        return {s.name: s.label_commit for s in self.sources}

    @property
    def is_identifier_set(self) -> bool:
        return any(q.query_form is not None for q in self.questions)


@dataclass(frozen=True)
class SetIssue:
    question_id: str | None  # 머리 정보면 None. ID를 읽지 못한 질문은 `#<순서>`
    field: str
    rule: str


@dataclass(frozen=True)
class SetWarning:
    question_id: str
    rule: str  # evidence_unindexed | evidence_partly_unindexed
    locations: tuple[str, ...]  # 빠진 근거 문서 위치


@dataclass(frozen=True)
class SetCounts:
    questions: int = 0
    by_type: Mapping[QuestionType, int] = field(default_factory=dict)
    by_label: Mapping[LabelStatus, int] = field(default_factory=dict)
    pending: int = 0


@dataclass(frozen=True)
class SetCheck:
    ok: bool
    issues: tuple[SetIssue, ...] = ()
    counts: SetCounts = field(default_factory=SetCounts)
    warnings: tuple[SetWarning, ...] = ()
    set_id: str | None = None
    version: int | None = None
    fingerprint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """출력용 요약. 질문 문장·핵심 사실·라벨 근거 낱말이 없다."""
        return {
            "ok": self.ok,
            "set": {"id": self.set_id, "version": self.version, "fingerprint": self.fingerprint},
            "counts": {
                "questions": self.counts.questions,
                "by_type": {str(k): v for k, v in self.counts.by_type.items()},
                "by_label": {str(k): v for k, v in self.counts.by_label.items()},
                "pending": self.counts.pending,
            },
            "issues": [{"question_id": i.question_id, "field": i.field, "rule": i.rule} for i in self.issues],
            "warnings": [
                {"question_id": w.question_id, "rule": w.rule, "locations": list(w.locations)} for w in self.warnings
            ],
        }


def _is_date(value: object) -> bool:
    return isinstance(value, date) and not isinstance(value, datetime)


def _is_count(value: object, minimum: int) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= minimum


def _bad_path(value: str) -> bool:
    """contracts 4절 `evidence_bad_location`과 같은 규칙. 저장소·자료원 기준 상대 경로만 받는다."""
    stripped = value.strip()
    if not stripped or stripped != value or value.startswith("/") or "://" in value or "\\" in value:
        return True
    return ".." in value.split("/")


class _Checker:
    def __init__(self) -> None:
        self.issues: list[SetIssue] = []

    def add(self, question_id: str | None, name: str, rule: str) -> None:
        self.issues.append(SetIssue(question_id, name, rule))

    def fields(
        self, table: Mapping[str, Any], allowed: set[str], required: Sequence[str], qid: str | None, prefix: str
    ):
        for key in table:
            if key not in allowed:
                self.add(qid, prefix + key, "unknown_field")
        for key in required:
            if key not in table:
                self.add(qid, prefix + key, "required_missing")

    def enum(self, value: object, kind: type[StrEnum], qid: str | None, name: str):
        if not isinstance(value, str):
            self.add(qid, name, "bad_format")
            return None
        try:
            return kind(value)
        except ValueError:
            self.add(qid, name, "bad_enum")
            return None


def _header(data: Any, path: Path, check: _Checker) -> dict[str, Any]:
    if not isinstance(data, dict):
        check.add(None, "set", "required_missing" if data is None else "bad_format")
        return {}
    check.fields(data, _SET_FIELDS, _SET_REQUIRED, None, "set.")
    out: dict[str, Any] = {}
    set_id, version = data.get("id"), data.get("version")
    if "id" in data:
        if isinstance(set_id, str) and SET_ID.fullmatch(set_id):
            out["id"] = set_id
        else:
            check.add(None, "set.id", "bad_format")
    if "version" in data:
        if _is_count(version, 1):
            out["version"] = version
        else:
            check.add(None, "set.version", "bad_format")
    if "id" in out and "version" in out:
        if path.parent.name != out["id"]:
            check.add(None, "set.id", "set_path_mismatch")
        if path.name != f"v{out['version']}.toml":
            check.add(None, "set.version", "set_path_mismatch")
    for key in ("created", "confirmed_on"):
        if key in data and not _is_date(data[key]):
            check.add(None, f"set.{key}", "bad_format")
    if "created" in data and _is_date(data["created"]):
        out["created"] = data["created"]
    confirmed = data.get("confirmed")
    if "confirmed" in data and not isinstance(confirmed, bool):
        check.add(None, "set.confirmed", "bad_format")
    elif isinstance(confirmed, bool):
        out["confirmed"] = confirmed
        if confirmed != ("confirmed_on" in data):
            check.add(None, "set.confirmed_on", "confirmed_date")
        out["confirmed_on"] = data.get("confirmed_on") if _is_date(data.get("confirmed_on")) else None
    if "labeling" in data:
        labeling = data["labeling"]
        if isinstance(labeling, str) and not _bad_path(labeling):
            out["labeling"] = labeling
        else:
            check.add(None, "set.labeling", "bad_format")
    out["origin_set"] = _origin(data.get("origin"), check) if "origin" in data else None
    out["shortfall"] = _shortfall(data.get("shortfall"), check) if "shortfall" in data else {}
    before = len(check.issues)
    out["sources"] = _sources(data.get("sources"), check) if "sources" in data else ()
    out["sources_ok"] = "sources" in data and len(check.issues) == before
    return out


def _origin(value: Any, check: _Checker) -> OriginSet | None:
    if not isinstance(value, dict):
        check.add(None, "set.origin", "bad_format")
        return None
    check.fields(value, {"id", "version", "document"}, ("id", "version", "document"), None, "set.origin.")
    ok = True
    if "id" in value and not (isinstance(value["id"], str) and SET_ID.fullmatch(value["id"])):
        check.add(None, "set.origin.id", "bad_format")
        ok = False
    if "version" in value and not _is_count(value["version"], 1):
        check.add(None, "set.origin.version", "bad_format")
        ok = False
    if "document" in value and not (isinstance(value["document"], str) and not _bad_path(value["document"])):
        check.add(None, "set.origin.document", "bad_format")
        ok = False
    if not ok or not {"id", "version", "document"} <= value.keys():
        return None
    return OriginSet(value["id"], value["version"], value["document"])


def _shortfall(value: Any, check: _Checker) -> dict[IdentifierForm, int]:
    if not isinstance(value, dict):
        check.add(None, "set.shortfall", "bad_format")
        return {}
    out: dict[IdentifierForm, int] = {}
    for key, count in value.items():
        form = check.enum(key, IdentifierForm, None, f"set.shortfall.{key}")
        if not _is_count(count, 0):
            check.add(None, f"set.shortfall.{key}", "bad_format")
        elif form is not None:
            out[form] = count
    return out


def _sources(value: Any, check: _Checker) -> tuple[SourceLabel, ...]:
    if not isinstance(value, list) or not all(isinstance(v, dict) for v in value):
        check.add(None, "set.sources", "bad_format")
        return ()
    if not value:
        check.add(None, "set.sources", "required_missing")
    out: list[SourceLabel] = []
    seen: set[str] = set()
    for item in value:
        check.fields(item, {"name", "label_commit"}, ("name", "label_commit"), None, "set.sources.")
        name, commit = item.get("name"), item.get("label_commit")
        if "name" in item and not (isinstance(name, str) and name.strip() and name == name.strip()):
            check.add(None, "set.sources.name", "bad_format")
            continue
        if "label_commit" in item and not (isinstance(commit, str) and COMMIT.fullmatch(commit)):
            check.add(None, "set.sources.label_commit", "bad_format")
            continue
        if not isinstance(name, str) or not isinstance(commit, str):
            continue
        if name in seen:
            check.add(None, "set.sources.name", "source_duplicate")
            continue
        seen.add(name)
        out.append(SourceLabel(name, commit))
    return tuple(out)


def _evidence(value: Any, qid: str, sources: set[str] | None, check: _Checker) -> tuple[Evidence, ...] | None:
    """`sources`가 None이면 머리 정보의 자료원 목록이 불량이라 자료원 대조를 하지 않는다(오류 하나에 규칙 하나)."""
    if not isinstance(value, list) or not all(isinstance(v, dict) for v in value):
        check.add(qid, "evidence", "bad_format")
        return None
    out: list[Evidence] = []
    ok = True
    for item in value:
        check.fields(item, {"source", "location"}, ("source", "location"), qid, "evidence.")
        source, location = item.get("source"), item.get("location")
        if "source" in item and not isinstance(source, str):
            check.add(qid, "evidence.source", "bad_format")
            ok = False
        elif isinstance(source, str) and sources is not None and source not in sources:
            check.add(qid, "evidence.source", "evidence_unknown_source")
            ok = False
        if "location" in item and (not isinstance(location, str) or _bad_path(location)):
            check.add(qid, "evidence.location", "evidence_bad_location")
            ok = False
        if not (isinstance(source, str) and isinstance(location, str)):
            ok = False
            continue
        entry = Evidence(source, location)
        if entry in out:
            check.add(qid, "evidence", "evidence_duplicate")
            ok = False
            continue
        out.append(entry)
    return tuple(out) if ok else None


def _question(item: Any, position: int, sources: set[str] | None, seen: set[str], check: _Checker) -> Question | None:
    if not isinstance(item, dict):
        check.add(f"#{position}", "question", "bad_format")
        return None
    raw_id = item.get("id")
    qid = raw_id if isinstance(raw_id, str) and QUESTION_ID.fullmatch(raw_id) else f"#{position}"
    errors_before = len(check.issues)
    check.fields(item, _QUESTION_FIELDS, _QUESTION_REQUIRED, qid, "")
    if "id" in item and qid.startswith("#"):
        check.add(qid, "id", "bad_format")
    elif qid in seen:
        check.add(qid, "id", "question_id_duplicate")
    seen.add(qid)
    text = item.get("text")
    if "text" in item:
        if not isinstance(text, str):
            check.add(qid, "text", "bad_format")
        elif not text.strip():
            check.add(qid, "text", "text_empty")
        elif len(text.strip()) > RetrievalSettings().question_max_chars:
            check.add(qid, "text", "text_too_long")
        elif find_secrets(text):
            check.add(qid, "text", "text_secret")
    qtype = check.enum(item["type"], QuestionType, qid, "type") if "type" in item else None
    label = check.enum(item["label"], LabelStatus, qid, "label") if "label" in item else None
    origin = check.enum(item["origin"], QuestionOrigin, qid, "origin") if "origin" in item else None
    query_form = check.enum(item["query_form"], QueryForm, qid, "query_form") if "query_form" in item else None
    id_form = (
        check.enum(item["identifier_form"], IdentifierForm, qid, "identifier_form")
        if "identifier_form" in item
        else None
    )
    for key in ("facts", "original_number"):
        if key in item and not isinstance(item[key], str):
            check.add(qid, key, "bad_format")
    terms = item.get("label_terms")
    terms_bad = False
    if "label_terms" in item and not (isinstance(terms, list) and all(isinstance(t, str) and t.strip() for t in terms)):
        check.add(qid, "label_terms", "bad_format")
        terms, terms_bad = None, True
    evidence = _evidence(item["evidence"], qid, sources, check) if "evidence" in item else None
    if evidence is not None and qtype is not None and label is not None:
        if qtype is QuestionType.NO_ANSWER and evidence:
            check.add(qid, "evidence", "evidence_forbidden")
        elif qtype is not QuestionType.NO_ANSWER and label is LabelStatus.DONE and not evidence:
            check.add(qid, "evidence", "evidence_required")
    if "query_form" in item:
        if query_form in _ID_FORMS:
            if "identifier_form" not in item:
                check.add(qid, "identifier_form", "form_fields")
            if not terms_bad and (not isinstance(item.get("label_terms"), list) or len(terms or ()) != 1):
                check.add(qid, "label_terms", "form_fields")
        elif query_form is QueryForm.SENTENCE:
            if "identifier_form" in item:
                check.add(qid, "identifier_form", "form_fields")
            if not terms_bad and (not isinstance(item.get("label_terms"), list) or not terms):
                check.add(qid, "label_terms", "form_fields")
    else:
        for key in ("identifier_form", "label_terms"):
            if key in item:
                check.add(qid, key, "form_fields")
    if len(check.issues) != errors_before or qtype is None or label is None or evidence is None:
        return None
    return Question(
        id=qid,
        text=text,
        type=qtype,
        label=label,
        evidence=evidence,
        facts=item.get("facts"),
        origin=origin,
        identifier_form=id_form,
        query_form=query_form,
        label_terms=tuple(terms or ()),
        original_number=item.get("original_number"),
    )


def _warnings(questions: Sequence[Question], documents: Sequence[TargetDocument]) -> tuple[SetWarning, ...]:
    indexed = {(d.source, d.location) for d in documents}
    out = []
    for question in questions:
        if question.type is QuestionType.NO_ANSWER or not question.evidence:
            continue
        missing = tuple(e.location for e in question.evidence if (e.source, e.location) not in indexed)
        if not missing:
            continue
        rule = "evidence_unindexed" if len(missing) == len(question.evidence) else "evidence_partly_unindexed"
        out.append(SetWarning(question.id, rule, missing))
    return tuple(out)


def check_question_set(
    path: Path, documents: Sequence[TargetDocument] | None = None
) -> tuple[QuestionSet | None, SetCheck]:
    """파일 하나를 읽어 검증한다. 통과하면 `QuestionSet`, 거부하면 `None`과 모든 오류를 돌려준다."""
    raw = path.read_bytes()
    fingerprint = hashlib.sha256(raw).hexdigest()
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError):
        return None, SetCheck(ok=False, issues=(SetIssue(None, "file", "toml_invalid"),), fingerprint=fingerprint)
    check = _Checker()
    for key in data:
        if key not in ("set", "question"):
            check.add(None, key, "unknown_field")
    header = _header(data.get("set"), path, check)
    raw_questions = data.get("question")
    if raw_questions is None:
        check.add(None, "question", "required_missing")
        raw_questions = []
    elif not isinstance(raw_questions, list):
        check.add(None, "question", "bad_format")
        raw_questions = []
    sources = {s.name for s in header.get("sources", ())} if header.get("sources_ok") else None
    seen: set[str] = set()
    questions = [_question(item, n, sources, seen, check) for n, item in enumerate(raw_questions, start=1)]
    with_form = [isinstance(q, dict) and "query_form" in q for q in raw_questions]
    if any(with_form) and not all(with_form):
        check.add(None, "question.query_form", "form_mixed")
    parsed = [q for q in questions if q is not None]
    counts = SetCounts(
        questions=len(raw_questions),
        by_type=dict(Counter(q.type for q in parsed)),
        by_label=dict(Counter(q.label for q in parsed)),
        pending=sum(q.label is LabelStatus.PENDING for q in parsed),
    )
    base = dict(set_id=header.get("id"), version=header.get("version"), fingerprint=fingerprint, counts=counts)
    if check.issues:
        return None, SetCheck(ok=False, issues=tuple(check.issues), **base)
    question_set = QuestionSet(
        id=header["id"],
        version=header["version"],
        sources=header["sources"],
        labeling=header["labeling"],
        created=header["created"],
        confirmed=header["confirmed"],
        confirmed_on=header["confirmed_on"],
        origin_set=header["origin_set"],
        shortfall=header["shortfall"],
        questions=tuple(parsed),
        fingerprint=fingerprint,
    )
    warnings = _warnings(question_set.questions, documents) if documents is not None else ()
    return question_set, SetCheck(ok=True, warnings=warnings, **base)


__all__ = [
    "RULES",
    "Evidence",
    "IdentifierForm",
    "LabelStatus",
    "OriginSet",
    "Question",
    "QuestionOrigin",
    "QuestionSet",
    "QuestionType",
    "QueryForm",
    "SetCheck",
    "SetCounts",
    "SetIssue",
    "SetWarning",
    "SourceLabel",
    "check_question_set",
]
