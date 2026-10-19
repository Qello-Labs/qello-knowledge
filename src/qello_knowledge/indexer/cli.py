"""`qk-index`: 색인 진입점. 지금은 설정 점검만 하고, 수집은 후속 명세(QK-ING-002, QK-SYN-001)가 채운다."""

from __future__ import annotations

import argparse

from qello_knowledge.config.cli import add_check_options, run_check
from qello_knowledge.config.registry import Entrypoint


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="qk-index", description="색인 진입점")
    sub = parser.add_subparsers(dest="command", required=True)
    add_check_options(sub.add_parser("check", help="설정만 점검한다. 외부 호출 없음"))
    add_check_options(sub.add_parser("run", help="설정을 점검하고 색인을 실행한다"))
    args = parser.parse_args(argv)

    code, _ = run_check(Entrypoint.INDEX, args)
    if code != 0 or args.command == "check":
        return code
    print("수집할 자료원 없음")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
