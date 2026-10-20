"""예상 토큰·Neurons와 계산 근거(FR-023, research R-04)."""

import math

from qello_knowledge.domain.embedding import MODELS, EstimateBasis
from qello_knowledge.embedding.estimate import estimate_basis, estimated_neurons, estimated_tokens

MODEL = MODELS["@cf/baai/bge-m3"]


def test_tokens_are_utf8_bytes_over_three_and_a_half() -> None:
    assert estimated_tokens("", MODEL) == 0
    assert estimated_tokens("abcdefg", MODEL) == 2  # 7바이트
    assert estimated_tokens("한국어", MODEL) == math.ceil(9 / 3.5)  # 한 글자 3바이트


def test_neurons_follow_price_table() -> None:
    texts = ["a" * 3500, "가" * 1000]  # 1000토큰 + ceil(3000 / 3.5) = 858토큰
    assert estimated_neurons(texts, MODEL) == (1000 + 858) * 1075 / 1_000_000


def test_basis_reports_bytes_and_rates() -> None:
    assert estimate_basis(["ab", "가"], MODEL) == EstimateBasis(5, 3.5, 1075)
