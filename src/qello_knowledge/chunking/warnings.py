"""청크 경계·버전에 영향을 주지 않는 구조 관찰(research R-11)."""

import re

from qello_knowledge.chunking.blocks import ParsedDocument
from qello_knowledge.domain.chunking import StructureWarning, StructureWarningKind

_CONTAINER = re.compile(r"^[ \t]*(?:>[ \t]?|(?:[-+*]|\d{1,9}[.)])[ \t]+)")


def _cell_count(line: str, depth: int) -> int:
    for _ in range(depth):
        stripped, count = _CONTAINER.subn("", line, count=1)
        if not count:
            break
        line = stripped
    line = line.strip()
    # An even number of preceding backslashes leaves a pipe unescaped.
    cells, start, backslashes = [], 0, 0
    for i, char in enumerate(line):
        if char == "|" and backslashes % 2 == 0:
            cells.append(line[start:i])
            start = i + 1
        backslashes = backslashes + 1 if char == "\\" else 0
    cells.append(line[start:])
    if line.startswith("|"):
        cells.pop(0)
    if len(cells) > 1 and line.endswith("|") and not cells[-1]:
        cells.pop()
    return len(cells)


def structure_warnings(parsed: ParsedDocument, lines: list[str]) -> tuple[StructureWarning, ...]:
    warnings = [
        StructureWarning(StructureWarningKind.UNCLOSED_FENCE, f.start + 1)
        for f in parsed.fences
        if f.content_newlines != f.end - f.start - 2
    ]
    for table in parsed.tables:
        count = _cell_count(lines[table.start], table.container_depth)
        for n in range(table.start + 1, table.end):
            if _cell_count(lines[n], table.container_depth) != count:
                warnings.append(StructureWarning(StructureWarningKind.TABLE_CELL_MISMATCH, n + 1))
    return tuple(sorted(warnings, key=lambda w: (w.line, w.kind)))
