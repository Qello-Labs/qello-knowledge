"""US1 AS2: 입력 한도를 넘는 텍스트는 자르지 않고 그 항목만 실패한다(FR-003, SC-004)."""

from qello_knowledge.domain.embedding import EmbedFailureKind
from qello_knowledge.embedding.fake import FakeEmbeddingProvider
from tests.unit.embedding.helpers import index_request

LONG = "가" * 30_000  # 예상 25,715토큰 > 6,144(한도의 75%)


def test_large_text_is_sent_alone_and_fails_alone(make_harness) -> None:
    harness = make_harness(FakeEmbeddingProvider(too_long=frozenset({LONG})))
    result = harness.embedder.embed(index_request(["앞", LONG, "뒤"]))
    assert harness.provider.calls == [("앞",), (LONG,), ("뒤",)]
    assert [item.failure for item in result.items] == [None, EmbedFailureKind.INPUT_TOO_LONG, None]
    assert result.summary.failures == {"input_too_long": 1}


def test_multi_text_rejection_is_split_to_find_the_cause(make_harness) -> None:
    bad = "보통 길이지만 제공자가 거부하는 텍스트"
    harness = make_harness(FakeEmbeddingProvider(too_long=frozenset({bad})))
    texts = ["a", "b", bad, "c"]
    result = harness.embedder.embed(index_request(texts))
    assert harness.provider.calls[0] == tuple(texts)
    assert [item.failure for item in result.items] == [None, None, EmbedFailureKind.INPUT_TOO_LONG, None]
    assert harness.store.put_calls and all(len(v) == 1024 for v in harness.store.vectors.values())
    assert len(harness.store.vectors) == 3  # 잘린 벡터 저장 0건
