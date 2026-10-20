"""US4: 색인이 질의응답 몫을 쓰지 않게 일일 예산을 지킨다(AS1~AS5, FR-018~021, SC-002)."""

from qello_knowledge.domain.embedding import BudgetSettings, EmbedFailureKind, ProviderFailureKind, UsageOutcome
from qello_knowledge.embedding.fake import FakeEmbeddingProvider
from qello_knowledge.embedding.service import QUERY_RESERVE_WARNING, QUOTA_MISMATCH_WARNING
from qello_knowledge.ports.embedder import ProviderFailure
from tests.unit.embedding.helpers import index_request, query_request

TEXTS = [f"문서 {i} " + "본문 " * 300 for i in range(6)]  # 항목마다 예상 약 0.5 Neurons


def _spend_index_budget(harness) -> None:
    budget = harness.ledger.settings.index_budget
    harness.ledger.settle(harness.ledger.reserve("earlier", "m", 1, 1, budget), budget, True, UsageOutcome.OK)


def _harness(make_harness, budget: int = 5000, **options):
    return make_harness(settings=BudgetSettings(10000, budget, 3000), **options)


def test_spent_budget_blocks_index_requests(make_harness) -> None:
    harness = _harness(make_harness, budget=10)
    _spend_index_budget(harness)
    result = harness.embedder.embed(index_request(TEXTS[:2]))
    assert harness.provider.calls == []
    assert [item.failure for item in result.items] == [EmbedFailureKind.INDEX_BUDGET] * 2


def test_query_still_works_when_index_budget_is_spent(make_harness) -> None:
    harness = _harness(make_harness, budget=10)
    _spend_index_budget(harness)
    assert harness.embedder.embed(query_request(["질문"])).items[0].vector is not None


def test_partial_run_processes_within_budget_and_caches_it(make_harness) -> None:
    harness = _harness(make_harness, budget=1, max_items=1)
    result = harness.embedder.embed(index_request(TEXTS, allow_partial=True))
    done = [item for item in result.items if item.vector is not None]
    assert done and result.items[0].vector is not None
    assert all(item.failure is EmbedFailureKind.INDEX_BUDGET for item in result.items[len(done) :])
    assert len(harness.store.vectors) == len(done)
    assert harness.ledger.today().index_used <= 1


def test_without_partial_over_budget_run_sends_nothing(make_harness) -> None:
    harness = _harness(make_harness, budget=1)
    result = harness.embedder.embed(index_request(TEXTS))
    assert harness.provider.calls == [] and harness.ledger.rows == []
    assert {item.failure for item in result.items} == {EmbedFailureKind.INDEX_BUDGET}


def test_new_utc_day_has_new_budget(make_harness) -> None:
    harness = _harness(make_harness, budget=10)
    harness.ledger.clock.now = harness.ledger.clock.now.replace(hour=23, minute=59, second=59)
    _spend_index_budget(harness)
    assert harness.embedder.embed(index_request(TEXTS[:1])).items[0].failure is EmbedFailureKind.INDEX_BUDGET
    harness.clock.advance(seconds=1)  # 00:00 UTC = 한국 시간 09:00
    assert harness.embedder.embed(index_request(TEXTS[:1])).items[0].vector is not None


def test_query_over_reserve_only_warns(make_harness) -> None:
    harness = make_harness(settings=BudgetSettings(10000, 5000, 1), provider=FakeEmbeddingProvider(neurons=2))
    result = harness.embedder.embed(query_request(["질문"]))
    assert result.items[0].vector is not None
    assert QUERY_RESERVE_WARNING in result.summary.warnings


def test_provider_quota_with_budget_left_warns(make_harness) -> None:
    quota = ProviderFailure(ProviderFailureKind.PROVIDER_QUOTA)
    harness = make_harness(FakeEmbeddingProvider(fail_calls={1: quota}))
    result = harness.embedder.embed(index_request(["하나"]))
    assert result.items[0].failure is EmbedFailureKind.PROVIDER_QUOTA
    assert QUOTA_MISMATCH_WARNING in result.summary.warnings
