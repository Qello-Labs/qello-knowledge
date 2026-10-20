"""외부 호출 없는 결정적 가짜 제공자(FR-006). 테스트와 후속 명세 개발에 쓴다.

같은 텍스트는 언제나 같은 단위 벡터가 된다. 호출 기록과 실패 주입을 지원한다.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from hashlib import sha256

from qello_knowledge.domain.embedding import ModelSpec, ProviderFailureKind
from qello_knowledge.embedding.estimate import estimated_neurons
from qello_knowledge.ports.embedder import ProviderBatch, ProviderFailure

ESTIMATE = "estimate"


def fake_vector(text: str, dimension: int) -> tuple[float, ...]:
    """텍스트 SHA-256을 씨앗으로 만든 단위 벡터."""
    seed = sha256(text.encode("utf-8")).digest()
    raw: list[float] = []
    counter = 0
    while len(raw) < dimension:
        block = sha256(seed + counter.to_bytes(4, "big")).digest()
        raw += [int.from_bytes(block[i : i + 4], "big") / 0xFFFFFFFF * 2 - 1 for i in range(0, len(block), 4)]
        counter += 1
    raw = raw[:dimension]
    norm = math.sqrt(sum(v * v for v in raw)) or 1.0
    return tuple(v / norm for v in raw)


class FakeEmbeddingProvider:
    """`EmbeddingProvider` 가짜 구현.

    - `neurons`: 호출마다 알려 줄 사용량. 기본은 예상값, `None`이면 알려 주지 않는다.
    - `too_long`: 이 텍스트가 든 호출은 `input_too_long`으로 끝난다.
    - `fail_calls`: n번째(1부터) 호출을 주어진 실패로 끝낸다.
    - `wrong_dimension_calls`: n번째 호출은 차원이 하나 모자란 벡터를 돌려준다.
    """

    def __init__(
        self,
        *,
        neurons: float | str | None = ESTIMATE,
        too_long: frozenset[str] = frozenset(),
        fail_calls: Mapping[int, ProviderFailure] | None = None,
        wrong_dimension_calls: frozenset[int] = frozenset(),
    ) -> None:
        self.neurons = neurons
        self.too_long = too_long
        self.fail_calls = dict(fail_calls or {})
        self.wrong_dimension_calls = wrong_dimension_calls
        self.calls: list[tuple[str, ...]] = []

    @property
    def sent_texts(self) -> list[str]:
        return [text for call in self.calls for text in call]

    def embed_texts(self, model: ModelSpec, texts: Sequence[str]) -> ProviderBatch:
        self.calls.append(tuple(texts))
        number = len(self.calls)
        if number in self.fail_calls:
            raise self.fail_calls[number]
        if any(text in self.too_long for text in texts):
            raise ProviderFailure(ProviderFailureKind.INPUT_TOO_LONG)
        dimension = model.dimension - 1 if number in self.wrong_dimension_calls else model.dimension
        vectors = tuple(fake_vector(text, dimension) for text in texts)
        if self.neurons == ESTIMATE:
            neurons: float | None = estimated_neurons(texts, model)
        else:
            neurons = self.neurons  # type: ignore[assignment]
        return ProviderBatch(vectors, neurons)
