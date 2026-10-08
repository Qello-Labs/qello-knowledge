#!/usr/bin/env python3
"""Codex 세션에 CODEX.md와 TASK.md를 넣는다.

Claude Code는 CLAUDE.md의 `@AGENTS.md`, `@TASK.md` import로 두 문서를 늘 컨텍스트에 둔다.
Codex는 AGENTS.md만 자동으로 읽고 import 문법이 없으므로, 세션을 시작·재개·압축할 때마다
이 훅이 CODEX.md와 TASK.md를 SessionStart additionalContext로 넣는다.
입력을 해석할 수 없으면 아무것도 하지 않는다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCUMENTS = ("CODEX.md", "TASK.md")
MISSING = {
    "CODEX.md": "저장소 루트에 CODEX.md가 없다. AGENTS.md만 따른다.",
    "TASK.md": (
        "저장소 루트에 TASK.md가 없다. AGENTS.md 1절에 따라 조사, 계획, 문서 초안까지만 하고 "
        "구현, 색인 실행, 외부 API 비용이 드는 작업, PR 생성은 하지 않는다."
    ),
}


def section(name: str) -> str:
    path = ROOT / name
    if not path.is_file():
        return f"# {name}\n\n{MISSING[name]}"
    return f"# {name} (저장소 루트, 세션 시작 훅이 주입)\n\n{path.read_text(encoding='utf-8').strip()}"


def main() -> int:
    # Windows의 기본 입력 인코딩(cp949 등)이 아니라 UTF-8로 읽는다.
    try:
        event = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 0
    if not isinstance(event, dict) or event.get("hook_event_name") != "SessionStart":
        return 0

    output = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": "\n\n".join(section(name) for name in DOCUMENTS),
        }
    }
    sys.stdout.write(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
