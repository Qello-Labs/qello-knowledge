"""레지스트리에서 `.env.example`을 만든다. 이름·설명·placeholder만 쓰고 실제 값은 쓰지 않는다(FR-005)."""

from __future__ import annotations

import sys
from pathlib import Path

from qello_knowledge.config.registry import SETTINGS, Entrypoint

HEADER = """\
# Qello Knowledge 설정 예시. 이 파일은 qello_knowledge.config.example이 만든다. 직접 고치지 않는다.
# 복사해서 .env로 쓰고 값을 채운다. .env는 git에 올리지 않는다.
# 같은 이름의 실행 환경 변수가 있으면 그 값이 우선한다.
"""

_LABELS = {
    Entrypoint.QUERY: "질의응답",
    Entrypoint.INDEX: "색인",
    Entrypoint.RELAY: "중계 Worker",
    Entrypoint.REGISTER: "명령 등록",
}


def render() -> str:
    blocks = [HEADER]
    for spec in SETTINGS:
        users = ", ".join(_LABELS[e] for e in Entrypoint if e in spec.entrypoints)
        flags = ["필수" if spec.required else "선택"]
        if spec.secret:
            flags.append("비밀")
        value = spec.default if spec.default is not None else f"<{spec.name.lower().replace('_', '-')}>"
        blocks.append(
            f"# {spec.description}\n# 진입점: {users} | {', '.join(flags)} | 형식: {spec.rule.description}\n"
            f"{spec.name}={value}\n"
        )
    return "\n".join(blocks)


def main() -> int:
    target = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(".env.example")
    target.write_text(render(), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
