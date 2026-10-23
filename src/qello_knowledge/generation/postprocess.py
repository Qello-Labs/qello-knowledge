"""모델 출력 후처리(QK-GEN-001 research R-04, spec FR-009·FR-013~016).

순서: (1) 추론 블록 → (2) 코드 가림(10단계까지 유지) → (3) 출처 목록 줄 → (4) URL → (5) 문장 나누기 → (6) 인용 →
(7) 빈 결과 → (8) 확인 불가 판정 → (9) 세기 → (10) 코드 되돌림 → (11) 출처 ID. 모든 단계는 결정적이다.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from qello_knowledge.domain.generation import CANNOT_CONFIRM, CHECK_ORIGIN, CannotConfirmReason, RenderedInput
from qello_knowledge.generation.render import URL_CANDIDATE, URL_TRAILING

CANNOT_CORE = CANNOT_CONFIRM.rstrip(".")
ORIGIN_CORE = CHECK_ORIGIN.rstrip(".")

THINK_BLOCK = re.compile(r"<think>(.*?)</think>", re.DOTALL)
CODE_FENCE = re.compile(r"```.*?(?:```|\Z)", re.DOTALL)  # 닫히지 않은 펜스는 끝까지 코드다
CODE_SPAN = re.compile(r"`[^`\n]+`")
PLACEHOLDER = re.compile(r"\x00C(\d+)\x00")
SOURCE_HEAD = re.compile(r"^[ \t]*(출처|참고|Sources?|References)[ \t]*[:：]")
LIST_LINE = re.compile(r"^[ \t]*([-*]|\d+\.)[ \t]")
# URL 뒤에 붙어도 되는 조사(research R-04 4단계). 한글 1~2자 전부가 아니라 정해진 조사만 받는다(독립 검토 L4).
PARTICLE = re.compile(r"에서|에게|으로|부터|까지|에|은|는|을|를|이|가|의|로|와|과|도|만")
# 인식하는 인용: `[S1]`, `[ S1 ]`, `[S1, S2]`, `[S1，S2]`, `[S1 S2]`. 대괄호 안 공백은 줄바꿈을 받지 않는다(R-04 6단계).
RECOGNIZED = re.compile(r"\[[ \t]*S[1-9]\d*(?:(?:[ \t]*[,，][ \t]*|[ \t]+)S[1-9]\d*)*[ \t]*\]")
ID_IN_GROUP = re.compile(r"S([1-9]\d*)")
BRACKET = re.compile(r"\[([^\[\]\n]*)\]")
UNRECOGNIZED_INNER = re.compile(r"[ \t,，;；/\-~–S\d및]*S\d[ \t,，;；/\-~–S\d및]*")
UNRECOGNIZED_OTHER = re.compile(r"\[s\d+\]|\(S\d+\)|【S\d+】")
QUOTES = "\"'“”‘’「」"
SENTENCE_END = ".?!"
WORD = re.compile(r"\w")
# 문장부호 뒤가 공백·줄 끝일 때만 앞 공백을 지운다. `.env`처럼 점으로 시작하는 이름은 건드리지 않는다(재검토 N1).
SPACE_BEFORE_MARK = re.compile(r"[ \t]+(?=[.,?!](?:\s|$))")


@dataclass(frozen=True)
class Postprocessed:
    answer: str
    citation_ids: tuple[str, ...]
    cannot_confirm_reason: CannotConfirmReason | None
    empty: bool
    removed_citations: int = 0
    unrecognized_citations: int = 0
    uncited_sentences: int = 0
    fact_sentences: int = 0  # 사실 문장 수. 문장마다 인용 비율 = (사실 - 인용 없음) ÷ 사실(SC-008)
    removed_urls: int = 0
    removed_source_lines: int = 0
    unsupported_answer: bool = False
    thinking_detected: bool = False

    def __repr__(self) -> str:  # 답변 본문을 숨긴다(spec FR-012)
        return (
            f"Postprocessed(citations={self.citation_ids!r}, reason={self.cannot_confirm_reason!r}, empty={self.empty})"
        )


def _code_ranges(text: str) -> list[tuple[int, int]]:
    ranges = [m.span() for m in CODE_FENCE.finditer(text)]
    ranges += [m.span() for m in CODE_SPAN.finditer(text) if not _inside(m.start(), ranges)]
    return ranges


def _inside(position: int, ranges: list[tuple[int, int]]) -> bool:
    return any(start <= position < end for start, end in ranges)


def _positions(text: str, needle: str) -> list[int]:
    found, start = [], 0
    while (index := text.find(needle, start)) != -1:
        found.append(index)
        start = index + 1
    return found


def _strip_thinking(text: str) -> tuple[str, bool]:
    """추론 블록을 지운다. 코드 표기 안의 `<think>`·`</think>`는 추론 표시로 보지 않는다(독립 검토 M2)."""
    detected = False
    while True:
        ranges = _code_ranges(text)
        block = next((m for m in THINK_BLOCK.finditer(text) if not _inside(m.start(), ranges)), None)
        if block is None:
            break
        detected = detected or bool(block.group(1).strip())
        text = text[: block.start()] + text[block.end() :]
    ranges = _code_ranges(text)
    closes = [i for i in _positions(text, "</think>") if not _inside(i, ranges)]
    if closes:  # 짝 없는 닫는 표시: 그 앞까지를 추론으로 본다
        before, text = text[: closes[-1]], text[closes[-1] + len("</think>") :]
        detected = detected or bool(before.replace("<think>", "").strip())
    ranges = _code_ranges(text)
    opens = [i for i in _positions(text, "<think>") if not _inside(i, ranges)]
    if opens:  # 닫히지 않은 추론: 끝까지 지운다
        text, after = text[: opens[0]], text[opens[0] + len("<think>") :]
        detected = detected or bool(after.strip())
    return text, detected


def _mask_code(text: str) -> tuple[str, list[str]]:
    codes: list[str] = []

    def keep(match: re.Match[str]) -> str:
        codes.append(match.group(0))
        return f"\x00C{len(codes) - 1}\x00"

    text = CODE_FENCE.sub(keep, text)
    return CODE_SPAN.sub(keep, text), codes


def _unmask(text: str, codes: list[str]) -> str:
    def restore(match: re.Match[str]) -> str:
        index = int(match.group(1))
        return codes[index] if index < len(codes) else ""

    return PLACEHOLDER.sub(restore, text)


def _drop_source_lines(text: str) -> tuple[str, int]:
    kept: list[str] = []
    removed = 0
    in_list = False
    for line in text.split("\n"):
        if SOURCE_HEAD.match(line):
            removed += 1
            in_list = True
            continue
        if in_list and LIST_LINE.match(line):
            removed += 1
            continue
        in_list = False
        kept.append(line)
    return "\n".join(kept), removed


def _clean_urls(text: str, allowed: frozenset[str]) -> tuple[str, int]:
    removed = 0

    def judge(match: re.Match[str]) -> str:
        nonlocal removed
        candidate = match.group(0)
        core = candidate.rstrip(URL_TRAILING)
        tail = candidate[len(core) :]
        if core in allowed:
            return candidate
        for url in allowed:
            if core.startswith(url) and PARTICLE.fullmatch(core[len(url) :]):
                return candidate
        removed += 1
        return tail

    return URL_CANDIDATE.sub(judge, text), removed


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    """문장 경계: 문장부호 뒤(붙은 인용 꼴까지) 공백·줄 끝, 그리고 줄바꿈(spec FR-014)."""
    spans: list[tuple[int, int]] = []
    start = 0
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "\n":
            spans.append((start, i))
            start = i + 1
        elif ch in SENTENCE_END:
            j = i + 1
            while j < n and text[j] == "[":
                close = text.find("]", j)
                if close == -1 or "\n" in text[j:close]:
                    break
                j = close + 1
            if j >= n or text[j] in " \t\n":
                spans.append((start, j))
                start = j
                i = j
                continue
        i += 1
    spans.append((start, n))
    return [(a, b) for a, b in spans if text[a:b].strip()]


def _normalize_citations(sentence: str, allowed: set[str]) -> tuple[str, int, int]:
    """인식한 인용을 `[S1][S2]`로 맞추고 없는 ID·같은 문장 안 중복을 지운다. (글, 지운 ID 수, 인식 못 한 꼴 수)."""
    seen: set[str] = set()
    removed = 0

    def group(match: re.Match[str]) -> str:
        nonlocal removed
        out = []
        for number in ID_IN_GROUP.findall(match.group(0)):
            sid = f"S{number}"
            if sid not in allowed:
                removed += 1
                continue
            if sid in seen:
                continue
            seen.add(sid)
            out.append(f"[{sid}]")
        return "".join(out)

    normalized = RECOGNIZED.sub(group, sentence)
    unrecognized = sum(1 for m in BRACKET.finditer(normalized) if _is_unrecognized(m.group(1)))
    unrecognized += len(UNRECOGNIZED_OTHER.findall(normalized))
    return normalized, removed, unrecognized


def _is_unrecognized(inner: str) -> bool:
    return bool(UNRECOGNIZED_INNER.fullmatch(inner)) and not RECOGNIZED.fullmatch(f"[{inner}]")


def _strip_citation_marks(sentence: str) -> str:
    sentence = RECOGNIZED.sub("", sentence)
    sentence = BRACKET.sub(lambda m: "" if _is_unrecognized(m.group(1)) else m.group(0), sentence)
    return UNRECOGNIZED_OTHER.sub("", sentence)


def _core(sentence: str) -> str:
    text = _strip_citation_marks(sentence)
    text = "".join(ch for ch in text if ch not in QUOTES).strip()
    return text.rstrip(".").strip()


def _leading_citations(sentence: str) -> tuple[str, str]:
    """문장 머리의 인용 꼴(공백 포함)과 나머지."""
    rest = sentence.lstrip()
    head = ""
    while True:
        match = RECOGNIZED.match(rest) or UNRECOGNIZED_OTHER.match(rest)
        if match is None:
            bracket = BRACKET.match(rest)
            match = bracket if bracket and _is_unrecognized(bracket.group(1)) else None
        if match is None:
            return head, rest
        head += match.group(0)
        rest = rest[match.end() :].lstrip()


def _attribute(sentences: list[str]) -> list[str]:
    """머리에 붙은 인용을 문장부호로 끝난 앞 문장으로 옮긴다. 인용만 남은 조각은 앞에 붙인다(R-04 5단계)."""
    out: list[str] = []
    for sentence in sentences:
        head, rest = _leading_citations(sentence)
        # 앞 조각이 (붙은 인용을 뗀 뒤) 문장부호로 끝날 때만 옮긴다(R-04 5단계, 독립 검토 L3)
        previous_end = _strip_citation_marks(out[-1]).rstrip()[-1:] if out else ""
        if out and head and (not rest or previous_end in SENTENCE_END):
            out[-1] = out[-1] + head
            sentence = rest
        if not WORD.search(_strip_citation_marks(sentence)):
            continue
        out.append(sentence)
    return out


def _tidy(text: str) -> str:
    """지운 자리의 겹친 공백과 문장부호 앞 공백을 정리한다(독립 검토 L2). 코드는 가려진 상태에서 부른다."""
    lines = [SPACE_BEFORE_MARK.sub("", re.sub(r"[ \t]{2,}", " ", line)).rstrip() for line in text.split("\n")]
    return "\n".join(lines).strip()


def postprocess(reply_text: str, rendered: RenderedInput) -> Postprocessed:
    allowed = {b.source_id for b in rendered.blocks}
    excerpt_urls = frozenset().union(*(b.excerpt_urls for b in rendered.blocks)) if rendered.blocks else frozenset()

    # 응답 안의 NUL은 코드 자리 표시와 겹칠 수 있어 먼저 지운다(독립 검토 L1)
    text, thinking = _strip_thinking(reply_text.replace("\x00", ""))  # 1
    text, codes = _mask_code(text)  # 2
    text, source_lines = _drop_source_lines(text)  # 3
    text, removed_urls = _clean_urls(text, excerpt_urls)  # 4

    pieces: list[str] = []  # 5·6: 문장 단위로 인용을 정리하고 원래 구분자를 지킨다
    removed_ids = 0
    unrecognized = 0
    cursor = 0
    sentences: list[str] = []
    for start, end in _sentence_spans(text):
        pieces.append(text[cursor:start])
        normalized, removed, unknown = _normalize_citations(text[start:end], allowed)
        removed_ids += removed
        unrecognized += unknown
        pieces.append(normalized)
        sentences.append(normalized)
        cursor = end
    pieces.append(text[cursor:])
    body = _tidy("".join(pieces))

    sentences = _attribute(sentences)
    common = {
        "removed_citations": removed_ids,
        "unrecognized_citations": unrecognized,
        "removed_urls": removed_urls,
        "removed_source_lines": source_lines,
        "thinking_detected": thinking,
    }
    if not sentences:  # 7
        return Postprocessed("", (), None, True, **common)

    cores = [_core(s) for s in sentences]  # 8
    if all(core == CANNOT_CORE for core in cores):
        return Postprocessed(CANNOT_CONFIRM, (), CannotConfirmReason.MODEL_CANNOT_CONFIRM, False, **common)
    if all(core.endswith(CANNOT_CORE) or core == ORIGIN_CORE for core in cores):
        stripped = _unmask(_tidy(_strip_citation_marks(body)), codes)
        return Postprocessed(stripped, (), CannotConfirmReason.MODEL_UNCONFIRMABLE_PARTS, False, **common)

    uncited = 0  # 9
    facts = 0
    for sentence, core in zip(sentences, cores, strict=True):
        if core.endswith(CANNOT_CORE) or core == ORIGIN_CORE or PLACEHOLDER.fullmatch(core):
            continue
        facts += 1
        if not RECOGNIZED.search(sentence):
            uncited += 1
    ids = sorted({f"S{n}" for g in RECOGNIZED.findall(body) for n in ID_IN_GROUP.findall(g)}, key=lambda s: int(s[1:]))
    answer = _unmask(body, codes)  # 10
    return Postprocessed(  # 11
        answer,
        tuple(ids),
        None,
        False,
        uncited_sentences=uncited,
        fact_sentences=facts,
        unsupported_answer=not ids,
        **common,
    )
