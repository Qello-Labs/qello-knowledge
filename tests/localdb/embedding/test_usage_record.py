"""US3: 외부 호출마다 원문 없이 사용량을 기록하고 하루 합계를 조회한다(AS1, AS3~AS5, FR-013~016, SC-003)."""

from __future__ import annotations

from datetime import UTC

import psycopg
import pytest

from qello_knowledge.domain.embedding import BudgetSettings, UsageOutcome

pytestmark = pytest.mark.localdb

MODEL = "@cf/baai/bge-m3"
SECRET_TEXT = "원문에만 있는 문장 7f3a"


def _rows(db_url: str) -> list[dict]:
    with psycopg.connect(db_url) as conn, conn.cursor(row_factory=psycopg.rows.dict_row) as cur:
        return cur.execute("SELECT * FROM qk.embedding_usage ORDER BY id").fetchall()


def test_settled_index_row_has_all_fields(make_ledger, db_url) -> None:
    ledger = make_ledger()
    reservation = ledger.reserve("run-1", MODEL, 3, 120, 0.04)
    assert reservation is not None
    ledger.settle(reservation, 0.03, True, UsageOutcome.OK)
    [row] = _rows(db_url)
    assert row["purpose"] == "index" and row["run_id"] == "run-1" and row["model_version"] == MODEL
    assert (row["input_count"], row["input_bytes"]) == (3, 120)
    assert (float(row["estimated_neurons"]), float(row["neurons"])) == (0.04, 0.03)
    assert (row["measured"], row["state"], row["outcome"]) == (True, "settled", "ok")
    assert row["usage_day"] == row["occurred_at"].astimezone(UTC).date()


def test_failed_call_is_recorded_with_zero(make_ledger, db_url) -> None:
    ledger = make_ledger()
    reservation = ledger.reserve("run-1", MODEL, 1, 40000, 12.3)
    ledger.settle(reservation, 0, False, UsageOutcome.INPUT_TOO_LONG)
    [row] = _rows(db_url)
    assert (float(row["neurons"]), row["measured"], row["outcome"]) == (0.0, False, "input_too_long")


def test_settle_twice_keeps_first_values(make_ledger, db_url) -> None:
    ledger = make_ledger()
    reservation = ledger.reserve("run-1", MODEL, 1, 10, 0.01)
    ledger.settle(reservation, 0.02, True, UsageOutcome.OK)
    ledger.settle(reservation, 9.99, False, UsageOutcome.TRANSIENT)
    [row] = _rows(db_url)
    assert (float(row["neurons"]), row["outcome"]) == (0.02, "ok")


def test_today_sums_by_purpose(make_ledger) -> None:
    ledger = make_ledger(BudgetSettings(10000, 100, 3000))
    ledger.settle(ledger.reserve("run-1", MODEL, 1, 10, 5), 4, True, UsageOutcome.OK)
    ledger.reserve("run-1", MODEL, 1, 10, 6)  # 정산 전 예약은 예상량으로 센다
    query = ledger.record("q-1", MODEL, 1, 10, 0.5, 0.5, False, UsageOutcome.OK)
    assert (query.query_used, query.query_reserve_exceeded) == (0.5, False)
    today = ledger.today()
    assert (today.total, today.index_used, today.query_used, today.index_remaining) == (10.5, 10, 0.5, 90)
    assert today.estimated_share == pytest.approx(6.5 / 10.5, abs=1e-4)


def test_query_reserve_exceeded_is_reported(make_ledger) -> None:
    ledger = make_ledger(BudgetSettings(10000, 5000, 1))
    assert ledger.record("q-1", MODEL, 1, 10, 2, 2, True, UsageOutcome.OK).query_reserve_exceeded


def test_no_column_holds_input_text(make_ledger, db_url) -> None:
    from tests.unit.embedding.helpers import build_harness, index_request

    harness = build_harness(ledger=make_ledger())
    harness.embedder.embed(index_request([SECRET_TEXT]))
    rows = _rows(db_url)
    assert rows and all(SECRET_TEXT not in str(value) for row in rows for value in row.values())


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO qk.embedding_usage (purpose, run_id, model_version, input_count, input_bytes,"
        " estimated_neurons, state) VALUES ('index', 'r', 'm', 1, 1, 0, 'settled')",
        "INSERT INTO qk.embedding_usage (purpose, run_id, model_version, input_count, input_bytes,"
        " estimated_neurons, state) VALUES ('query', 'r', 'm', 1, 1, 0, 'reserved')",
    ],
)
def test_check_constraints(db_url, sql) -> None:
    with psycopg.connect(db_url, autocommit=True) as conn, pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(sql)


def test_small_amounts_are_not_rounded_away(make_ledger) -> None:
    ledger = make_ledger(BudgetSettings(10000, 1, 3000))
    for _ in range(100):
        ledger.record("q", MODEL, 1, 10, 0.0097, 0.0097, True, UsageOutcome.OK)
    granted = sum(ledger.reserve("r", MODEL, 1, 10, 0.004) is not None for _ in range(300))
    today = ledger.today()
    assert today.query_used == pytest.approx(0.97)  # SC-003: 제공자 합과 같다
    assert granted == 250 and today.index_used == pytest.approx(1.0)  # 0.004 × 250 = 1
