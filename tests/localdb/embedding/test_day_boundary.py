"""하루 경계는 00:00 UTC다(US4 AS4의 저장소 쪽)."""

from __future__ import annotations

from datetime import date

import psycopg
import pytest

pytestmark = pytest.mark.localdb

INSERT = (
    "INSERT INTO qk.embedding_usage (occurred_at, purpose, run_id, model_version, input_count, input_bytes,"
    " estimated_neurons, neurons, measured, state, outcome)"
    " VALUES (%s, 'index', 'r', 'm', 1, 1, 0, %s, true, 'settled', 'ok')"
)


def test_records_split_at_utc_midnight(db_url) -> None:
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(INSERT, ("2026-10-20 23:59:59+00", 1))
        conn.execute(INSERT, ("2026-10-21 00:00:00+00", 2))
        conn.execute(INSERT, ("2026-10-21 08:59:59+09", 4))  # 한국 시간 09:00 전 = 전날(UTC)
        days = conn.execute("SELECT usage_day, sum(neurons) FROM qk.embedding_usage GROUP BY 1 ORDER BY 1").fetchall()
        first = conn.execute("SELECT qk.embedding_usage_today(5000, 3000, '2026-10-20')").fetchone()[0]
    assert [(d, float(n)) for d, n in days] == [(date(2026, 10, 20), 5.0), (date(2026, 10, 21), 2.0)]
    assert first["index_used"] == 5
