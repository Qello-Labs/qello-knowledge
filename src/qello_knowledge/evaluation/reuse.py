"""질의 벡터 재사용과 실제 제공자 호출 세기(QK-EVL-001 spec FR-014, research R-06).

- `ReusingEmbedder`는 `Embedder`를 감싸 같은 질문 문장의 질의 임베딩을 한 번만 부른다. 결과와 예외를 메모리에만 담고
  `forget`으로 버린다. 디스크·저장소·실행 기록에 벡터를 남기지 않는다. 검색 코드(`retrieval/`)는 바꾸지 않는다.
- `CountingProvider`는 제공자 시도를 모두 센다. 검색 요약의 호출 수를 더하면 재사용한 결과를 대상·방식 수만큼 겹쳐 센다.
  Neurons는 성공한 묶음만 센다. 제공자가 알려 준 값은 측정, 없으면 추정이다.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from qello_knowledge.domain.embedding import (
    EmbedError,
    EmbedPreview,
    EmbedPurpose,
    EmbedRequest,
    EmbedResult,
    ModelSpec,
)
from qello_knowledge.domain.source_config import RetryPolicy
from qello_knowledge.embedding.estimate import estimated_neurons
from qello_knowledge.ports.embedder import Embedder, EmbeddingProvider, ProviderBatch


def call_limit(questions: int, retry: RetryPolicy) -> int:
    """질의 임베딩 호출 상한. 질문마다 한 번 + 재시도(research R-07). `EmbeddingService`에 준 정책과 같은 값을 쓴다."""
    return questions * (retry.max_retries + 1)


class CountingProvider:
    """`EmbeddingProvider` 감싸기. 성공·실패 시도를 모두 센다."""

    def __init__(self, inner: EmbeddingProvider) -> None:
        self._inner = inner
        self.calls = 0
        self.measured_neurons = 0.0
        self.estimated_neurons = 0.0

    @property
    def neurons(self) -> float:
        return self.measured_neurons + self.estimated_neurons

    def embed_texts(self, model: ModelSpec, texts: Sequence[str]) -> ProviderBatch:
        self.calls += 1
        batch = self._inner.embed_texts(model, texts)  # 실패는 그대로 올린다. 실패한 시도는 0 Neurons
        if batch.neurons is None:
            self.estimated_neurons += estimated_neurons(texts, model)
        else:
            self.measured_neurons += batch.neurons
        return batch


@dataclass(frozen=True)
class EmbedOutcome:
    """한 문장의 첫 질의 임베딩 결과 종류. 실행기는 이 값으로만 멈춤을 가린다(research R-08)."""

    kind: Literal["vector", "item_failure", "error"]
    value: str | None  # 항목 실패면 `EmbedFailureKind` 값, 묶음 전체 실패면 `EmbedErrorKind` 값


class ReusingEmbedder:
    """`Embedder` 구현. 질의용 단일 입력만 재사용하고 나머지는 그대로 넘긴다."""

    def __init__(self, inner: Embedder) -> None:
        self._inner = inner
        self._results: dict[str, EmbedResult | EmbedError] = {}

    @staticmethod
    def _key(request: EmbedRequest) -> str | None:
        if request.purpose is EmbedPurpose.QUERY and len(request.inputs) == 1:
            return request.inputs[0].text
        return None

    def embed(self, request: EmbedRequest) -> EmbedResult:
        key = self._key(request)
        if key is None:
            return self._inner.embed(request)
        stored = self._results.get(key)
        if isinstance(stored, EmbedError):
            raise EmbedError(stored.kind)
        if stored is not None:
            return stored
        try:
            result = self._inner.embed(request)
        except EmbedError as error:
            self._results[key] = EmbedError(error.kind)
            raise
        self._results[key] = result
        return result

    def preview(self, request: EmbedRequest) -> EmbedPreview:
        return self._inner.preview(request)

    def outcome(self, text: str) -> EmbedOutcome | None:
        stored = self._results.get(text)
        if stored is None:
            return None
        if isinstance(stored, EmbedError):
            return EmbedOutcome("error", stored.kind.value)
        failure = stored.items[0].failure if stored.items else None
        if failure is not None:
            return EmbedOutcome("item_failure", failure.value)
        return EmbedOutcome("vector", None)

    def forget(self, text: str) -> None:
        self._results.pop(text, None)


__all__ = ["CountingProvider", "EmbedOutcome", "ReusingEmbedder", "call_limit"]
