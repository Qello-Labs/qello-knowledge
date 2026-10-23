"""생성 설정 기본값·범위(QK-GEN-001 tasks T003, data-model 1절, spec FR-025)."""

from __future__ import annotations

import pytest

from qello_knowledge.domain.generation import PROMPT_NAMES, GenerationSettings


def test_defaults():
    s = GenerationSettings()
    assert (s.model_id, s.max_tokens, s.temperature, s.timeout_seconds, s.prompt_version) == (
        "@cf/qwen/qwen3-30b-a3b-fp8", 800, 0.2, 20, "gen-p1",
    )  # fmt: skip
    assert (s.bytes_per_token, s.underestimate_factor, s.context_window) == (3.5, 2.0, 32768)
    assert (s.input_price_per_m, s.output_price_per_m, s.max_attempts) == (4625, 30475, 2)
    assert s.deadline == 45
    assert GenerationSettings(timeout_seconds=30).deadline == 65
    assert PROMPT_NAMES == ("gen-p1", "gen-base")


@pytest.mark.parametrize(
    "overrides",
    [
        {"model_id": "@cf/meta/llama-3.1-8b-instruct"},
        {"max_tokens": 0},
        {"max_tokens": 4097},
        {"temperature": -0.1},
        {"temperature": 1.1},
        {"timeout_seconds": 0.5},
        {"timeout_seconds": 61},
        {"prompt_version": "gen-x"},
        {"underestimate_factor": 0.9},
        {"underestimate_factor": 4.1},
        {"input_price_per_m": 0},
        {"output_price_per_m": -1},
        {"context_window": 8192},
        {"max_attempts": 3},
        {"deadline_seconds": 44},  # 2 × 20 + 5 = 45보다 작다(독립 검토 L5)
        {"deadline_seconds": 131},
        {"timeout_seconds": 60, "deadline_seconds": 124},
    ],
)
def test_out_of_range_rejected(overrides):
    with pytest.raises(ValueError):
        GenerationSettings(**overrides)


@pytest.mark.parametrize(
    "overrides",
    [
        {"model_id": "@cf/qwen/qwen3-8b"},
        {"max_tokens": 1},
        {"max_tokens": 4096},
        {"temperature": 0},
        {"temperature": 1},
        {"timeout_seconds": 1},
        {"timeout_seconds": 60},
        {"prompt_version": "gen-base"},
        {"underestimate_factor": 1.0},
        {"underestimate_factor": 4.0},
        {"deadline_seconds": 45},
        {"deadline_seconds": 130},
    ],
)
def test_in_range_accepted(overrides):
    GenerationSettings(**overrides)


def test_timeout_60_has_deadline_that_keeps_retry():
    s = GenerationSettings(timeout_seconds=60)
    assert s.deadline == 125 and s.deadline >= 2 * s.timeout_seconds + 5
