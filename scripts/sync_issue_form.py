#!/usr/bin/env python3
"""로드맵 명세 백로그로 Issue 폼의 기능명세서 드롭다운 옵션을 만든다.

GitHub Issue 폼은 옵션을 YAML에 고정으로 적어야 하므로, docs/sdd/roadmap.md 4절 백로그를 읽어
.github/ISSUE_TEMPLATE/work.yml의 BEGIN·END 표시 사이를 다시 쓴다.

    python scripts/sync_issue_form.py           # 폼 갱신
    python scripts/sync_issue_form.py --check   # 고치지 않고, 로드맵과 다르면 실패(CI용)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from roadmap import ROADMAP, ROOT, BacklogItem, load_backlog

FORM = ROOT / ".github" / "ISSUE_TEMPLATE" / "work.yml"
BEGIN = "# BEGIN roadmap-backlog"
END = "# END roadmap-backlog"
NOT_APPLICABLE = "해당 없음 (도구·기술부채 작업)"


def option_label(item: BacklogItem) -> str:
    wbs = f" (WBS {item.wbs})" if item.wbs else ""
    return f"{item.spec_id}{wbs} {item.title}".strip()


def render(form_text: str, items: dict[str, BacklogItem]) -> str:
    newline = "\r\n" if "\r\n" in form_text else "\n"
    lines = form_text.splitlines()
    begin = next((i for i, line in enumerate(lines) if line.strip().startswith(BEGIN)), None)
    end = next((i for i, line in enumerate(lines) if line.strip().startswith(END)), None)
    if begin is None or end is None or end < begin:
        raise ValueError(f"{FORM.relative_to(ROOT)}에서 '{BEGIN}'와 '{END}' 표시를 찾지 못했습니다.")
    indent = lines[begin][: len(lines[begin]) - len(lines[begin].lstrip())]
    labels = [option_label(item) for item in items.values()] + [NOT_APPLICABLE]
    options = [f"{indent}- {json.dumps(label, ensure_ascii=False)}" for label in labels]
    return newline.join(lines[: begin + 1] + options + lines[end:]) + newline


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="폼을 고치지 않고 로드맵과 다르면 실패한다")
    args = parser.parse_args()

    items = load_backlog()
    if not items:
        print(f"명세 백로그 표를 찾지 못해 폼을 바꾸지 않았습니다: {ROADMAP.relative_to(ROOT)}", file=sys.stderr)
        return 2
    current = FORM.read_bytes().decode("utf-8")
    try:
        expected = render(current, items)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 2

    if current.splitlines() == expected.splitlines():
        print(f"Issue 폼이 로드맵 백로그와 같습니다: 명세 {len(items)}개")
        return 0
    if args.check:
        print(
            "Issue 폼의 기능명세서 목록이 로드맵 백로그와 다릅니다. "
            "`python scripts/sync_issue_form.py`를 실행해 갱신한 뒤 커밋하세요.",
            file=sys.stderr,
        )
        return 1
    FORM.write_bytes(expected.encode("utf-8"))
    print(f"Issue 폼을 갱신했습니다: 명세 {len(items)}개")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    raise SystemExit(main())
