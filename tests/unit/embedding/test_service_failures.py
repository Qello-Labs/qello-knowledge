"""US1 AS3·AS4: 일시 오류 재시도, 할당 소진, 인증 오류, 잘못된 응답(FR-004, FR-020)."""

import pytest

from qello_knowledge.domain.embedding import EmbedError, EmbedErrorKind, EmbedFailureKind, ProviderFailureKind
from qello_knowledge.embedding.fake import FakeEmbeddingProvider
from qello_knowledge.ports.embedder import ProviderFailure
from tests.unit.embedding.helpers import index_request

TRANSIENT = ProviderFailure(ProviderFailureKind.TRANSIENT, retry_after_seconds=2)


def test_transient_twice_then_success(make_harness) -> None:
    harness = make_harness(FakeEmbeddingProvider(fail_calls={1: TRANSIENT, 2: TRANSIENT}))
    result = harness.embedder.embed(index_request(["하나"]))
    assert result.items[0].vector is not None
    assert harness.sleeps == [2, 2]  # Retry-After를 따른다
    assert result.summary.provider_calls == 3


def test_transient_beyond_retry_limit_fails_the_items(make_harness) -> None:
    harness = make_harness(FakeEmbeddingProvider(fail_calls={n: TRANSIENT for n in range(1, 5)}))
    result = harness.embedder.embed(index_request(["하나", "둘"]))
    assert [item.failure for item in result.items] == [EmbedFailureKind.TRANSIENT] * 2
    assert len(harness.provider.calls) == 4 and len(harness.sleeps) == 3


def test_retry_delay_is_injected(make_harness) -> None:
    seen = []
    harness = make_harness(
        FakeEmbeddingProvider(fail_calls={1: ProviderFailure(ProviderFailureKind.TRANSIENT)}),
        retry_delay=lambda attempt, after: seen.append((attempt, after)) or 7.0,
    )
    harness.embedder.embed(index_request(["하나"]))
    assert seen == [(0, None)] and harness.sleeps == [7.0]


def test_provider_quota_stops_without_retry_and_sends_nothing_more(make_harness) -> None:
    quota = ProviderFailure(ProviderFailureKind.PROVIDER_QUOTA)
    harness = make_harness(FakeEmbeddingProvider(fail_calls={2: quota}), max_items=1)
    result = harness.embedder.embed(index_request(["하나", "둘", "셋"]))
    assert len(harness.provider.calls) == 2 and harness.sleeps == []
    assert [item.failure for item in result.items] == [
        None,
        EmbedFailureKind.PROVIDER_QUOTA,
        EmbedFailureKind.PROVIDER_QUOTA,
    ]
    assert len(harness.store.vectors) == 1  # 그 전 벡터는 저장돼 있다(FR-011)


def test_auth_config_stops_the_whole_request(make_harness) -> None:
    auth = ProviderFailure(ProviderFailureKind.AUTH_CONFIG)
    harness = make_harness(FakeEmbeddingProvider(fail_calls={2: auth}), max_items=1)
    with pytest.raises(EmbedError) as excinfo:
        harness.embedder.embed(index_request(["하나", "둘", "셋"]))
    assert excinfo.value.kind is EmbedErrorKind.AUTH_CONFIG
    assert len(harness.provider.calls) == 2 and len(harness.store.vectors) == 1


def test_wrong_dimension_is_bad_response_and_not_stored(make_harness) -> None:
    harness = make_harness(FakeEmbeddingProvider(wrong_dimension_calls=frozenset({1})))
    result = harness.embedder.embed(index_request(["하나", "둘"]))
    assert [item.failure for item in result.items] == [EmbedFailureKind.BAD_RESPONSE] * 2
    assert harness.store.vectors == {}


def test_default_retry_delay_uses_retry_after_then_backoff() -> None:
    from qello_knowledge.embedding.service import default_retry_delay

    assert default_retry_delay(0, 2.5) == 2.5
    assert default_retry_delay(0, 3600) == 60  # 제공자 대기 시간도 60초를 넘지 않는다
    assert [default_retry_delay(n, None) for n in range(8)] == [1, 2, 4, 8, 16, 32, 60, 60]
