#!/usr/bin/env python3
"""docs/sdd/roadmap.md의 명세 백로그(첫 열 머리글이 `ID`인 표)를 읽는다.

Spec Kit 훅, Issue 폼 생성 스크립트, PR 검증이 같은 규칙으로 명세 ID를 읽도록 한 곳에 둔다.
명령으로 실행하면 명세 ID가 백로그에 있는지 확인한다.

    python scripts/roadmap.py              # 백로그 전체 출력
    python scripts/roadmap.py QK-ING-002   # 있으면 0, 없으면 1
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROADMAP = ROOT / "docs" / "sdd" / "roadmap.md"

SPEC_ID = r"QK-[A-Z]{3}-\d{3}"
TABLE_SEPARATOR = re.compile(r"^\s*\|\s*:?-{3,}")


@dataclass(frozen=True)
class BacklogItem:
    spec_id: str
    wbs: str
    title: str


def load_backlog(path: Path = ROADMAP) -> dict[str, BacklogItem]:
    """명세 ID 순서를 유지한 {ID: 항목}을 돌려준다. 백로그 표가 없으면 빈 dict다."""
    if not path.is_file():
        return {}
    lines = path.read_text(encoding="utf-8").splitlines()
    items: dict[str, BacklogItem] = {}
    columns: dict[str, int] | None = None
    for index, line in enumerate(lines):
        if not line.lstrip().startswith("|"):
            columns = None
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        if TABLE_SEPARATOR.match(next_line):
            columns = {name: position for position, name in enumerate(cells)} if cells[0] == "ID" else None
            continue
        if columns is None or not re.fullmatch(SPEC_ID, cells[0]):
            continue

        def cell(name: str, fallback: int | None = None) -> str:
            position = columns.get(name, fallback)
            return cells[position] if position is not None and position < len(cells) else ""

        items[cells[0]] = BacklogItem(spec_id=cells[0], wbs=cell("WBS"), title=cell("제목", 1))
    return items


def main(argv: list[str]) -> int:
    items = load_backlog()
    if not items:
        print(f"명세 백로그 표를 찾지 못했습니다: {ROADMAP.relative_to(ROOT)}", file=sys.stderr)
        return 2
    if not argv:
        for item in items.values():
            print(f"{item.spec_id}\t{item.wbs}\t{item.title}")
        return 0
    missing = [spec_id for spec_id in argv if spec_id not in items]
    for spec_id in argv:
        if spec_id in items:
            item = items[spec_id]
            print(f"{item.spec_id}\t{item.wbs}\t{item.title}")
    if missing:
        print(f"로드맵 명세 백로그에 없는 ID: {', '.join(missing)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:]))
