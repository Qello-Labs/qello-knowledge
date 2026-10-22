"""검색·임베딩 입력 형식(research R-09). 색인 쪽 키워드 규칙은 QK-RET-001 research R-04."""

import re

from qello_knowledge.domain.keyword_rules import INDEX_BASELINE, INDEX_IDSPLIT

# camelCase·PascalCase·약어 경계가 있는 영숫자 토큰만 나눈다. snake_case·kebab-case·경로는 토크나이저가 나눈다.
_WORD = re.compile(r"[A-Za-z][A-Za-z0-9]*")
_CASE_BOUNDARY = re.compile(r"[a-z][A-Z]|[A-Z][A-Z][a-z]")
_PART = re.compile(r"[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[A-Z]+|[0-9]+")


def identifier_parts(text):
    """식별자 경계로 나눈 소문자 낱말을 원문 순서로, 중복 없이 돌려준다."""
    parts, seen = [], set()
    for token in _WORD.findall(text):
        if not _CASE_BOUNDARY.search(token):
            continue
        for part in _PART.findall(token):
            word = part.lower()
            if word not in seen:
                seen.add(word)
                parts.append(word)
    return tuple(parts)


def search_header(location, title, heading_path):
    path = heading_path[1:] if heading_path and heading_path[0] == title else heading_path
    return location + "\n" + " > ".join((title, *path))


def search_text(header, body, rule=INDEX_BASELINE):
    text = header + "\n\n" + body
    if rule == INDEX_IDSPLIT:
        parts = identifier_parts(header + "\n" + body)
        if parts:
            text += "\n\n" + " ".join(parts)
    return text


def embedding_text(header, prefix, body):
    return header + "\n\n" + (prefix + "\n" if prefix else "") + body
