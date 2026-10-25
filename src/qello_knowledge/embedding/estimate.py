"""예상 토큰·Neurons. UTF-8 바이트를 토큰으로 환산한다(research R-04, FR-023).

미리 보기, 예산 예약, 제공자가 사용량을 알려 주지 않을 때의 추정 기록이 모두 `estimated_neurons`를 쓴다(FR-014).
`estimated_tokens`는 청크 나누기·묶음 나누기·입력 한도 판정용이고, 예상 Neurons는 따로 보정한 계수로 센다.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from fractions import Fraction

from qello_knowledge.domain.embedding import EstimateBasis, ModelSpec


def input_bytes(texts: Sequence[str]) -> int:
    return sum(len(text.encode("utf-8")) for text in texts)


def estimated_tokens(text: str, model: ModelSpec) -> int:
    return math.ceil(len(text.encode("utf-8")) / model.bytes_per_token_estimate)


def billed_tokens(text: str, model: ModelSpec) -> int:
    # 1.4 같은 소수는 이진 부동소수로 나누면 1400 / 1.4 = 1000.0000000000001이 되어 올림이 하나 커진다
    return math.ceil(len(text.encode("utf-8")) / Fraction(str(model.neuron_bytes_per_token)))


def estimated_neurons(texts: Sequence[str], model: ModelSpec) -> float:
    tokens = sum(billed_tokens(text, model) for text in texts)
    return tokens * model.neurons_per_million_tokens / 1_000_000


def estimate_basis(texts: Sequence[str], model: ModelSpec) -> EstimateBasis:
    return EstimateBasis(
        bytes_total=input_bytes(texts),
        bytes_per_token=model.neuron_bytes_per_token,
        neurons_per_million_tokens=model.neurons_per_million_tokens,
    )
