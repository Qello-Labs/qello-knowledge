"""`qk-index usage`, `qk-index usage prune`(QK-EMB-001 contracts/cli.md). 외부 호출 없이 저장소만 본다.

종료 코드: 0 정상, 1 설정 검사 실패(예산 교차 검사 포함), 2 저장소 사용 불가.
"""

from __future__ import annotations

import argparse
import json
import os
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Protocol

from qello_knowledge.config.check import BUDGET_CHECK, budget_settings
from qello_knowledge.config.loader import load, merge_sources, read_env_file
from qello_knowledge.config.registry import Entrypoint
from qello_knowledge.domain.embedding import BudgetSettings, DailyUsage, EmbedError, PruneResult

EXIT_OK = 0
EXIT_SETTINGS = 1
EXIT_UNAVAILABLE = 2


class UsageReader(Protocol):
    def today(self) -> DailyUsage: ...
    def prune(self, retention_days: int = 90) -> PruneResult: ...
    def close(self) -> None: ...


LedgerFactory = Callable[[BudgetSettings, Mapping[str, str]], UsageReader]


def postgres_ledger(settings: BudgetSettings, source: Mapping[str, str]) -> UsageReader:
    from qello_knowledge.adapters.postgres.connection import database_url
    from qello_knowledge.adapters.postgres.usage import PostgresUsageLedger

    return PostgresUsageLedger(database_url(source), settings)


def add_usage_parser(sub: argparse._SubParsersAction) -> None:
    usage = sub.add_parser("usage", help="오늘(UTC) 임베딩 사용량과 남은 색인 예산을 보인다. 외부 호출 없음")
    usage.add_argument("--json", action="store_true")
    usage.add_argument("--env-file", type=Path, default=Path(".env"))
    commands = usage.add_subparsers(dest="usage_command")
    prune = commands.add_parser("prune", help="보관 기간이 지난 호출별 사용량 기록을 일 합계로 옮기고 지운다")
    prune.add_argument("--retention-days", type=int, default=90)
    prune.add_argument("--env-file", type=Path, default=argparse.SUPPRESS)  # 상위 옵션 값을 덮지 않는다


def render_usage(usage: DailyUsage, settings: BudgetSettings, json_output: bool) -> str:
    data = {
        "usage_day": usage.usage_day.isoformat(),
        "total": usage.total,
        "index_used": usage.index_used,
        "query_used": usage.query_used,
        "index_budget": settings.index_budget,
        "query_reserve": settings.query_reserve,
        "index_remaining": usage.index_remaining,
        "estimated_share": usage.estimated_share,
    }
    if json_output:
        return json.dumps(data, ensure_ascii=False)
    return "\n".join(
        [
            f"usage_day={data['usage_day']} (UTC, 한국 시간 09:00 기준 초기화)",
            f"index: used={usage.index_used:.2f} budget={settings.index_budget} remaining={usage.index_remaining:.2f}",
            f"query: used={usage.query_used:.2f} reserve={settings.query_reserve}",
            f"total={usage.total:.2f} allowance={settings.daily_allowance}"
            f" estimated_share={round(usage.estimated_share * 100)}%",
        ]
    )


def run_usage(args: argparse.Namespace, ledger_factory: LedgerFactory = postgres_ledger) -> int:
    source = merge_sources(os.environ, read_env_file(args.env_file))
    settings = budget_settings(load(Entrypoint.INDEX, environ=source, env_file=None))
    if settings is None:
        print("설정 검사 실패: QK_EMBED_* 형식 오류")
        return EXIT_SETTINGS
    if not settings.within_allowance:
        print(f"설정 검사 실패: {BUDGET_CHECK} ({settings.index_budget} + {settings.query_reserve}"
              f" <= {settings.daily_allowance})")  # fmt: skip
        return EXIT_SETTINGS
    try:
        ledger = ledger_factory(settings, source)
        try:
            if getattr(args, "usage_command", None) == "prune":
                result = ledger.prune(args.retention_days)
                print(f"days_rolled_up={result.days_rolled_up} rows_deleted={result.rows_deleted}")
            else:
                print(render_usage(ledger.today(), settings, args.json))
        finally:
            ledger.close()
    except EmbedError as error:
        print(f"저장소 사용 불가: {error.kind.value}")
        return EXIT_UNAVAILABLE
    return EXIT_OK
