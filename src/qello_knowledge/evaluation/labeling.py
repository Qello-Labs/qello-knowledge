"""식별자 세트 만들기 도우미(QK-EVL-001 research R-13, spec US2-3·US2-4).

평가 대상의 노출 청크 `(자료원 이름, 위치, 본문)`을 받아 식별자 형태별 후보와 문서 위치를 낸다.
본문 문장은 돌려주지 않는다. 흔한 일부 낱말 제외(두 글자 이하, 문서 절반 이상에 나옴 등)는 코드가 아니라
세트의 `labeling.md`에 적고 사람이 적용한다.
"""

from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from qello_knowledge.domain.secret_rules import find_secrets
from qello_knowledge.evaluation.question_set import IdentifierForm, QueryForm, QuestionSet

Chunk = tuple[str, str, str]  # (자료원 이름, 위치, 본문)
Document = tuple[str, str]  # (자료원 이름, 위치)

# 형태 판별 규칙. 한 낱말은 형태 하나에만 든다(경로 → snake → kebab → 약어 → 숫자 → camel → Pascal 순).
_WORD = re.compile(r"[A-Za-z0-9_]+(?:-[A-Za-z0-9_]+)*")
_URL_PATH = re.compile(r"(?<![\w:/.])/[A-Za-z0-9_.{}-]+(?:/[A-Za-z0-9_.{}-]+)*")  # 호스트가 붙으면 후보 아님
_SNAKE = re.compile(r"[A-Za-z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)+")
_KEBAB = re.compile(r"[a-z][a-z0-9]*(?:-[a-z0-9]+)+")
_ACRONYM = re.compile(r"[A-Z]{2,}[a-z]|[a-z][A-Z]{2,}")
_DIGIT = re.compile(r"[A-Za-z][0-9]+[A-Za-z]|^[A-Za-z]{2,}[0-9]+$")
_CAMEL = re.compile(r"[a-z]+(?:[A-Z][a-z0-9]+)+")
_PASCAL = re.compile(r"(?:[A-Z][a-z0-9]+){2,}")
_CASE_PARTS = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+")
_FORM_ORDER = {form: n for n, form in enumerate(IdentifierForm)}


def form_of(token: str) -> IdentifierForm | None:
    if token.startswith("/"):
        return IdentifierForm.URL_PATH if _URL_PATH.fullmatch(token) else None
    if "_" in token:
        return IdentifierForm.SNAKE if _SNAKE.fullmatch(token) else None
    if "-" in token:
        return IdentifierForm.KEBAB if _KEBAB.fullmatch(token) else None
    if not (token.isascii() and token.isalnum()):
        return None
    if _ACRONYM.search(token):
        return IdentifierForm.ACRONYM
    if len(token) >= 4 and _DIGIT.search(token):
        return IdentifierForm.DIGIT
    if _CAMEL.fullmatch(token):
        return IdentifierForm.CAMEL
    if _PASCAL.fullmatch(token):
        return IdentifierForm.PASCAL
    return None


def split_words(identifier: str) -> tuple[str, ...]:
    """식별자를 이루는 낱말(소문자). 일부 질문의 후보다. 대소문자·숫자 경계 형태는 숫자만인 조각을 뺀다."""
    if identifier.startswith("/"):
        parts = identifier.split("/")
    elif "_" in identifier:
        parts = identifier.split("_")
    elif "-" in identifier:
        parts = identifier.split("-")
    else:
        parts = [p for p in _CASE_PARTS.findall(identifier) if not p.isdigit()]
    return tuple(p.lower() for p in parts if p)


@dataclass(frozen=True)
class Candidate:
    identifier: str
    form: IdentifierForm
    documents: tuple[Document, ...]
    words: tuple[str, ...]
    word_documents: Mapping[str, int] = field(default_factory=dict)  # 낱말을 대소문자 무시로 담은 문서 수


@dataclass(frozen=True)
class CandidateReport:
    candidates: tuple[Candidate, ...]
    secret_excluded: int  # 비밀값 규칙에 걸려 뺀 식별자 수. 값은 남기지 않는다


@dataclass(frozen=True)
class EvidenceDiff:
    question_id: str
    missing: tuple[Document, ...]  # 다시 계산하면 근거인데 파일에 없는 문서
    extra: tuple[Document, ...]  # 파일에 있는데 다시 계산하면 근거가 아닌 문서


def _tokens(body: str) -> Iterable[str]:
    yield from _URL_PATH.findall(body)
    yield from _WORD.findall(body)


def _documents(chunks: Iterable[Chunk]) -> dict[Document, list[str]]:
    docs: dict[Document, list[str]] = defaultdict(list)
    for source, location, body in chunks:
        docs[(source, location)].append(body)
    return docs


def identifier_candidates(chunks: Iterable[Chunk], forms: Sequence[IdentifierForm] | None = None) -> CandidateReport:
    wanted = set(forms or IdentifierForm)
    docs = _documents(chunks)
    found: dict[tuple[IdentifierForm, str], set[Document]] = defaultdict(set)
    secrets: set[str] = set()
    for doc, bodies in docs.items():
        for body in bodies:
            for token in _tokens(body):
                form = form_of(token)
                if form is None or form not in wanted:
                    continue
                if find_secrets(token):
                    secrets.add(token)
                    continue
                found[(form, token)].add(doc)
    lowered = {doc: "\n".join(bodies).casefold() for doc, bodies in docs.items()}
    candidates = []
    for (form, identifier), where in found.items():
        words = split_words(identifier)
        counts = {w: sum(w in text for text in lowered.values()) for w in dict.fromkeys(words)}
        candidates.append(Candidate(identifier, form, tuple(sorted(where)), words, counts))
    candidates.sort(key=lambda c: (_FORM_ORDER[c.form], -len(c.documents), c.identifier))
    return CandidateReport(tuple(candidates), len(secrets))


def recompute_evidence(question_set: QuestionSet, chunks: Iterable[Chunk]) -> tuple[EvidenceDiff, ...]:
    """식별자 세트 질문마다 `label_terms`로 근거 문서를 다시 계산해 파일과 다른 질문만 돌려준다(spec US2-4).

    원형·일부 질문은 식별자 원형의 대소문자 구별 부분 문자열, 문장형은 모든 낱말을 대소문자 무시로 담은 문서다.
    한 문서의 노출 청크를 합쳐 본다.
    """
    docs = _documents(chunks)
    joined = {doc: "\n".join(bodies) for doc, bodies in docs.items()}
    folded = {doc: text.casefold() for doc, text in joined.items()}
    diffs = []
    for question in question_set.questions:
        if question.query_form is None or not question.label_terms:
            continue
        if question.query_form is QueryForm.SENTENCE:
            terms = [t.casefold() for t in question.label_terms]
            computed = {doc for doc, text in folded.items() if all(t in text for t in terms)}
        else:
            term = question.label_terms[0]
            computed = {doc for doc, text in joined.items() if term in text}
        listed = {(e.source, e.location) for e in question.evidence}
        missing, extra = tuple(sorted(computed - listed)), tuple(sorted(listed - computed))
        if missing or extra:
            diffs.append(EvidenceDiff(question.id, missing, extra))
    return tuple(diffs)


__all__ = [
    "Candidate",
    "CandidateReport",
    "EvidenceDiff",
    "form_of",
    "identifier_candidates",
    "recompute_evidence",
    "split_words",
]
