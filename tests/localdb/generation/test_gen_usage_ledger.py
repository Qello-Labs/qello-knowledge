"""생성 사용량 표·함수와 장부(QK-GEN-001 tasks T040, research R-06, data-model 6절, SC-007)."""

from __future__ import annotations

import psycopg
import pytest

from qello_knowledge.adapters.postgres.generation_usage import GenerationUsageUnavailable, PostgresGenerationLedger
from qello_knowledge.adapters.postgres.usage import PostgresUsageLedger
from qello_knowledge.domain.embedding import BudgetSettings, PruneResult, UsageOutcome
from qello_knowledge.domain.generation import GenerationUsage

pytestmark = pytest.mark.localdb

INSERT = (
    "INSERT INTO qk.generation_usage (occurred_at, run_id, model_id, prompt_version, attempt, estimated_input_tokens,"
    " neurons, measured, outcome) VALUES (now() - make_interval(days => %s), 'r', 'm', 'p', 1, 1, %s, %s, 'ok')"
)


def _usage(**overrides) -> GenerationUsage:
    values = {
        "run_id": "answer-1", "model_id": "@cf/qwen/qwen3-30b-a3b-fp8", "prompt_version": "gen-p1-abc",
        "attempt": 1, "input_tokens": 1000, "output_tokens": 50, "estimated_input_tokens": 900,
        "neurons": 6.2, "measured": True, "outcome": "ok",
    }  # fmt: skip
    values.update(overrides)
    return GenerationUsage(**values)


@pytest.fixture
def ledger(db_url):
    with PostgresGenerationLedger(db_url, 3000) as instance:
        yield instance


def test_record_returns_answer_usage_with_embedding_query_share(ledger, db_url):
    with PostgresUsageLedger(db_url, BudgetSettings()) as embedding:
        embedding.record("query-1", "@cf/baai/bge-m3", 1, 30, 0.1, 0.4, True, UsageOutcome.OK)
        before = embedding.today()
        today = ledger.record(_usage())
        after = embedding.today()
    assert today.generation_used == pytest.approx(6.2)
    assert today.query_embedding_used == pytest.approx(0.4)
    assert today.answer_total == pytest.approx(6.6) and today.day_total == pytest.approx(6.6)
    assert today.query_reserve == 3000 and not today.query_reserve_exceeded
    assert before == after  # 기존 임베딩 하루 합계(query_used·index_remaining)는 생성 기록 전후로 같다


def test_reserve_exceeded_uses_answer_total(db_url):
    with PostgresGenerationLedger(db_url, 5) as small:
        assert small.record(_usage(neurons=6.0)).query_reserve_exceeded


def test_index_budget_judgement_ignores_generation(db_url):
    with (
        PostgresGenerationLedger(db_url, 3000) as gen,
        PostgresUsageLedger(db_url, BudgetSettings(10000, 10, 3000)) as emb,
    ):
        gen.record(_usage(neurons=100.0))
        assert (
            emb.reserve("index-1", "@cf/baai/bge-m3", 1, 10, 5.0) is not None
        )  # 색인 예산 10 안(생성 100은 세지 않는다)


@pytest.mark.parametrize(
    "sql",
    [
        "INSERT INTO qk.generation_usage (purpose, run_id, model_id, prompt_version, attempt, estimated_input_tokens,"
        " neurons, measured, outcome) VALUES ('query', 'r', 'm', 'p', 1, 1, 1, true, 'ok')",
        "INSERT INTO qk.generation_usage (run_id, model_id, prompt_version, attempt, estimated_input_tokens,"
        " neurons, measured, outcome) VALUES ('r', 'm', 'p', 3, 1, 1, true, 'ok')",
        "INSERT INTO qk.generation_usage (run_id, model_id, prompt_version, attempt, estimated_input_tokens,"
        " neurons, measured, outcome) VALUES ('r', 'm', 'p', 1, 1, 1, true, 'weird')",
        "INSERT INTO qk.generation_usage (run_id, model_id, prompt_version, attempt, estimated_input_tokens,"
        " neurons, measured, outcome) VALUES ('r', 'm', 'p', 1, 1, -1, true, 'ok')",
    ],
)
def test_constraints(db_url, sql):
    with psycopg.connect(db_url, autocommit=True) as conn, pytest.raises(psycopg.errors.CheckViolation):
        conn.execute(sql)


def test_no_raw_text_columns(db_url):
    with psycopg.connect(db_url) as conn:
        columns = {
            row[0]
            for row in conn.execute(
                "SELECT column_name FROM information_schema.columns"
                " WHERE table_schema = 'qk' AND table_name = 'generation_usage'"
            )
        }
    assert columns == {
        "id", "purpose", "occurred_at", "usage_day", "run_id", "model_id", "prompt_version", "attempt", "input_tokens",
        "output_tokens", "estimated_input_tokens", "neurons", "measured", "truncated", "outcome",
    }  # fmt: skip


def test_prune_rolls_up_old_days_and_is_rerunnable(ledger, db_url):
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(INSERT, (91, 2, True))
        conn.execute(INSERT, (91, 3, False))
        conn.execute(INSERT, (89, 5, True))
    assert ledger.prune() == PruneResult(1, 2)
    assert ledger.prune() == PruneResult(0, 0)
    with psycopg.connect(db_url) as conn:
        daily = conn.execute("SELECT neurons, calls, estimated_calls FROM qk.generation_usage_daily").fetchall()
        remaining = conn.execute("SELECT count(*) FROM qk.generation_usage").fetchone()
    assert [(float(n), c, e) for n, c, e in daily] == [(5.0, 2, 1)] and remaining == (1,)


def test_prune_rejects_retention_below_one(ledger):
    with pytest.raises(GenerationUsageUnavailable):
        ledger.prune(0)
