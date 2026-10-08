#!/usr/bin/env python3
"""Codex의 `$speckit-specify` 명세 디렉터리를 specs/<명세 ID>-<짧은 이름>으로 고정한다.

판정 규칙은 Claude Code 훅(.claude/hooks/speckit_spec_id.py)의 resolve()를 그대로 쓴다.
Codex에는 Claude의 Skill 도구가 없어 PreToolUse로 스킬 호출을 가로챌 수 없다. 그래서
speckit-specify는 명시 호출만 허용하고(.agents/skills/speckit-specify/agents/openai.yaml),
사용자가 입력한 `$speckit-specify`를 UserPromptSubmit에서 검사한다.
조건을 만족하면 Codex에게 디렉터리 경로를 지시하고, 아니면 턴을 막고 이유를 알려 준다.
입력을 해석할 수 없으면 아무것도 하지 않는다.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / ".claude" / "hooks"))

from speckit_spec_id import SKILL, resolve  # noqa: E402

# Codex는 프롬프트 어디에 있든 `$skill-name`을 스킬 호출로 본다. 인자는 언급 뒤의 텍스트다.
MENTION = re.compile(rf"(?:^|\s)\${SKILL}(?:\s+|$)(.*)", re.DOTALL)


def arguments_from_prompt(prompt: str) -> str | None:
    match = MENTION.search(prompt)
    return match.group(1) if match else None


def for_codex(message: str) -> str:
    """Claude 훅의 안내문에 있는 `/speckit-*` 호출 문법을 Codex의 `$speckit-*`로 바꾼다."""
    return message.replace("/speckit-", "$speckit-")


def main() -> int:
    # Windows의 기본 입력 인코딩(cp949 등)이 아니라 UTF-8로 읽는다.
    try:
        event = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 0
    if not isinstance(event, dict) or event.get("hook_event_name") != "UserPromptSubmit":
        return 0
    arguments = arguments_from_prompt(event.get("prompt") or "")
    if arguments is None:
        return 0

    allowed, message = resolve(arguments)
    message = for_codex(message)
    if allowed:
        output = {
            "hookSpecificOutput": {
                "hookEventName": "UserPromptSubmit",
                "additionalContext": message,
            }
        }
    else:
        output = {"decision": "block", "reason": message}
    sys.stdout.write(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
