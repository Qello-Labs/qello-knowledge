#!/usr/bin/env python3
"""Mark WBS progress in docs/sdd/roadmap.md from GitHub Issue titles. Reads GitHub only."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROADMAP = ROOT / "docs" / "sdd" / "roadmap.md"

DONE, ACTIVE, TODO = "✅", "🔄", "⬜"
MARK_ORDER = (DONE, ACTIVE)

WBS_ID = re.compile(r"^[0-9]+\.(?:[0-9]+|G)$")
WBS_IN_TITLE = re.compile(r"\(WBS ([0-9]+\.(?:[0-9]+|G))\)")
PHASE_LABEL = re.compile(r"^Phase ([0-9]+)$")


def split_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip()[1:-1].split("|")]


def join_row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def is_separator(cells: list[str]) -> bool:
    return all(cell and set(cell) <= {"-", ":"} for cell in cells)


def fetch_issues() -> list[dict]:
    command = [
        "gh", "issue", "list", "--state", "all", "--limit", "1000",
        "--json", "number,title,state,stateReason,url",
    ]
    try:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError) as error:
        detail = getattr(error, "stderr", "") or str(error)
        print(f"GitHub Issue를 읽지 못했다: {detail.strip()}", file=sys.stderr)
        sys.exit(2)
    return json.loads(result.stdout)


def status_by_wbs(issues: list[dict]) -> dict[str, tuple[str, list[dict]]]:
    """열린 Issue가 있으면 진행 중, 모두 완료로 닫혔으면 완료. 'not planned' 등으로 닫힌 Issue는 세지 않는다."""
    grouped: dict[str, list[dict]] = {}
    for issue in issues:
        closed_unplanned = issue["state"] == "CLOSED" and issue.get("stateReason") != "COMPLETED"
        if closed_unplanned:
            continue
        for wbs in WBS_IN_TITLE.findall(issue["title"]):
            grouped.setdefault(wbs, []).append(issue)
    statuses = {}
    for wbs, related in grouped.items():
        related.sort(key=lambda issue: issue["number"])
        mark = ACTIVE if any(issue["state"] == "OPEN" for issue in related) else DONE
        statuses[wbs] = (mark, related)
    return statuses


def status_cell(current: str, computed: tuple[str, list[dict]] | None) -> str:
    # Issue가 없는 작업(회의 등)은 담당자가 적은 표시를 보존한다.
    if computed is None:
        return current or TODO
    mark, related = computed
    links = ", ".join(f"[#{issue['number']}]({issue['url']})" for issue in related)
    return f"{mark} {links}"


def progress_cell(marks: list[str]) -> str:
    counts = [f"{mark} {marks.count(mark)}" for mark in MARK_ORDER if marks.count(mark)]
    return f"{' · '.join(counts) or '0'} / {len(marks)}"


def update(text: str, statuses: dict[str, tuple[str, list[dict]]]) -> tuple[str, list[str], set[str]]:
    lines = text.split("\n")
    changes: list[str] = []
    seen: set[str] = set()
    marks_by_phase: dict[str, list[str]] = {}
    summary_rows: list[int] = []
    progress_index = -1

    # 3절 단계 표의 상태 열을 먼저 고친 뒤, 그 결과로 2절 진행 열을 센다.
    header: list[str] | None = None
    for index, line in enumerate(lines):
        if not line.strip().startswith("|"):
            header = None
            continue
        cells = split_row(line)
        if header is None:
            header = cells
            if "단계" in cells and "진행" in cells:
                progress_index = cells.index("진행")
            continue
        if is_separator(cells):
            continue
        if "WBS" in header and "상태" in header:
            wbs = cells[header.index("WBS")]
            if not WBS_ID.match(wbs):
                continue
            seen.add(wbs)
            status_index = header.index("상태")
            new = status_cell(cells[status_index], statuses.get(wbs))
            if new != cells[status_index]:
                changes.append(f"{wbs}: {cells[status_index] or '(빈칸)'} → {new}")
                cells[status_index] = new
                lines[index] = join_row(cells)
            marks_by_phase.setdefault(wbs.split(".")[0], []).append(new.split()[0])
        elif header[0] == "단계" and progress_index >= 0 and PHASE_LABEL.match(cells[0]):
            summary_rows.append(index)

    for index in summary_rows:
        cells = split_row(lines[index])
        phase = PHASE_LABEL.match(cells[0]).group(1)
        new = progress_cell(marks_by_phase.get(phase, []))
        if new != cells[progress_index]:
            changes.append(f"{cells[0]} 진행: {cells[progress_index] or '(빈칸)'} → {new}")
            cells[progress_index] = new
            lines[index] = join_row(cells)

    return "\n".join(lines), changes, seen


def write_atomically(path: Path, text: str) -> None:
    descriptor, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
        os.replace(temp_name, path)
    except BaseException:
        Path(temp_name).unlink(missing_ok=True)
        raise


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true", help="로드맵 파일을 갱신한다. 없으면 바뀔 내용만 보여 준다")
    args = parser.parse_args()

    statuses = status_by_wbs(fetch_issues())
    original = ROADMAP.read_text(encoding="utf-8")
    updated, changes, seen = update(original, statuses)

    for wbs in sorted(set(statuses) - seen):
        numbers = ", ".join(f"#{issue['number']}" for issue in statuses[wbs][1])
        print(f"경고: Issue {numbers}의 WBS {wbs}가 로드맵 3절 표에 없다", file=sys.stderr)

    if not changes:
        print("로드맵 진행 표시가 GitHub Issue와 일치한다.")
        return 0
    for change in changes:
        print(change)
    if args.write:
        write_atomically(ROADMAP, updated)
        print(f"{len(changes)}건을 {ROADMAP.relative_to(ROOT)}에 반영했다.")
        return 0
    print(f"{len(changes)}건이 최신이 아니다. --write로 반영한다.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
