"""90일 보관 뒤 날짜 단위 집계(FR-025, research R-13)."""

from __future__ import annotations

import psycopg
import pytest

from qello_knowledge.domain.embedding import PruneResult
from qello_knowledge.domain.store import EmbeddingRef
from tests.localdb.store.builders import MODEL, vec

pytestmark = pytest.mark.localdb

INSERT = (
    "INSERT INTO qk.embedding_usage (occurred_at, purpose, run_id, model_version, input_count, input_bytes,"
    " estimated_neurons, neurons, measured, state, outcome)"
    " VALUES (now() - make_interval(days => %s), 'index', 'r', %s, 1, 1, 1, %s, %s, %s, %s)"
)


def test_old_days_roll_up_and_recent_days_stay(make_ledger, store, db_url) -> None:
    store.put_embedding(EmbeddingRef("H", MODEL), vec(1))
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(INSERT, (91, MODEL, 2, True, "settled", "ok"))
        conn.execute(INSERT, (91, MODEL, 3, False, "settled", "ok"))
        conn.execute(INSERT, (89, MODEL, 5, True, "settled", "ok"))
    ledger = make_ledger()
    assert ledger.prune() == PruneResult(1, 2)
    assert ledger.prune() == PruneResult(0, 0)
    with psycopg.connect(db_url) as conn:
        daily = conn.execute("SELECT neurons, calls, estimated_calls FROM qk.embedding_usage_daily").fetchall()
        remaining = conn.execute("SELECT count(*) FROM qk.embedding_usage").fetchone()
        vectors = conn.execute("SELECT count(*) FROM qk.embedding").fetchone()
    assert [(float(n), c, e) for n, c, e in daily] == [(5.0, 2, 1)]
    assert remaining == (1,) and vectors == (1,)
