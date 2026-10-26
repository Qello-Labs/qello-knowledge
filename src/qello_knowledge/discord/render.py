"""US1 기본 답변·출처 표시. 무력화와 정교한 분할은 US3·US4에서 확장한다."""

import re
from datetime import timedelta, timezone

from qello_knowledge.domain.discord import RenderedReply
from qello_knowledge.domain.generation import Citation, GenerationResult

MESSAGE_LIMIT = 2000
SOURCE_HEADER = "자료 기준: 색인된 문서"
VERSION_MAX_CHARS = 12
KST = timezone(timedelta(hours=9))


def citation_line(citation: Citation, *, title_max_chars: int = 80, link_max_chars: int = 300) -> str:
    title = citation.title
    if len(title) > title_max_chars:
        title = title[:title_max_chars] + "…"
    url = citation.source_url
    link = "링크 없음" if not url else ("링크 생략(길이 초과)" if len(url) > link_max_chars else f"<{url}>")
    version = citation.source_version[
        : 7 if re.fullmatch(r"[0-9a-fA-F]{40}", citation.source_version) else VERSION_MAX_CHARS
    ]
    modified = (
        citation.source_modified_at.astimezone(KST).strftime("%Y-%m-%d") if citation.source_modified_at else "미상"
    )
    collected = citation.collected_at.astimezone(KST).strftime("%Y-%m-%d %H:%M KST")
    return f"[{citation.source_id}] {title} · {link} · 버전 {version} · 수정 {modified} · 수집 {collected}"


def render(
    result: GenerationResult,
    *,
    private: bool = False,
    title_max_chars: int = 80,
    link_max_chars: int = 300,
    max_messages: int = 4,
) -> RenderedReply:
    messages = [result.answer[i : i + MESSAGE_LIMIT] for i in range(0, len(result.answer), MESSAGE_LIMIT)] or [""]
    for index, citation in enumerate(result.citations):
        line = citation_line(citation, title_max_chars=title_max_chars, link_max_chars=link_max_chars)
        if len(line) + len(SOURCE_HEADER) + 1 > MESSAGE_LIMIT:
            raise ValueError("출처 항목 길이 초과")
        addition = ("\n\n" + SOURCE_HEADER + "\n" if index == 0 else "\n") + line
        if len(messages[-1]) + len(addition) <= MESSAGE_LIMIT:
            messages[-1] += addition
        else:
            messages.append(SOURCE_HEADER + "\n" + line)
    if len(messages) > max_messages:
        raise ValueError("기본 표시 메시지 수 초과")
    return RenderedReply(tuple(messages), private)
