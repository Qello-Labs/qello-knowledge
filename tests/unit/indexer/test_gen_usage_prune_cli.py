"""`qk-index usage prune`의 생성 사용량 정리(QK-GEN-001 tasks T043, research R-06, spec FR-020)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from qello_knowledge.adapters.postgres.generation_usage import GenerationUsageUnavailable
from qello_knowledge.domain.embedding import PruneResult, UsageOutcome
from qello_knowledge.indexer.cli import main
from tests.unit.fakes import InMemoryUsageLedger


class Ledger(InMemoryUsageLedger):
    def close(self) -> None:
        pass


PRUNED = PruneResult(3, 17)


class GenerationLedger:
    def __init__(self, result=PRUNED, error=None) -> None:
        self.result, self.error = result, error
        self.calls: list[int] = []
        self.closed = False

    def prune(self, retention_days: int = 90) -> PruneResult:
        self.calls.append(retention_days)
        if self.error:
            raise self.error
        return self.result

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def env(monkeypatch, tmp_path):
    for name in ("QK_EMBED_DAILY_ALLOWANCE", "QK_EMBED_INDEX_BUDGET", "QK_EMBED_QUERY_RESERVE", "DATABASE_URL"):
        monkeypatch.delenv(name, raising=False)
    return ["--env-file", str(tmp_path / ".env")]


def _ledger(settings, source):
    ledger = Ledger(settings, lambda: datetime(2026, 10, 20, 3, tzinfo=UTC))
    ledger.record("q", "m", 1, 1, 0.5, 0.5, False, UsageOutcome.OK)
    return ledger


def test_prune_also_prunes_generation_with_same_retention(env, capsys):
    made = []

    def factory(query_reserve, source):
        made.append(query_reserve)
        return generation

    generation = GenerationLedger()
    assert (
        main(
            ["usage", *env, "prune", "--retention-days", "45"],
            ledger_factory=_ledger,
            generation_ledger_factory=factory,
        )
        == 0
    )
    out = capsys.readouterr().out.splitlines()
    assert out[-1] == "generation_days_rolled_up=3 generation_rows_deleted=17"
    assert generation.calls == [45] and generation.closed and made == [3000]


def test_generation_store_failure_is_reported(env, capsys):
    failing = GenerationLedger(error=GenerationUsageUnavailable("x"))
    code = main(["usage", *env, "prune"], ledger_factory=_ledger, generation_ledger_factory=lambda r, s: failing)
    assert code == 2 and "generation_usage_unavailable" in capsys.readouterr().out and failing.closed


def test_today_output_does_not_touch_generation(env, capsys):
    def factory(query_reserve, source):
        raise AssertionError("today는 생성 장부를 만들지 않는다")

    assert main(["usage", *env], ledger_factory=_ledger, generation_ledger_factory=factory) == 0
    assert capsys.readouterr().out.splitlines()[2] == "query: used=0.50 reserve=3000"
