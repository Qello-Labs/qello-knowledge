"""두 진입점의 `check` 명령 공통 부분. 종료 코드는 통과 0, 실패 1이다."""

from __future__ import annotations

import argparse
from collections.abc import Mapping
from pathlib import Path

from qello_knowledge.config.check import CheckReport, build_report
from qello_knowledge.config.loader import load
from qello_knowledge.config.registry import Entrypoint


def add_check_options(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="JSON 한 줄로 출력한다")
    parser.add_argument("--env-file", type=Path, default=Path(".env"), help="로컬 설정 파일 경로 (기본 .env)")


def run_check(
    entrypoint: Entrypoint,
    args: argparse.Namespace,
    environ: Mapping[str, str] | None = None,
) -> tuple[int, CheckReport]:
    report = build_report(load(entrypoint, environ=environ, env_file=args.env_file))
    print(report.to_json() if args.json else report.to_text())
    return (0 if report.ok else 1), report
