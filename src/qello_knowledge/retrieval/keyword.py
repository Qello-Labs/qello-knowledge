"""질의 쪽 키워드 규칙(QK-RET-001 research R-03 결정 1, spec FR-017).

질문을 낱말 배열로 바꾼다. 연산자를 문자열로 잇지 않고, 낱말마다 저장소 함수가 이스케이프한다.
대문자 `OR`는 소문자로 바꿔 점수 질의(낱말을 ` OR `로 잇는다)에서 연산자로 해석되지 않게 한다(독립 재검토 N1).
"""

from __future__ import annotations

import re

from qello_knowledge.domain.keyword_rules import QUERY_RULES

MAX_TERMS = 16
MAX_TERM_CHARS = 64
STRIP_CHARS = "?!.,;:'\"`()[]<>“”‘’「」『』？！，。、"
# 긴 것부터 하나만 뗀다. 남는 부분이 2글자 이상일 때만.
PARTICLES = (
    "에서", "으로", "에게", "까지", "부터", "처럼", "보다", "하고", "이랑",
    "은", "는", "이", "가", "을", "를", "의", "에", "로", "와", "과", "도", "만",
)  # fmt: skip
QUESTION_ENDINGS = frozenset({"뭐야", "뭔가요", "무엇", "어디", "어떻게", "알려줘", "있나요"})
_OR_WORD = re.compile(r"(?<![0-9A-Za-z_])OR(?![0-9A-Za-z_])")


def _hangul(char: str) -> bool:
    return "가" <= char <= "힣"


def _strip_particle(term: str) -> str:
    if len(term) < 3 or not _hangul(term[-1]):
        return term
    for particle in PARTICLES:
        if term.endswith(particle) and len(term) - len(particle) >= 2:
            return term[: -len(particle)]
    return term


def _v1(question: str) -> tuple[str, ...]:
    terms: list[str] = []
    seen: set[str] = set()
    for raw in question.split():
        term = _strip_particle(raw.strip(STRIP_CHARS))
        if term == "OR":
            term = "or"
        if not term or (len(term) == 1 and _hangul(term)) or term in QUESTION_ENDINGS:
            continue
        if len(term) > MAX_TERM_CHARS or term.casefold() in seen:
            continue
        seen.add(term.casefold())
        terms.append(term)
        if len(terms) == MAX_TERMS:
            break
    return tuple(terms)


def _raw(question: str) -> tuple[str, ...]:
    text = _OR_WORD.sub("or", question.strip())
    return (text,) if text else ()


def keyword_query(question: str, rule: str) -> tuple[str, ...]:
    """질문을 키워드 검색 낱말 배열로 바꾼다. 저장소를 부르지 않는다."""
    if rule not in QUERY_RULES:
        raise ValueError("알 수 없는 질의 쪽 키워드 규칙")
    return _v1(question) if rule == "kw-query-v1" else _raw(question)
