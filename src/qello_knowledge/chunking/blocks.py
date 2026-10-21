"""단일 Markdown 해석기 경계. 토큰의 원문 줄 범위만 이용한다."""

from dataclasses import dataclass

import markdown_it
from markdown_it import MarkdownIt

PARSER_VERSION = markdown_it.__version__


@dataclass(frozen=True)
class Block:
    start: int
    end: int
    kind: str
    level: int = 0
    text: str = ""
    prefix: str = ""
    children: tuple["Block", ...] = ()


@dataclass(frozen=True)
class FenceInfo:
    start: int
    end: int
    content_newlines: int


@dataclass(frozen=True)
class TableInfo:
    start: int
    end: int
    container_depth: int


@dataclass(frozen=True)
class ParsedDocument:
    blocks: tuple[Block, ...]
    front_matter_title: str | None
    fences: tuple[FenceInfo, ...]
    tables: tuple[TableInfo, ...]


def _inline_text(tokens) -> str:
    parts = []
    for token in tokens or ():
        if token.type in ("text", "code_inline"):
            parts.append(token.content)
        elif token.type == "image":
            parts.append(_inline_text(token.children) if token.children else token.content)
        elif token.type in ("softbreak", "hardbreak"):
            parts.append(" ")
    return "".join(parts)


def parse_document(lines: list[str]) -> ParsedDocument:
    copy = list(lines)
    blocks = []
    title = None
    if lines and lines[0] == "---":
        end = next((i + 1 for i in range(1, len(lines)) if lines[i] in ("---", "...")), None)
        if end is not None:
            blocks.append(Block(0, end, "front_matter"))
            for line in lines[1 : end - 1]:
                if line.startswith("title:"):
                    title = line[6:].strip().strip("'\"")
            copy[:end] = [""] * end
    text = "\n".join(copy)
    tokens = MarkdownIt("commonmark").enable("table").parse(text if text.endswith("\n") else text + "\n")
    pairs, stack = {}, []
    fences, tables = [], []
    for i, token in enumerate(tokens):
        if token.type == "fence":
            fences.append(FenceInfo(*token.map, token.content.count("\n")))
        if token.type == "table_open":
            depth = sum(tokens[j].type in ("list_item_open", "blockquote_open") for j in stack)
            tables.append(TableInfo(*token.map, depth))
        if token.nesting == 1:
            stack.append(i)
        elif token.nesting == -1:
            pairs[stack.pop()] = i

    def build(i):
        token = tokens[i]
        end_i = pairs.get(i, i)
        start, end = token.map
        kind = token.type.removesuffix("_open")
        kind = {"bullet_list": "list", "ordered_list": "list", "code_block": "code", "html_block": "html"}.get(
            kind, kind
        )
        children = []
        if kind in ("list", "list_item", "blockquote"):
            j = i + 1
            while j < end_i:
                child = tokens[j]
                if child.map and child.type != "inline" and child.nesting >= 0:
                    children.append(build(j))
                j = pairs.get(j, j) + 1
        heading = " ".join(_inline_text(tokens[i + 1].children).split()) if kind == "heading" else ""
        prefix = "\n".join(lines[start : start + 2]) if kind == "table" else lines[start] if kind == "fence" else ""
        return Block(start, end, kind, int(token.tag[1:]) if kind == "heading" else 0, heading, prefix, tuple(children))

    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.level == 0 and token.map and token.type != "inline" and token.nesting >= 0:
            blocks.append(build(i))
        i = pairs.get(i, i) + 1
    blocks.sort(key=lambda b: b.start)
    covered = {n for b in blocks for n in range(b.start, b.end)}
    i = 0
    while i < len(lines):
        if i not in covered and lines[i].strip():
            start = i
            while i < len(lines) and i not in covered and lines[i].strip():
                i += 1
            blocks.append(Block(start, i, "raw"))
        else:
            i += 1
    return ParsedDocument(tuple(sorted(blocks, key=lambda b: b.start)), title, tuple(fences), tuple(tables))
