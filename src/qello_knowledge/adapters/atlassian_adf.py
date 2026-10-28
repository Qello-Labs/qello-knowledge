"""Atlassian 문서 형식(ADF) → Markdown(QK-ING-003 contracts/adf-markdown.md).

표준 라이브러리만 쓰고, 같은 입력이면 바이트 단위로 같은 출력을 만든다.
Jira 설명·댓글도 ADF라 QK-ING-004가 다시 쓸 수 있다.
계정 ID·메일 주소·매크로 설정값은 결과에 넣지 않는다. 경고에는 원문 없이 종류와 최상위 블록 순번만 담는다.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from urllib.parse import unquote, urlsplit

from qello_knowledge.domain.source import ConversionWarning, ConversionWarningKind

RULES_VERSION = "adf-md-v1"
GLOSSARY_HEADER = ("용어", "정의", "동의어·약어·영문", "코드 식별자·API 경로", "관련 문서")
PANEL_NAMES = {"info": "정보", "note": "참고", "warning": "경고", "error": "오류", "success": "성공", "tip": "팁"}
LIST_TYPES = frozenset({"bulletList", "orderedList", "taskList"})
_PLACEHOLDER = re.compile(r"\[(?:이미지|첨부(?:: [^\]]*)?|매크로: [^\]]*|링크|메일 주소)\]")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_WORD = re.compile(r"\w")
_LINE_START = re.compile(r"^(\s*)([#>|+*-]|[0-9]+[.)])")  # 줄 머리에서 Markdown 구문이 되는 문자(구현 검토 C7)


@dataclass(frozen=True)
class Meeting:
    date: str
    kind: str | None
    spec_ids: tuple[str, ...]


@dataclass(frozen=True)
class ConvertResult:
    markdown: str
    rules_version: str
    warnings: tuple[ConversionWarning, ...]
    meeting: Meeting | None


def _attrs(node) -> dict:
    attrs = node.get("attrs") if isinstance(node, dict) else None
    return attrs if isinstance(attrs, dict) else {}


def _children(node) -> list:
    content = node.get("content") if isinstance(node, dict) else None
    return [child for child in content if isinstance(child, dict)] if isinstance(content, list) else []


def _span(value) -> int:
    """셀 병합 값. 정수가 아니면 병합 없음으로 본다(형식이 어긋난 응답에서 멈추지 않게, 구현 검토 C6)."""
    return value if type(value) is int else 1


def _escape(text: str, at_line_start: bool) -> str:
    """원문 글자가 Markdown 구문으로 읽히지 않게 한다. 코드 울타리와 줄 머리 기호만 막는다(구현 검토 C7)."""
    text = text.replace("```", "\\`\\`\\`")
    if at_line_start:

        def escaped(match):
            mark = match.group(2)
            # 번호 목록은 점·괄호 앞에, 나머지 기호는 기호 앞에 백슬래시를 둔다(CommonMark).
            return match.group(1) + (mark[:-1] + "\\" + mark[-1] if mark[0].isdigit() else "\\" + mark)

        text = _LINE_START.sub(escaped, text, count=1)
    return text


class _Converter:
    def __init__(self, site_host: str | None, public_link_hosts: Sequence[str]) -> None:
        self.site_host = (site_host or "").lower()
        self.public_link_hosts = frozenset(host.lower() for host in public_link_hosts)
        self.warnings: list[ConversionWarning] = []
        self.block = 0

    def warn(self, kind: ConversionWarningKind) -> None:
        self.warnings.append(ConversionWarning(kind, self.block))

    def placeholder(self, node) -> str:
        self.warn(ConversionWarningKind.UNSUPPORTED_BLOCK)
        return f"[매크로: {_attrs(node).get('extensionKey') or node.get('type') or '?'}]"

    # ---- 링크 ----------------------------------------------------------------------------------

    def keep(self, href) -> str | None:
        """남길 수 있는 주소면 쿼리·조각을 뺀 주소를, 아니면 `None`을 돌려준다(링크 규칙)."""
        if not isinstance(href, str):
            return None
        try:
            parts = urlsplit(href)
            port = parts.port
        except ValueError:
            return None
        host = (parts.hostname or "").lower()
        if parts.scheme != "https" or not host or port not in {None, 443}:
            return None
        path = parts.path or ""
        if host == self.site_host:
            # 사람 프로필과 개인 스페이스 경로는 계정 ID를 담는다. 인코딩을 풀고 본다(구현 검토 C3).
            segments = unquote(path).split("/")
            if any(segment == "people" or segment.startswith("~") for segment in segments):
                return None
        elif host not in self.public_link_hosts:
            return None
        return f"https://{host}{path}"

    def link(self, text: str, href) -> str:
        if isinstance(href, str) and href.lower().startswith("mailto:"):
            return "[메일 주소]"
        kept = self.keep(href)
        if kept is not None:
            return f"[{text}]({kept})"
        host = ""
        if isinstance(href, str):
            try:
                host = (urlsplit(href).hostname or "").lower()
            except ValueError:
                host = ""
        if isinstance(href, str) and href and (href in text or (host and host in text.lower())):
            return "[링크]"  # 자동 링크는 텍스트가 곧 버린 주소다(스킴 없는 표기 포함)
        return text

    def card(self, url) -> str:
        kept = self.keep(url)
        return f"[{kept}]({kept})" if kept is not None else "[링크]"

    # ---- 인라인 --------------------------------------------------------------------------------

    def inline(self, nodes) -> str:
        out = []
        at_line_start = True
        for node in nodes:
            kind = node.get("type")
            attrs = _attrs(node)
            if kind == "text":
                out.append(self.text(node, at_line_start))
            elif kind == "hardBreak":
                out.append("\n")
                at_line_start = True
                continue
            elif kind == "mention":
                out.append(str(attrs.get("text") or "").lstrip("@"))
            elif kind == "emoji":
                out.append(str(attrs.get("text") or attrs.get("shortName") or ""))
            elif kind == "status":
                out.append(str(attrs.get("text") or ""))
            elif kind == "date":
                out.append(_date(attrs.get("timestamp")))
            elif kind == "inlineCard":
                out.append(self.card(attrs.get("url")))
            elif kind == "mediaInline":
                out.append("[첨부]")
            else:
                out.append(self.placeholder(node))
            at_line_start = at_line_start and not out[-1]
        return "".join(out)

    def text(self, node, at_line_start: bool = False) -> str:
        value = str(node.get("text") or "")
        marks = node.get("marks") if isinstance(node.get("marks"), list) else []
        marks = [m for m in marks if isinstance(m, dict)]
        types = {m.get("type") for m in marks}
        if "code" in types:
            value = f"`{value}`"
        else:
            value = _escape(value, at_line_start)
        if "strike" in types:
            value = f"~~{value}~~"
        if "em" in types:
            value = f"*{value}*"
        if "strong" in types:
            value = f"**{value}**"
        link = next((m for m in marks if m.get("type") == "link"), None)
        return self.link(value, _attrs(link).get("href")) if link is not None else value

    # ---- 블록 ----------------------------------------------------------------------------------

    def blocks(self, nodes) -> list[str]:
        out: list[str] = []
        for node in nodes:
            lines = self.block_lines(node)
            if lines:
                if out:
                    out.append("")
                out.extend(lines)
        return out

    def block_lines(self, node) -> list[str]:
        kind = node.get("type")
        attrs = _attrs(node)
        if kind == "paragraph":
            text = self.inline(_children(node))
            return text.split("\n") if text.strip() else []
        if kind == "heading":
            level = attrs.get("level") if isinstance(attrs.get("level"), int) else 1
            return ["#" * min(max(level, 1) + 1, 6) + " " + self.inline(_children(node)).replace("\n", " ")]
        if kind in LIST_TYPES:
            return self.list_lines(node, "")
        if kind == "codeBlock":
            text = "".join(str(c.get("text") or "") for c in _children(node)).rstrip("\n")
            run = max((len(m) for m in re.findall(r"`+", text)), default=0)
            fence = "`" * max(3, run + 1)
            return [fence + str(attrs.get("language") or ""), *text.split("\n"), fence]
        if kind == "blockquote":
            return [("> " + line) if line else ">" for line in self.blocks(_children(node))]
        if kind == "rule":
            return ["---"]
        if kind in {"layoutSection", "layoutColumn"}:
            return self.blocks(_children(node))  # 열 레이아웃은 내용만 차례로 펼친다(구현 검토 C2)
        if kind == "decisionList":
            items = [self.inline(_children(item)).replace("\n", " ") for item in _children(node)]
            return [f"- {item}" for item in items if item.strip()]
        if kind == "table":
            return self.table_lines(node)
        if kind == "panel":
            name = PANEL_NAMES.get(str(attrs.get("panelType")), "패널")
            return [f"**{name}**", "", *self.blocks(_children(node))]
        if kind in {"expand", "nestedExpand"}:
            return [f"**{attrs.get('title') or '펼치기'}**", "", *self.blocks(_children(node))]
        if kind == "mediaSingle":
            return ["[이미지]"]
        if kind == "mediaGroup":
            names = [_attrs(m).get("alt") for m in _children(node)]
            return [" ".join(f"[첨부: {name}]" if name else "[첨부]" for name in names)] if names else []
        if kind in {"blockCard", "embedCard"}:
            return [self.card(attrs.get("url"))]
        return [self.placeholder(node)]

    def list_lines(self, node, indent: str) -> list[str]:
        lines: list[str] = []
        ordered = node.get("type") == "orderedList"
        start = _attrs(node).get("order") if isinstance(_attrs(node).get("order"), int) else 1
        for index, item in enumerate(_children(node)):
            if item.get("type") in LIST_TYPES:
                lines.extend(self.list_lines(item, indent + "  "))
                continue
            if item.get("type") == "taskItem":
                marker = "- [x] " if _attrs(item).get("state") == "DONE" else "- [ ] "
                lines.append(indent + marker + self.inline(_children(item)).replace("\n", " "))
                continue
            marker = f"{start + index}. " if ordered else "- "
            first = True
            for child in _children(item):
                if child.get("type") in LIST_TYPES:
                    if first:
                        lines.append(indent + marker.rstrip())  # 하위 목록으로 시작하는 항목(구현 검토 C8)
                        first = False
                    lines.extend(self.list_lines(child, indent + "  "))
                    continue
                for line in self.block_lines(child):
                    lines.append(indent + (marker if first else "  ") + line)
                    first = False
            if first:
                lines.append(indent + marker.rstrip())
        return lines

    def cell_text(self, nodes) -> str:
        parts = []
        for node in nodes:
            if node.get("type") == "table":
                parts.extend(self.cell_text(_children(cell)) for row in _children(node) for cell in _children(row))
            elif node.get("type") in {"paragraph", "heading"}:
                parts.append(self.inline(_children(node)))
            elif node.get("type") in LIST_TYPES or node.get("type") == "listItem":
                parts.append(self.cell_text(_children(node)))
            else:
                parts.append(" ".join(self.block_lines(node)))
        return " ".join(p.replace("\n", " ").strip() for p in parts if p.strip())

    def table_lines(self, node) -> list[str]:
        rows = [_children(row) for row in _children(node) if row.get("type") == "tableRow"]
        if not rows:
            return []
        merged = any(
            _span(_attrs(cell).get("colspan")) > 1 or _span(_attrs(cell).get("rowspan")) > 1
            for row in rows
            for cell in row
        )
        nested = any(child.get("type") == "table" for row in rows for cell in row for child in _children(cell))
        if merged or nested:
            self.warn(ConversionWarningKind.TABLE_FLATTENED)
            return ["- " + " / ".join(self.cell_text(_children(cell)) for cell in row) for row in rows]
        width = max(len(row) for row in rows)

        def line(row):
            cells = [self.cell_text(_children(cell)).replace("|", "\\|") for cell in row]
            return "| " + " | ".join(cells + [""] * (width - len(cells))) + " |"

        return [line(rows[0]), "| " + " | ".join(["---"] * width) + " |", *(line(row) for row in rows[1:])]

    def table_texts(self, node) -> list[list[str]]:
        return [
            [self.cell_text(_children(cell)) for cell in _children(row)]
            for row in _children(node)
            if row.get("type") == "tableRow"
        ]


def _date(timestamp) -> str:
    try:
        return datetime.fromtimestamp(int(str(timestamp)) / 1000, UTC).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OverflowError, OSError):
        return ""


def _meeting(converter: _Converter, blocks: list) -> tuple[Meeting | None, int]:
    """본문 첫 표의 `일시`·`회의 종류`·`관련 명세 ID`(FR-022). 날짜가 없거나 형식이 틀리면 `None`."""
    index = next((i for i, node in enumerate(blocks) if node.get("type") == "table"), None)
    if index is None:
        return None, 0
    seen = len(converter.warnings)
    fields = {row[0]: row[1] for row in converter.table_texts(blocks[index]) if len(row) >= 2}
    del converter.warnings[seen:]  # 미리 읽기의 경고는 본문 변환에서 다시 생긴다(구현 검토 C8)
    day = fields.get("일시", "").strip()
    try:
        valid = bool(_DATE.fullmatch(day)) and date.fromisoformat(day) is not None
    except ValueError:
        valid = False
    if not valid:
        return None, index
    ids = tuple(p.strip() for p in fields.get("관련 명세 ID", "").split(",") if p.strip() and p.strip() != "없음")
    kind = _PLACEHOLDER.sub("", fields.get("회의 종류", "")).strip() or None
    return Meeting(day, kind, ids), index


def _glossary_lines(converter: _Converter, node) -> list[str] | None:
    seen = len(converter.warnings)
    rows = converter.table_texts(node)
    if not rows or tuple(rows[0]) != GLOSSARY_HEADER:
        del converter.warnings[seen:]  # 용어집이 아니면 표를 다시 변환하며 경고가 생긴다(구현 검토 C8)
        return None
    lines: list[str] = []
    for row in rows[1:]:
        cells = (row + [""] * len(GLOSSARY_HEADER))[: len(GLOSSARY_HEADER)]
        if not cells[0]:
            continue
        if lines:
            lines.append("")
        lines += [f"## {cells[0]}", ""]
        lines += [f"- {header}: {value}" for header, value in zip(GLOSSARY_HEADER[1:], cells[1:], strict=True) if value]
    return lines


def convert_adf(doc, *, title: str, site_host: str | None, public_link_hosts: Sequence[str], doc_type) -> ConvertResult:
    if not isinstance(doc, dict) or doc.get("type") != "doc" or not isinstance(doc.get("content", []), list):
        raise ValueError("ADF 최상위는 doc이어야 한다")
    converter = _Converter(site_host, public_link_hosts)
    blocks = _children(doc)
    meeting = None
    if doc_type == "회의록":
        meeting, block = _meeting(converter, blocks)
        if meeting is None:
            converter.block = block
            converter.warn(ConversionWarningKind.MEETING_METADATA_MISSING)
    parts: list[str] = []
    glossary = False
    for index, node in enumerate(blocks):
        converter.block = index
        lines = _glossary_lines(converter, node) if doc_type == "용어집" and node.get("type") == "table" else None
        glossary = glossary or lines is not None
        lines = lines if lines is not None else converter.block_lines(node)
        if lines:
            parts.append("\n".join(lines))
    if doc_type == "용어집" and not glossary:
        converter.block = 0
        converter.warn(ConversionWarningKind.NOT_GLOSSARY)
    body = "\n\n".join(parts)
    # 제목 줄과 자리 표시 말고 텍스트가 없으면 본문 없음이다(FR-032).
    markdown = f"# {title}\n\n{body}\n" if _WORD.search(_PLACEHOLDER.sub("", body)) else ""
    warnings = tuple(sorted(converter.warnings, key=lambda w: w.block))
    return ConvertResult(markdown, RULES_VERSION, warnings, meeting)
