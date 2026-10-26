"""US1 기본 답변·출처 표시. 무력화와 정교한 분할은 US3·US4에서 확장한다."""

import math
import re
from datetime import timedelta, timezone

from qello_knowledge.discord.notices import OUTPUT_TRUNCATED, SOURCE_UNVERIFIED, status_notice
from qello_knowledge.domain.discord import RenderedReply
from qello_knowledge.domain.generation import Citation, GenerationResult, GenerationStatus
from qello_knowledge.domain.retrieval import RetrievalFailure

MESSAGE_LIMIT = 2000
SOURCE_HEADER = "자료 기준: 색인된 문서"
VERSION_MAX_CHARS = 12
KST = timezone(timedelta(hours=9))
FORMAT_CHARACTERS = frozenset("[]()*_~`|>\\<")
BODY_OMITTED = "(답변이 길어 일부를 생략했습니다.)"
LONG_LINK_OMITTED = "(긴 링크 생략)"
SOURCE_ITEM_FIXED_CHARS = len("[S20]  · <> · 버전  · 수정 2000-12-31 · 수집 2000-12-31 23:59 KST\n")
FENCE = re.compile(r"```([^\n`]*)\n?")


def source_item_max_chars(title_max_chars: int, link_max_chars: int) -> int:
    # 제목의 모든 글자를 이스케이프한 길이 + 말줄임표 한 글자, 버전 최대 12자도 이스케이프한다.
    return SOURCE_ITEM_FIXED_CHARS + 2 * title_max_chars + 1 + link_max_chars + 2 * VERSION_MAX_CHARS


SOURCE_ITEM_MAX_CHARS = source_item_max_chars(80, 300)


def source_capacity(title_max_chars: int, link_max_chars: int, *, expand_top: int = 8) -> tuple[int, int]:
    per_message = (MESSAGE_LIMIT - len(SOURCE_HEADER + "\n")) // source_item_max_chars(title_max_chars, link_max_chars)
    return per_message, math.ceil(expand_top / per_message) if per_message else expand_top + 1


def _merge_spans(spans):
    merged = []
    for start, end in sorted(spans):
        if merged and start < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def _link_spans(text):
    spans = [m.span() for m in re.finditer(r"<https?://[^>\n]*>|https?://[^\s<>]+", text)]
    for match in re.finditer(r"\[[^\]\n]*\]\(", text):
        index, depth = match.end(), 1
        while index < len(text) and depth:
            char = text[index]
            if char == "\\":
                index += 2
                continue
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
            index += 1
        if not depth:
            spans.append((match.start(), index))
    return _merge_spans(spans)


def _shorten_long_links(text):
    for start, end in reversed(_link_spans(text)):
        if end - start > MESSAGE_LIMIT:
            text = text[:start] + LONG_LINK_OMITTED + text[end:]
    return text


def _protected_spans(text):
    return _merge_spans(
        _link_spans(text)
        + [m.span() for m in re.finditer(r"\[S[0-9]{1,3}\]|\\[\s\S]", text)]
        + [m.span() for m in FENCE.finditer(text)]
    )


def _safe_cut(position, spans):
    for start, end in spans:
        if start < position < end:
            return start
    return position


def _choose_cut(text, start, ceiling, spans):
    for pattern in (r"\n[ \t]*\n", r"(?<=[.!?。！？])\s+", r"\s+"):
        for match in reversed(list(re.finditer(pattern, text[start:ceiling]))):
            cut = _safe_cut(start + match.end(), spans)
            if cut > start and FENCE.sub("", text[start:cut]).strip():
                return cut
    return _safe_cut(ceiling, spans)


def _language_after(text, language):
    for match in FENCE.finditer(text):
        language = match.group(1).strip() if language is None else None
    return language


def _close_fence(text, language):
    return ("" if text.endswith("\n") else "\n") + "```" if language is not None else ""


def _split_body(text, max_messages):
    text = _shorten_long_links(text)
    spans = _protected_spans(text)
    messages, position, language = [], 0, None
    for slot in range(max_messages):
        prefix = f"```{language}\n" if language is not None else ""
        tail = text[position:]
        tail_language = _language_after(tail, language)
        final = prefix + tail + _close_fence(tail, tail_language)
        if len(final) <= MESSAGE_LIMIT:
            return (*messages, final), False
        last = slot == max_messages - 1
        notice = "\n\n" + BODY_OMITTED if last else ""
        ceiling = min(len(text), position + MESSAGE_LIMIT - len(prefix) - len(notice))
        cut = _choose_cut(text, position, ceiling, spans)
        part = text[position:cut]
        next_language = _language_after(part, language)
        suffix = _close_fence(part, next_language)
        if len(prefix + part + suffix + notice) > MESSAGE_LIMIT:
            cut = _choose_cut(text, position, ceiling - 4, spans)
            part = text[position:cut]
            next_language = _language_after(part, language)
            suffix = _close_fence(part, next_language)
        if cut <= position:
            raise ValueError("메시지 하나에 담을 수 없는 서식 표시")
        messages.append(prefix + part + suffix + notice)
        if last:
            return tuple(messages), True
        position, language = cut, next_language
    raise ValueError("본문 메시지 자리 없음")


def _source_messages(citations, title_max_chars, link_max_chars):
    messages = []
    for citation in citations:
        line = citation_line(citation, title_max_chars=title_max_chars, link_max_chars=link_max_chars)
        if len(SOURCE_HEADER) + 1 + len(line) > MESSAGE_LIMIT:
            raise ValueError("출처 항목 길이 초과")
        if messages and len(messages[-1]) + 1 + len(line) <= MESSAGE_LIMIT:
            messages[-1] += "\n" + line
        else:
            messages.append(SOURCE_HEADER + "\n" + line)
    return messages


def neutralize(text: str) -> str:
    return "".join("\\" + char if char in FORMAT_CHARACTERS else char for char in text)


def _safe_url(url: str) -> str:
    # 링크를 닫는 글자·공백·제어 문자는 URL 내부의 문자로 보낸다.
    return "".join(
        f"%{ord(char):02X}" if char in "<>\\" or ord(char) <= 32 or ord(char) == 127 else char for char in url
    )


def citation_line(citation: Citation, *, title_max_chars: int = 80, link_max_chars: int = 300) -> str:
    title = citation.title
    if len(title) > title_max_chars:
        title = title[:title_max_chars] + "…"
    title = neutralize(title)
    url = _safe_url(citation.source_url)
    link = "링크 없음" if not url else ("링크 생략(길이 초과)" if len(url) > link_max_chars else f"<{url}>")
    version = citation.source_version[
        : 7 if re.fullmatch(r"[0-9a-fA-F]{40}", citation.source_version) else VERSION_MAX_CHARS
    ]
    version = neutralize(version)
    modified = (
        citation.source_modified_at.astimezone(KST).strftime("%Y-%m-%d") if citation.source_modified_at else "미상"
    )
    collected = citation.collected_at.astimezone(KST).strftime("%Y-%m-%d %H:%M KST")
    return (
        f"[{neutralize(citation.source_id)}] {title} · {link} · 버전 {version}"
        f" · 수정 {neutralize(modified)} · 수집 {neutralize(collected)}"
    )


def render(
    result: GenerationResult,
    *,
    private: bool = False,
    title_max_chars: int = 80,
    link_max_chars: int = 300,
    max_messages: int = 4,
    run_id: str = "",
    question_max_chars: int = 2000,
) -> RenderedReply:
    failure = result.summary.retrieval_failure
    retrieval_failure = RetrievalFailure(failure) if failure in set(RetrievalFailure) else None
    body = status_notice(
        result.status,
        run_id,
        body=result.answer,
        retrieval_failure=retrieval_failure,
        generation_failure=result.summary.failure,
        question_max_chars=question_max_chars,
    )
    answered = result.status is GenerationStatus.ANSWERED
    if answered and result.summary.flags.unsupported_answer:
        body = SOURCE_UNVERIFIED + "\n\n" + body
    if answered and result.summary.flags.truncated:
        body += "\n\n" + OUTPUT_TRUNCATED
    citations = result.citations if answered and not result.summary.flags.unsupported_answer else ()
    sources = _source_messages(citations, title_max_chars, link_max_chars)
    if len(sources) >= max_messages:
        raise ValueError("출처 목록이 본문 자리를 차지함")
    messages, truncated = _split_body(body, max_messages - len(sources))
    messages = list(messages)
    if sources and len(messages[-1]) + 2 + len(sources[0]) <= MESSAGE_LIMIT:
        messages[-1] += "\n\n" + sources.pop(0)
    return RenderedReply(tuple(messages + sources), private, truncated)
