"""색인 진입점. 실제 수집 연결은 QK-SYN-001이 맡는다."""

from __future__ import annotations

import argparse
from pathlib import Path

from qello_knowledge.config.cli import add_check_options, run_check
from qello_knowledge.config.registry import Entrypoint
from qello_knowledge.indexer.ask_cli import AskFactory, add_ask_parser, postgres_ask, run_ask
from qello_knowledge.indexer.search_cli import SearchFactory, add_search_parser, postgres_search, run_search
from qello_knowledge.indexer.sync_cli import (
    add_sync_parsers,
    build_runtime,
    postgres_sync_store,
    query_command,
    run_command,
)
from qello_knowledge.indexer.usage import (
    GenerationLedgerFactory,
    LedgerFactory,
    add_usage_parser,
    postgres_generation_ledger,
    postgres_ledger,
    run_usage,
)
from qello_knowledge.security.policy import load_policy
from qello_knowledge.security.report import render_security_report, security_report
from qello_knowledge.sources.config import load_sources
from qello_knowledge.sources.report import render_report, source_report
from qello_knowledge.sources.scope_review import load_checked_sources

REVIEWS = Path("config/source_reviews")
EXCEPTIONS = Path("config/security_exceptions.toml")


def main(
    argv: list[str] | None = None,
    *,
    ledger_factory: LedgerFactory = postgres_ledger,
    generation_ledger_factory: GenerationLedgerFactory = postgres_generation_ledger,
    sync_factory=build_runtime,
    sync_store_factory=postgres_sync_store,
    store_policy_path=Path("config/store_policy.toml"),
    search_factory: SearchFactory = postgres_search,
    ask_factory: AskFactory = postgres_ask,
    stdin=None,
) -> int:
    parser = argparse.ArgumentParser(prog="qk-index", description="색인 진입점")
    sub = parser.add_subparsers(dest="command", required=True)
    add_check_options(sub.add_parser("check", help="설정만 점검한다. 외부 호출 없음"))
    run = sub.add_parser("run", help="설정을 점검하고 색인을 실행한다")
    add_check_options(run)
    run.add_argument("--sources", type=Path, default=Path("config/sources.toml"))
    run.add_argument("--reviews", type=Path, default=REVIEWS)
    run.add_argument("--exceptions", type=Path, default=EXCEPTIONS)
    sources = sub.add_parser("sources", help="자료원 설정을 검사한다")
    source_commands = sources.add_subparsers(dest="source_command", required=True)
    check = source_commands.add_parser("check", help="원본 호출 없이 자료원 설정만 검사한다")
    check.add_argument("--sources", type=Path, default=Path("config/sources.toml"))
    check.add_argument("--reviews", type=Path, default=REVIEWS)
    check.add_argument("--json", action="store_true")
    security = sub.add_parser("security", help="보안 필터 규칙을 검사한다")
    security_commands = security.add_subparsers(dest="security_command", required=True)
    security_check = security_commands.add_parser("check", help="예외 파일을 검증하고 보안 규칙 버전을 보인다")
    security_check.add_argument("--sources", type=Path, default=Path("config/sources.toml"))
    security_check.add_argument("--exceptions", type=Path, default=EXCEPTIONS)
    security_check.add_argument("--json", action="store_true")
    add_usage_parser(sub)
    add_sync_parsers(sub, run)
    add_search_parser(sub)
    add_ask_parser(sub)
    args = parser.parse_args(argv)

    if args.command == "run":
        if args.preview and args.trigger is not None:
            parser.error("--preview and --trigger cannot be combined")
        return run_command(args, sync_factory, store_policy_path)
    if args.command in {"runs", "index"}:
        return query_command(args, sync_store_factory, store_policy_path)
    if args.command == "usage":
        return run_usage(args, ledger_factory, generation_ledger_factory)
    if args.command == "search":
        return run_search(args, search_factory, stdin)
    if args.command == "ask":
        return run_ask(args, ask_factory, stdin)

    if args.command not in {"sources", "security"}:
        code, _ = run_check(Entrypoint.INDEX, args)
        if code != 0 or args.command == "check":
            return code
    configs, issues = (
        load_sources(args.sources) if args.command == "security" else load_checked_sources(args.sources, args.reviews)
    )
    report = source_report(args.sources, configs, issues)
    if args.command == "sources" or issues:
        print(render_report(report, json_output=getattr(args, "json", False)))
        return 1 if issues else 0
    policy, policy_issues = load_policy(args.exceptions, configs)
    if args.command == "security" or policy_issues:
        print(
            render_security_report(
                security_report(args.exceptions, policy, policy_issues), getattr(args, "json", False)
            )
        )
        return 1 if policy_issues else 0
    for config in configs:
        print(f"{config.name}: {'수집 대기' if config.enabled else '비활성'}")
    if not any(config.enabled for config in configs):
        print("수집할 자료원 없음")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
