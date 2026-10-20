"""동시 예약: 같은 날 예산 100에 예상 60짜리 예약 두 개가 겹치면 하나만 통과한다(FR-021, SC-002)."""

from __future__ import annotations

import threading

import pytest

from qello_knowledge.domain.embedding import BudgetSettings, UsageOutcome

pytestmark = pytest.mark.localdb

MODEL = "@cf/baai/bge-m3"
SETTINGS = BudgetSettings(10000, 100, 3000)


def test_only_one_of_two_concurrent_reservations_is_granted(make_ledger) -> None:
    ledgers = [make_ledger(SETTINGS), make_ledger(SETTINGS)]
    barrier = threading.Barrier(2)
    results = []

    def reserve(ledger) -> None:
        barrier.wait()
        results.append(ledger.reserve("run", MODEL, 1, 10, 60))

    threads = [threading.Thread(target=reserve, args=(ledger,)) for ledger in ledgers]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sorted(r is not None for r in results) == [False, True]
    assert ledgers[0].today().index_used == 60  # 정산 전 예약은 예상량으로 합산


def test_overrun_is_bounded_by_one_request(make_ledger) -> None:
    ledger = make_ledger(SETTINGS)
    first = ledger.reserve("run", MODEL, 1, 10, 60)
    ledger.settle(first, 70, True, UsageOutcome.OK)  # 실제가 예상보다 10 크다
    assert ledger.reserve("run", MODEL, 1, 10, 40) is None  # 70 + 40 > 100
    assert ledger.reserve("run", MODEL, 1, 10, 30) is not None
    assert ledger.today().index_used - SETTINGS.index_budget <= 70 - 60
