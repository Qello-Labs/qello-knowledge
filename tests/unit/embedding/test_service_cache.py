"""US2: 변경 없는 텍스트는 다시 임베딩하지 않는다(AS1~AS5, FR-008~012, SC-001)."""

from qello_knowledge.domain.embedding import EmbedFailureKind, ProviderFailureKind
from qello_knowledge.embedding.fake import FakeEmbeddingProvider
from qello_knowledge.ports.embedder import ProviderFailure
from tests.unit.embedding.helpers import index_request, query_request

TEXTS = [f"문서 {i}" for i in range(10)]


def test_second_run_makes_no_calls_and_returns_same_vectors(make_harness) -> None:
    harness = make_harness()
    first = harness.embedder.embed(index_request(TEXTS))
    calls = len(harness.provider.calls)
    second = harness.embedder.embed(index_request(TEXTS))
    assert len(harness.provider.calls) == calls  # SC-001
    assert [i.vector for i in second.items] == [i.vector for i in first.items]
    assert all(item.cached for item in second.items)
    assert second.summary.cache_hits == 10 and second.summary.provider_calls == 0


def test_only_changed_text_is_sent(make_harness) -> None:
    harness = make_harness()
    harness.embedder.embed(index_request(TEXTS))
    harness.provider.calls.clear()
    changed = [*TEXTS[:9], "문서 9 수정"]
    result = harness.embedder.embed(index_request(changed))
    assert harness.provider.sent_texts == ["문서 9 수정"]
    assert [item.cached for item in result.items] == [True] * 9 + [False]


def test_other_model_version_misses(make_harness) -> None:
    from qello_knowledge.domain.store import EmbeddingRef
    from qello_knowledge.embedding.hashing import input_hash

    harness = make_harness()
    harness.store.vectors[EmbeddingRef(input_hash("문서 0"), "@cf/other/model")] = (0.0,) * 1024
    harness.embedder.embed(index_request(["문서 0"]))
    assert harness.provider.sent_texts == ["문서 0"]


def test_duplicate_texts_in_batch_are_sent_once(make_harness) -> None:
    harness = make_harness()
    result = harness.embedder.embed(index_request(["같은 텍스트", "다른 텍스트", "같은 텍스트"]))
    assert harness.provider.sent_texts == ["같은 텍스트", "다른 텍스트"]
    assert result.items[0].vector == result.items[2].vector is not None
    assert result.summary.deduplicated == 1


def test_query_vectors_are_not_stored(make_harness) -> None:
    harness = make_harness()
    result = harness.embedder.embed(query_request(["질문"]))
    assert result.items[0].vector is not None
    assert harness.store.put_calls == [] and harness.store.find_calls == 0


def test_vectors_before_quota_are_already_stored(make_harness) -> None:
    quota = ProviderFailure(ProviderFailureKind.PROVIDER_QUOTA)
    harness = make_harness(FakeEmbeddingProvider(fail_calls={2: quota}), max_items=2)
    result = harness.embedder.embed(index_request(TEXTS[:4]))
    assert [item.failure for item in result.items[2:]] == [EmbedFailureKind.PROVIDER_QUOTA] * 2
    assert len(harness.store.vectors) == 2
    harness2_calls = len(harness.provider.calls)
    harness.provider.fail_calls.clear()
    again = harness.embedder.embed(index_request(TEXTS[:4]))
    assert [item.cached for item in again.items] == [True, True, False, False]
    assert len(harness.provider.calls) == harness2_calls + 1
