"""생성 입력 렌더링과 구분자 무력화(QK-GEN-001 research R-03, spec FR-004·FR-011).

자료 블록은 QK-RET-001 Context 묶음을 순위 순서로 옮긴다.
`ContextBlock.text`(생략 표시 `(…)`)는 쓰지 않고 이 규칙으로 다시 만든다.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta, timezone

from qello_knowledge.domain.generation import GenerationSettings, PromptSpec, RenderedBlock, RenderedInput
from qello_knowledge.domain.retrieval import ContextBlock
from qello_knowledge.generation.settings import estimate_tokens

KST = timezone(timedelta(hours=9))  # 팀이 한국 시간으로 일한다(spec FR-004)
GAP_LINE = "…(중간 생략)…"
NO_TITLE = "제목 없음"
UNKNOWN_DATE = "수정 미상"
DELIMITERS = ("[자료 시작]", "[자료 끝]", "[자료]", "[질문]")
# 대괄호 쌍 안에 `S`+숫자가 있는 모든 글(줄바꿈 포함, 가장 짧게). 인식 규칙(R-04 6단계)보다 넓다(독립 검토 H1).
CITATION_LIKE = re.compile(r"\[([^\[\]]*?S\d[^\[\]]*?)\]", re.DOTALL)
# URL 후보: 공백·`<>"`·`)`·`]`·전각 괄호 전까지 가장 길게(비ASCII 포함, research R-04 4단계).
URL_CANDIDATE = re.compile(r"https?://[^\s<>\")\]）］】]+")
URL_TRAILING = ".,;:!?'"
HEADER_SEPARATOR = " | "
HEADER_SEPARATOR_SAFE = " ¦ "


def neutralize(text: str) -> tuple[str, int]:
    """구분자와 인용 꼴의 대괄호를 전각으로 바꾼다. (바꾼 글, 바꾼 개수)."""
    count = 0
    for delimiter in DELIMITERS:
        found = text.count(delimiter)
        if found:
            count += found
            text = text.replace(delimiter, "［" + delimiter[1:-1] + "］")
    text, found = CITATION_LIKE.subn(lambda m: "［" + m.group(1) + "］", text)
    return text, count + found


def neutralize_label(text: str) -> tuple[str, int]:
    """제목·위치용. 머리줄 구분 글자도 바꾼다."""
    text, count = neutralize(text)
    found = text.count(HEADER_SEPARATOR)
    return text.replace(HEADER_SEPARATOR, HEADER_SEPARATOR_SAFE), count + found


def extract_urls(text: str) -> frozenset[str]:
    return frozenset(m.group(0).rstrip(URL_TRAILING) for m in URL_CANDIDATE.finditer(text))


def raw_title(block: ContextBlock) -> str:
    """묶음 첫 청크의 제목 경로 → 청크 위치 경로 → `제목 없음`(spec FR-004)."""
    first = block.chunks[0]
    if first.heading_path:
        return " > ".join(first.heading_path)
    path = first.locator.get("path")
    if isinstance(path, str) and path:
        return path
    return NO_TITLE


def modified_label(value: datetime | None) -> str:
    if value is None:
        return UNKNOWN_DATE
    aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return aware.astimezone(KST).date().isoformat()


def render_block(block: ContextBlock, rule: str, settings: GenerationSettings) -> tuple[RenderedBlock, int]:
    """묶음 하나를 렌더링한다. (렌더링한 묶음, 무력화한 개수)."""
    title_raw = raw_title(block)
    title, count = neutralize_label(title_raw)
    label = modified_label(block.source_modified_at)
    if rule == "render-v1":
        dated = label if label == UNKNOWN_DATE else f"수정 {label}"
        lines = [f"[{block.source_id}] {title} | {dated}"]
    elif rule == "render-base":
        lines = [f"[{block.source_id}] 제목: {title}"]
    else:
        raise ValueError("알 수 없는 렌더링 규칙")
    previous = None
    for chunk in block.chunks:
        if rule == "render-v1" and previous is not None:
            if chunk.ordinal != previous.ordinal + 1:
                lines.append(GAP_LINE)
            if chunk.heading_path != previous.heading_path:
                section, found = neutralize_label(" > ".join(chunk.heading_path) or NO_TITLE)
                count += found
                lines.append(f"(절: {section})")
        body, found = neutralize(chunk.body)
        count += found
        lines.append(body)
        previous = chunk
    text = "\n".join(lines)
    excerpt = "\n".join(c.body for c in block.chunks)
    rendered = RenderedBlock(
        source_id=block.source_id,
        block=block,
        raw_title=title_raw,
        title=title,
        modified_label=label,
        text=text,
        excerpt_urls=extract_urls(excerpt),
        estimated_tokens=estimate_tokens(text, settings),
    )
    return rendered, count


def fill_template(template: str, context: str, question: str) -> str:
    """`{context}`·`{question}`을 한 번씩만 채운다. 자료 안의 같은 글자는 다시 채우지 않는다."""
    before, rest = template.split("{context}", 1)
    middle, after = rest.split("{question}", 1)
    return before + context + middle + question + after


def assemble(
    question: str,
    blocks: Sequence[RenderedBlock],
    prompt: PromptSpec,
    settings: GenerationSettings,
    *,
    dropped=(),
    neutralized: int = 0,
) -> RenderedInput:
    """렌더링한 묶음과 (무력화한) 질문으로 생성 입력을 만든다. 렌더러는 템플릿 밖에서 글을 붙이지 않는다."""
    context = "\n\n".join(b.text for b in blocks)
    user = fill_template(prompt.user_template, context, question)
    return RenderedInput(
        system=prompt.system,
        user=user,
        blocks=tuple(blocks),
        dropped=tuple(dropped),
        neutralized=neutralized,
        estimated_input_tokens=estimate_tokens(prompt.system, settings) + estimate_tokens(user, settings),
    )


def render(
    question: str, blocks: Sequence[ContextBlock], prompt: PromptSpec, settings: GenerationSettings
) -> RenderedInput:
    """순수 렌더링(contracts/generation.md 1절). 전송 직전 검사는 하지 않는다."""
    safe_question, count = neutralize(question)
    rendered = []
    for block in blocks:
        item, found = render_block(block, prompt.render_rule, settings)
        rendered.append(item)
        count += found
    return assemble(safe_question, rendered, prompt, settings, neutralized=count)
