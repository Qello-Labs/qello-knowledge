"""US3: 외부 호출마다 원문 없이 사용량을 남긴다(FR-013~015, SC-003)."""

import pytest

from qello_knowledge.domain.embedding import EmbedError, EmbedErrorKind
from qello_knowledge.embedding.fake import FakeEmbeddingProvider
from tests.unit.embedding.helpers import index_request, query_request


def test_ledger_total_equals_provider_reported_usage(make_harness) -> None:
    harness = make_harness(FakeEmbeddingProvider(neurons=0.25), max_items=2)
    result = harness.embedder.embed(index_request([f"t{i}" for i in range(5)]))
    rows = harness.ledger.rows
    assert len(rows) == 3 == result.summary.provider_calls
    assert sum(r["neurons"] for r in rows) == pytest.approx(0.75) == result.summary.neurons
    assert all(r["measured"] is True and r["state"] == "settled" for r in rows)


def test_missing_provider_usage_is_estimated(make_harness) -> None:
    harness = make_harness(FakeEmbeddingProvider(neurons=None))
    result = harness.embedder.embed(index_request(["가" * 350]))
    [row] = harness.ledger.rows
    assert row["measured"] is False and row["neurons"] == row["estimated_neurons"] > 0
    assert result.summary.neurons == result.summary.estimated_neurons


def test_cache_only_run_writes_no_usage_rows(make_harness) -> None:
    harness = make_harness()
    harness.embedder.embed(index_request(["하나"]))
    rows = len(harness.ledger.rows)
    result = harness.embedder.embed(index_request(["하나"]))
    assert len(harness.ledger.rows) == rows
    assert (result.summary.neurons, result.summary.cache_hits) == (0, 1)


def test_query_usage_is_recorded_without_reservation(make_harness) -> None:
    harness = make_harness()
    harness.embedder.embed(query_request(["질문 하나"]))
    [row] = harness.ledger.rows
    assert (row["purpose"], row["state"], row["outcome"]) == ("query", "settled", "ok")


def test_ledger_failure_stops_and_keeps_earlier_vectors(make_harness) -> None:
    harness = make_harness(max_items=1)
    original = harness.ledger.settle
    calls = []

    def flaky(*args):
        calls.append(args)
        if len(calls) == 2:
            raise RuntimeError("db down")
        return original(*args)

    harness.ledger.settle = flaky
    with pytest.raises(EmbedError) as excinfo:
        harness.embedder.embed(index_request(["하나", "둘", "셋"]))
    assert excinfo.value.kind is EmbedErrorKind.USAGE_UNAVAILABLE
    assert len(harness.provider.calls) == 2  # 기록 실패 뒤 다음 외부 호출 없음
    assert len(harness.store.vectors) == 1


def test_usage_rows_hold_no_text(make_harness) -> None:
    secret = "원문에만 있는 문장"
    harness = make_harness()
    harness.embedder.embed(index_request([secret]))
    harness.embedder.embed(query_request([secret + " 질문"]))
    assert all(secret not in str(value) for row in harness.ledger.rows for value in row.values())
