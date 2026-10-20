"""`qk-index usage`·`usage --json`·`usage prune`(contracts/cli.md). 메모리 장부로 돈다."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from qello_knowledge.domain.embedding import EmbedError, EmbedErrorKind, UsageOutcome
from qello_knowledge.indexer.cli import main
from tests.unit.fakes import InMemoryUsageLedger


class ClosableLedger(InMemoryUsageLedger):
    closed = False

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def env(monkeypatch, tmp_path):
    for name in ("QK_EMBED_DAILY_ALLOWANCE", "QK_EMBED_INDEX_BUDGET", "QK_EMBED_QUERY_RESERVE"):
        monkeypatch.delenv(name, raising=False)
    return ["--env-file", str(tmp_path / ".env")]


@pytest.fixture
def ledgers():
    made: list[ClosableLedger] = []

    def factory(settings, source):
        ledger = ClosableLedger(settings, lambda: datetime(2026, 10, 20, 3, tzinfo=UTC))
        ledger.settle(ledger.reserve("r", "m", 1, 1, 312.4), 312.4, True, UsageOutcome.OK)
        ledger.record("q", "m", 1, 1, 0.52, 0.52, False, UsageOutcome.OK)
        made.append(ledger)
        return ledger

    factory.made = made
    return factory


def test_usage_prints_contract_format(env, ledgers, capsys) -> None:
    assert main(["usage", *env], ledger_factory=ledgers) == 0
    assert capsys.readouterr().out.splitlines() == [
        "usage_day=2026-10-20 (UTC, 한국 시간 09:00 기준 초기화)",
        "index: used=312.40 budget=5000 remaining=4687.60",
        "query: used=0.52 reserve=3000",
        "total=312.92 allowance=10000 estimated_share=0%",
    ]
    assert ledgers.made[0].closed


def test_usage_json(env, ledgers, capsys) -> None:
    assert main(["usage", "--json", *env], ledger_factory=ledgers) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["usage_day"] == "2026-10-20" and data["index_remaining"] == pytest.approx(4687.6)
    assert set(data) == {
        "usage_day", "total", "index_used", "query_used", "index_budget", "query_reserve",
        "index_remaining", "estimated_share",
    }  # fmt: skip


def test_prune(env, ledgers, capsys) -> None:
    assert main(["usage", *env, "prune", "--retention-days", "30"], ledger_factory=ledgers) == 0
    assert capsys.readouterr().out.strip() == "days_rolled_up=0 rows_deleted=0"


def test_budget_cross_check_failure_exits_one(env, ledgers, capsys, monkeypatch) -> None:
    monkeypatch.setenv("QK_EMBED_INDEX_BUDGET", "8000")
    assert main(["usage", *env], ledger_factory=ledgers) == 1
    assert "8000 + 3000 <= 10000" in capsys.readouterr().out
    assert ledgers.made == []


def test_unavailable_store_exits_two(env, capsys) -> None:
    def broken(settings, source):
        raise EmbedError(EmbedErrorKind.USAGE_UNAVAILABLE, "사용량 저장소에 연결할 수 없다")

    assert main(["usage", *env], ledger_factory=broken) == 2
    assert "usage_unavailable" in capsys.readouterr().out
