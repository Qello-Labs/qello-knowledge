"""설정 검사 (1)(QK-GEN-001 tasks T010, spec FR-019, research R-08, SC-009)."""

from __future__ import annotations

from qello_knowledge.domain.generation import GenerationSettings
from qello_knowledge.domain.retrieval import RetrievalSettings
from qello_knowledge.generation.settings import (
    check_settings,
    estimate_tokens,
    within_input_limit,
    worst_case_tokens,
)


def test_default_settings_pass_with_documented_total():
    gen, retrieval = GenerationSettings(), RetrievalSettings()
    # 624(시스템 2,184바이트) + 15(고정 문구 50바이트) + 2,286(2,000자 × 4바이트) + 2,000 = 4,925 → × 2.0 + 800
    assert worst_case_tokens(gen, retrieval) == 10650
    assert check_settings(gen, retrieval) == []


def test_max_overrides_are_rejected():
    retrieval = RetrievalSettings(context_budget=8000, question_max_chars=8000)
    problems = check_settings(GenerationSettings(), retrieval)
    assert len(problems) == 1 and "32768" in problems[0]


def test_factor_applies_to_inputs_only_and_output_is_added_once():
    retrieval = RetrievalSettings()
    low = worst_case_tokens(GenerationSettings(underestimate_factor=1.0), retrieval)
    assert low == 4925 + 800
    assert worst_case_tokens(GenerationSettings(max_tokens=100), retrieval) == 9850 + 100


def test_question_limit_counts_four_bytes_per_char():
    one = worst_case_tokens(GenerationSettings(underestimate_factor=1.0), RetrievalSettings(question_max_chars=7))
    zero_q = 624 + 15 + 2000 + 800
    assert one == zero_q + 8  # ceil(7 × 4 / 3.5) = 8


def test_estimate_and_runtime_limit():
    gen = GenerationSettings()
    assert estimate_tokens("가" * 7, gen) == 6  # 21바이트 ÷ 3.5
    assert within_input_limit(15984, gen)  # 2 × 15,984 + 800 = 32,768
    assert not within_input_limit(15985, gen)
