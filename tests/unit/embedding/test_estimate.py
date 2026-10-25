"""예상 토큰·Neurons와 계산 근거(FR-023, research R-04)."""

import math

from qello_knowledge.domain.embedding import MODELS, EstimateBasis
from qello_knowledge.embedding.estimate import estimate_basis, estimated_neurons, estimated_tokens

MODEL = MODELS["@cf/baai/bge-m3"]


def test_tokens_are_utf8_bytes_over_three_and_a_half() -> None:
    assert estimated_tokens("", MODEL) == 0
    assert estimated_tokens("abcdefg", MODEL) == 2  # 7바이트
    assert estimated_tokens("한국어", MODEL) == math.ceil(9 / 3.5)  # 한 글자 3바이트


def test_neurons_follow_price_table_with_their_own_bytes_per_token() -> None:
    texts = ["a" * 1400, "가" * 1000]  # 1000토큰 + ceil(3000 / 1.4) = 2143토큰(SCRUM-114, research R-04 보정)
    assert estimated_neurons(texts, MODEL) == (1000 + 2143) * 1075 / 1_000_000


def test_neuron_estimate_does_not_change_chunk_token_estimate() -> None:
    # 청크 나누기·묶음 나누기는 3.5를 그대로 쓴다. 바꾸면 청킹 판수 재료 밖에서 청크 경계가 바뀐다(AGENTS.md 3.3).
    assert MODEL.bytes_per_token_estimate == 3.5
    assert MODEL.neuron_bytes_per_token == 1.4


def test_calibration_keeps_first_full_index_within_sc005() -> None:
    # 2026-10-21 로컬·2026-10-23 운영 첫 색인: 입력 1,199,214바이트, 제공자 Neurons 894.50(research R-04 보정 기록).
    estimate = 1_199_214 / MODEL.neuron_bytes_per_token * MODEL.neurons_per_million_tokens / 1_000_000
    assert abs(estimate - 894.50) / 894.50 <= 0.20


def test_basis_reports_bytes_and_rates() -> None:
    assert estimate_basis(["ab", "가"], MODEL) == EstimateBasis(5, 1.4, 1075)
