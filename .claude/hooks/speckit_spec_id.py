#!/usr/bin/env python3
"""/speckit-specify의 명세 디렉터리를 specs/<명세 ID>-<짧은 이름>으로 고정한다.

사용자가 직접 입력한 경우(UserPromptSubmit)와 Claude가 Skill 도구로 호출한 경우(PreToolUse)를
모두 처리한다. 명세 ID는 인자의 첫 단어로 받고, docs/sdd/roadmap.md 명세 백로그에 있어야 한다.
조건을 만족하면 Claude에게 디렉터리 경로를 지시하고, 아니면 실행을 막고 이유를 알려 준다.
입력을 해석할 수 없으면 아무것도 하지 않는다.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPECS = ROOT / "specs"
SKILL = "speckit-specify"

# 백로그 해석 규칙은 Issue 폼 생성·PR 검증과 같아야 하므로 scripts/roadmap.py를 쓴다.
sys.path.insert(0, str(ROOT / "scripts"))
try:
    from roadmap import SPEC_ID, load_backlog
except ImportError:
    SPEC_ID = r"QK-[A-Z]{3}-\d{3}"
    load_backlog = None

LEADING_ID = re.compile(rf"^\[?({SPEC_ID})\]?(?=\s|$)")
DIRECTORY_ARG = re.compile(r"SPECIFY_FEATURE_DIRECTORY=[\"']?([^\s\"']+)")
DIRECTORY_NAME = re.compile(rf"^({SPEC_ID})-[a-z0-9]+(?:-[a-z0-9]+)*$")
USAGE = "사용법: /speckit-specify QK-ING-002 <기능 설명>"


def backlog() -> dict[str, str]:
    """명세 백로그를 {ID: 제목}으로 읽는다. 읽지 못하면 빈 dict이고, 이때는 ID 형식만 검사한다."""
    if load_backlog is None:
        return {}
    return {spec_id: item.title for spec_id, item in load_backlog().items()}


def existing_dirs(spec_id: str) -> list[Path]:
    if not SPECS.is_dir():
        return []
    return sorted(path for path in SPECS.glob(f"{spec_id}-*") if path.is_dir())


def unstarted(items: dict[str, str], limit: int = 5) -> str:
    started = {path.name[:10] for path in SPECS.glob("QK-*")} if SPECS.is_dir() else set()
    rows = [f"  {spec_id} {title}" for spec_id, title in items.items() if spec_id not in started]
    return "\n".join(rows[:limit])


def check_known(spec_id: str, items: dict[str, str]) -> str | None:
    if items and spec_id not in items:
        return (
            f"docs/sdd/roadmap.md 명세 백로그에 없는 ID입니다: {spec_id}. "
            "백로그에 ID를 먼저 추가한 뒤 다시 실행하세요."
        )
    return None


def resolve(arguments: str) -> tuple[bool, str]:
    """(허용 여부, Claude에게 줄 지시 또는 사용자에게 보일 차단 사유)를 돌려준다."""
    items = backlog()
    explicit = DIRECTORY_ARG.search(arguments)
    if explicit:
        path = explicit.group(1).replace("\\", "/").rstrip("/")
        name_match = DIRECTORY_NAME.match(Path(path).name)
        if not path.startswith("specs/") or not name_match:
            return False, (
                f"SPECIFY_FEATURE_DIRECTORY={path}는 규칙에 맞지 않습니다. "
                "specs/QK-ING-002-github-repo-source처럼 specs/<명세 ID>-<영어 소문자 짧은 이름> 형식을 쓰세요."
            )
        problem = check_known(name_match.group(1), items)
        if problem:
            return False, problem
        return True, (
            f"[명세 ID 규칙] 사용자가 지정한 SPECIFY_FEATURE_DIRECTORY={path}를 그대로 쓴다. "
            "숫자 순번이나 타임스탬프 접두사를 붙이지 않는다."
        )

    leading = LEADING_ID.match(arguments.strip())
    if not leading:
        lines = [f"명세 ID를 첫 단어로 넣어 주세요. {USAGE}"]
        candidates = unstarted(items)
        if candidates:
            lines += ["아직 명세 디렉터리가 없는 백로그 항목:", candidates]
        return False, "\n".join(lines)

    spec_id = leading.group(1)
    problem = check_known(spec_id, items)
    if problem:
        return False, problem

    found = existing_dirs(spec_id)
    if found:
        names = ", ".join(f"specs/{path.name}" for path in found)
        return False, (
            f"{spec_id}의 명세 디렉터리가 이미 있습니다: {names}. "
            "내용을 보완하려면 /speckit-clarify를 쓰거나 spec.md를 직접 고치세요. "
            "처음부터 다시 쓰려면 기존 디렉터리를 정리한 뒤 실행하세요."
        )

    title = items.get(spec_id, "")
    title_note = f" 로드맵 백로그 제목: {title}." if title else ""
    return True, (
        f"[명세 ID 규칙] 이번 /speckit-specify의 명세 ID: {spec_id}.{title_note} "
        f"SPECIFY_FEATURE_DIRECTORY를 사용자가 지정한 값으로 취급해 specs/{spec_id}-<short-name>을 쓴다. "
        "<short-name>은 1단계 규칙으로 만든 영어 소문자·숫자·하이픈 2~4단어다. "
        "숫자 순번(001-)이나 타임스탬프 접두사를 쓰지 않고, .specify/feature.json에도 같은 경로를 저장한다. "
        f"spec.md 제목에 명세 ID({spec_id})를 적는다. 인자 첫 단어의 명세 ID는 기능 설명에서 뺀다."
    )


def arguments_from_prompt(prompt: str) -> str | None:
    match = re.match(rf"^\s*/{SKILL}(?:\s+|$)(.*)", prompt, re.DOTALL)
    return match.group(1) if match else None


def main() -> int:
    # Windows의 기본 입력 인코딩(cp949 등)이 아니라 UTF-8로 읽는다.
    try:
        event = json.loads(sys.stdin.buffer.read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return 0
    if not isinstance(event, dict):
        return 0
    name = event.get("hook_event_name")

    if name == "UserPromptSubmit":
        if event.get("prompt_type") not in (None, "user_typed"):
            return 0
        arguments = arguments_from_prompt(event.get("prompt") or "")
        if arguments is None:
            return 0
        allowed, message = resolve(arguments)
        if allowed:
            output = {
                "hookSpecificOutput": {
                    "hookEventName": "UserPromptSubmit",
                    "additionalContext": message,
                }
            }
        else:
            output = {"decision": "block", "reason": message}
    elif name == "PreToolUse" and event.get("tool_name") == "Skill":
        tool_input = event.get("tool_input") or {}
        skill = tool_input.get("skill_name") or tool_input.get("skill") or ""
        if skill.split(":")[-1] != SKILL:
            return 0
        arguments = tool_input.get("input") or tool_input.get("args") or ""
        allowed, message = resolve(arguments)
        specific: dict[str, str] = {"hookEventName": "PreToolUse"}
        if allowed:
            specific["additionalContext"] = message
        else:
            specific["permissionDecision"] = "deny"
            specific["permissionDecisionReason"] = message
        output = {"hookSpecificOutput": specific}
    else:
        return 0

    sys.stdout.write(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
