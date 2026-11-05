"""재색인 미리 보기(QK-STO-002 research R-05, FR-006, US1-1·US1-3·US1-9)."""

import pytest

from qello_knowledge.domain.embedding import BudgetSettings
from qello_knowledge.sync.preview import reindex_preview
from qello_knowledge.sync.run import SyncOptions, current_spec, plan_all, run_sync
from qello_knowledge.sync.versions import estimated_days
from tests.unit.sync.helpers import harness
from tests.unit.sync.reindex_fakes import DOCS, NEW_CHUNKING, ReindexMemoryStore, mismatched

REINDEX = SyncOptions(reindex=True)
KEYS = {
    "candidate",
    "candidate_status",
    "documents",
    "to_process",
    "embedding",
    "budget",
    "estimated_days",
    "coverage",
    "hidden_held",
    "security_takedowns",
}


@pytest.mark.parametrize(
    ("estimated", "remaining", "budget", "days"),
    [
        (0, 0, 5000, 1),
        (10, 10, 5000, 1),
        (10.5, 10, 5000, 2),
        (5010, 10, 5000, 2),
        (10011, 10, 5000, 4),
        (5, 1, 0, None),
    ],
)
def test_estimated_days(estimated, remaining, budget, days):
    assert estimated_days(estimated, remaining, budget) == days


def _preview(m, h, options=REINDEX):
    spec = current_spec(h.deps)
    plans = plan_all(h.targets, h.deps, spec, m.store.index_state(), options)
    return reindex_preview(
        plans, h.deps.embedder, spec, m.store.index_state(), candidate_status=None, coverage=None, options=options
    )


def test_preview_keys_no_provider_call_and_no_writes():
    m = mismatched()
    writes = m.store.writes
    value, runnable = _preview(m, m.h)
    assert set(value) == KEYS and runnable
    assert set(value["embedding"]) == {"requested", "cache_hits", "to_embed", "estimated_neurons", "basis"}
    assert set(value["budget"]) == {"index_budget", "used_today", "remaining_today"}
    assert value["documents"] == 10 and value["to_process"] == 10
    assert value["estimated_days"] == 1
    assert m.h.provider.calls == [] and m.store.writes == writes


def test_preview_without_cache_shows_full_embedding_cost():
    """임베딩 모델 교체처럼 캐시를 쓸 수 없으면 모든 청크를 새로 임베딩한다(US1-9). 캐시 키는 (입력, 모델)이다."""
    m = mismatched()
    empty_cache = ReindexMemoryStore()
    h = harness(DOCS, store=m.store, cache_store=empty_cache, chunking=NEW_CHUNKING)
    value, _ = _preview(m, h)
    assert value["embedding"]["cache_hits"] == 0
    assert value["embedding"]["to_embed"] == value["embedding"]["requested"] > 0
    assert value["embedding"]["estimated_neurons"] > 0


def test_budget_exceeded_refuses_before_writing_and_partial_runs():
    m = mismatched()
    empty_cache = ReindexMemoryStore()
    tight = BudgetSettings(index_budget=0)
    h = harness(DOCS, store=m.store, cache_store=empty_cache, chunking=NEW_CHUNKING, settings=tight)
    value, runnable = _preview(m, h)
    assert not runnable and value["estimated_days"] is None
    runs = dict(m.store.runs)
    h = harness(DOCS, store=m.store, cache_store=empty_cache, chunking=NEW_CHUNKING, settings=tight)
    result = run_sync(h.targets, h.deps, REINDEX)
    assert (result.exit_code, result.summary["reason"]) == (5, "budget_exceeded")
    assert "security_takedowns" in result.summary
    assert m.store.runs == runs and h.provider.calls == []
    partial = harness(DOCS, store=m.store, cache_store=empty_cache, chunking=NEW_CHUNKING, settings=tight)
    result = run_sync(partial.targets, partial.deps, SyncOptions(reindex=True, allow_partial_budget=True))
    assert result.run_id and result.summary.get("reason") is None  # 부분 실행은 기록을 남기고 예산 안에서 멈춘다
    assert partial.provider.calls == []
