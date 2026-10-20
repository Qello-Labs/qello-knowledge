"""예상 토큰·Neurons. UTF-8 바이트를 토큰으로 환산한다(research R-04, FR-023).

미리 보기, 예산 예약, 제공자가 사용량을 알려 주지 않을 때의 추정 기록이 모두 이 계산을 쓴다(FR-014).
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from qello_knowledge.domain.embedding import EstimateBasis, ModelSpec


def input_bytes(texts: Sequence[str]) -> int:
    return sum(len(text.encode("utf-8")) for text in texts)


def estimated_tokens(text: str, model: ModelSpec) -> int:
    return math.ceil(len(text.encode("utf-8")) / model.bytes_per_token_estimate)


def estimated_neurons(texts: Sequence[str], model: ModelSpec) -> float:
    tokens = sum(estimated_tokens(text, model) for text in texts)
    return tokens * model.neurons_per_million_tokens / 1_000_000


def estimate_basis(texts: Sequence[str], model: ModelSpec) -> EstimateBasis:
    return EstimateBasis(
        bytes_total=input_bytes(texts),
        bytes_per_token=model.bytes_per_token_estimate,
        neurons_per_million_tokens=model.neurons_per_million_tokens,
    )
