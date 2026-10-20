"""묶음 나누기: 최대 32개·예상 토큰 32,768, 큰 텍스트 단독, 순서 유지(research R-06, Edge Cases)."""

from qello_knowledge.embedding.batching import make_batches, split_half


def test_splits_by_item_count_in_order() -> None:
    batches = make_batches([10] * 70, 8192)
    assert [len(b) for b in batches] == [32, 32, 6]
    assert [p for b in batches for p in b] == list(range(70))


def test_splits_by_token_sum() -> None:
    batches = make_batches([6000] * 6, 8192)
    assert batches == [(0, 1, 2, 3, 4), (5,)]  # 5 × 6000 = 30,000 ≤ 32,768


def test_large_text_goes_alone() -> None:
    assert make_batches([10, 7000, 10, 10], 8192) == [(0,), (1,), (2, 3)]


def test_split_half() -> None:
    assert split_half((0, 1, 2)) == ((0,), (1, 2))


def test_service_keeps_input_order_across_batches(make_harness) -> None:
    from tests.unit.embedding.helpers import index_request

    harness = make_harness(max_items=2)
    texts = [f"text {i}" for i in range(5)]
    result = harness.embedder.embed(index_request(texts))
    assert [len(call) for call in harness.provider.calls] == [2, 2, 1]
    assert [item.index for item in result.items] == list(range(5))
    assert [call for batch in harness.provider.calls for call in batch] == texts
