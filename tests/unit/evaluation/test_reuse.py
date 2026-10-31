"""질의 벡터 재사용과 실제 제공자 호출 세기(QK-EVL-001 spec FR-014, SC-006, research R-06, tasks T019)."""

from __future__ import annotations

import pytest

from qello_knowledge.domain.embedding import (
    MODELS,
    BudgetSettings,
    EmbedError,
    EmbedErrorKind,
    EmbedFailureKind,
    EmbedInput,
    EmbedPurpose,
    EmbedRequest,
    ProviderFailureKind,
)
from qello_knowledge.domain.retrieval import RetrievalMode, RetrievalRequest
from qello_knowledge.domain.source_config import RetryPolicy
from qello_knowledge.embedding.estimate import estimated_neurons
from qello_knowledge.embedding.fake import FakeEmbeddingProvider
from qello_knowledge.embedding.service import EmbeddingService
from qello_knowledge.evaluation.reuse import CountingProvider, EmbedOutcome, ReusingEmbedder, call_limit
from qello_knowledge.ports.embedder import ProviderFailure
from qello_knowledge.retrieval import RetrievalDeps, retrieve
from tests.unit.fakes import InMemoryUsageLedger, MemoryEmbeddingStore
from tests.unit.retrieval.fakes import FakeRetrievalStore, keyword_result, no_block, vector_result

MODEL = "@cf/baai/bge-m3"
RETRY = RetryPolicy(max_retries=1)
QUESTIONS = ("결제 실패를 다시 시도하는 함수는?", "배포 금지 요일은?", "회식 장소는?", "토큰 보관 규칙은?")


def _service(provider: FakeEmbeddingProvider) -> tuple[ReusingEmbedder, CountingProvider]:
    counter = CountingProvider(provider)
    budget = BudgetSettings()
    service = EmbeddingService(
        counter,
        MemoryEmbeddingStore(),
        InMemoryUsageLedger(budget),
        budget,
        no_block,
        retry_policy=RETRY,
        sleep=lambda seconds: None,
    )
    return ReusingEmbedder(service), counter


def _request(text: str) -> EmbedRequest:
    return EmbedRequest(inputs=(EmbedInput(text),), purpose=EmbedPurpose.QUERY, model_version=MODEL, run_id="r")


def test_one_provider_call_per_question_across_modes_and_targets() -> None:
    embedder, counter = _service(FakeEmbeddingProvider())
    stores = [FakeRetrievalStore(vector=vector_result(1, 2), keyword=keyword_result((1, 1))) for _ in range(3)]
    for question in QUESTIONS:
        for store in stores:
            for mode in (RetrievalMode.VECTOR, RetrievalMode.HYBRID, RetrievalMode.KEYWORD):
                request = RetrievalRequest(question, mode=mode, want_context=False)
                assert retrieve(request, RetrievalDeps(store=store, embedder=embedder)).status == "ok"
        embedder.forget(question)
    assert counter.calls == len(QUESTIONS)
    assert sum(len(s.calls) for s in stores) == len(QUESTIONS) * 3 * 4  # 벡터 1 + 하이브리드 2 + 키워드 1


def test_same_text_returns_first_result_without_calling_again() -> None:
    embedder, counter = _service(FakeEmbeddingProvider())
    first = embedder.embed(_request("배포 금지 요일은?"))
    second = embedder.embed(_request("배포 금지 요일은?"))
    assert second is first and counter.calls == 1
    assert embedder.outcome("배포 금지 요일은?") == EmbedOutcome("vector", None)
    assert embedder.outcome("다른 질문") is None


def test_item_failure_is_reused_and_visible_as_outcome() -> None:
    quota = ProviderFailure(ProviderFailureKind.PROVIDER_QUOTA)
    embedder, counter = _service(FakeEmbeddingProvider(fail_calls={1: quota}))
    first = embedder.embed(_request("배포 금지 요일은?"))
    assert first.items[0].failure is EmbedFailureKind.PROVIDER_QUOTA
    assert embedder.embed(_request("배포 금지 요일은?")) is first and counter.calls == 1
    assert embedder.outcome("배포 금지 요일은?") == EmbedOutcome("item_failure", "provider_quota")


def test_embed_error_is_reused_and_counted() -> None:
    auth = ProviderFailure(ProviderFailureKind.AUTH_CONFIG)
    embedder, counter = _service(FakeEmbeddingProvider(fail_calls={1: auth}))
    for _ in range(3):
        with pytest.raises(EmbedError) as raised:
            embedder.embed(_request("배포 금지 요일은?"))
        assert raised.value.kind is EmbedErrorKind.AUTH_CONFIG
    assert counter.calls == 1 and counter.neurons == 0  # 실패한 시도는 0 Neurons
    assert embedder.outcome("배포 금지 요일은?") == EmbedOutcome("error", "auth_config")


def test_forget_calls_again() -> None:
    embedder, counter = _service(FakeEmbeddingProvider())
    embedder.embed(_request("배포 금지 요일은?"))
    embedder.forget("배포 금지 요일은?")
    assert embedder.outcome("배포 금지 요일은?") is None
    embedder.embed(_request("배포 금지 요일은?"))
    assert counter.calls == 2


def test_transient_retry_counts_every_attempt() -> None:
    transient = ProviderFailure(ProviderFailureKind.TRANSIENT)
    embedder, counter = _service(FakeEmbeddingProvider(fail_calls={1: transient}))
    assert embedder.embed(_request("배포 금지 요일은?")).items[0].vector is not None
    assert counter.calls == 2  # 실패 1 + 재시도 성공 1


def test_neurons_are_measured_or_estimated() -> None:
    text = "배포 금지 요일은?"
    expected = estimated_neurons([text], MODELS[MODEL])
    embedder, counter = _service(FakeEmbeddingProvider())  # 제공자가 사용량을 알려 준다
    embedder.embed(_request(text))
    assert counter.measured_neurons == pytest.approx(expected) and counter.estimated_neurons == 0
    embedder, counter = _service(FakeEmbeddingProvider(neurons=None))
    embedder.embed(_request(text))
    assert counter.estimated_neurons == pytest.approx(expected) and counter.measured_neurons == 0
    assert counter.neurons == pytest.approx(expected)


def test_call_limit_follows_injected_retry_policy() -> None:
    assert call_limit(5, RETRY) == 10
    assert call_limit(5, RetryPolicy(max_retries=3)) == 20


def test_preview_is_passed_through() -> None:
    embedder, counter = _service(FakeEmbeddingProvider())
    embedder.preview(_request("배포 금지 요일은?"))
    assert counter.calls == 0
