"""US5: 색인을 돌리기 전에 예상 사용량을 본다(AS1~AS4, FR-022~024)."""

from qello_knowledge.domain.embedding import MODELS, BudgetSettings, EmbedFailureKind
from qello_knowledge.embedding.estimate import estimated_neurons
from tests.unit.embedding.helpers import index_request

TEXTS = [f"문서 {i}" for i in range(100)]


def test_preview_counts_cache_hits_and_makes_no_side_effects(make_harness) -> None:
    harness = make_harness()
    harness.embedder.embed(index_request(TEXTS[:60]))
    calls, rows, stored = len(harness.provider.calls), len(harness.ledger.rows), len(harness.store.vectors)
    preview = harness.embedder.preview(index_request(TEXTS))
    assert (preview.requested, preview.cache_hits, preview.to_embed) == (100, 60, 40)
    assert preview.estimated_neurons == estimated_neurons(TEXTS[60:], MODELS["@cf/baai/bge-m3"])
    assert preview.basis.bytes_total == sum(len(t.encode()) for t in TEXTS[60:])
    assert preview.basis.bytes_per_token == 3.5 and preview.basis.neurons_per_million_tokens == 1075
    assert preview.index_budget == 5000 and preview.index_remaining == 5000 - preview.index_used_today
    assert preview.runnable is True
    assert (len(harness.provider.calls), len(harness.ledger.rows), len(harness.store.vectors)) == (calls, rows, stored)


def test_preview_over_budget_is_not_runnable(make_harness) -> None:
    harness = make_harness(settings=BudgetSettings(10000, 1, 3000))
    texts = ["본문 " * 2000 + str(i) for i in range(3)]
    preview = harness.embedder.preview(index_request(texts))
    assert preview.runnable is False and preview.estimated_neurons > preview.index_remaining == 1


def test_not_runnable_embed_sends_nothing(make_harness) -> None:
    harness = make_harness(settings=BudgetSettings(10000, 1, 3000))
    texts = ["본문 " * 2000 + str(i) for i in range(3)]
    result = harness.embedder.embed(index_request(texts))
    assert harness.provider.calls == []
    assert {item.failure for item in result.items} == {EmbedFailureKind.INDEX_BUDGET}


def test_over_limit_and_duplicates_are_counted(make_harness) -> None:
    preview = make_harness().embedder.preview(index_request(["가" * 30_000, "같음", "같음"]))
    assert (preview.over_limit_expected, preview.deduplicated, preview.to_embed) == (1, 1, 2)
