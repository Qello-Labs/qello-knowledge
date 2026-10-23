"""생성 도메인 타입 불변식(QK-GEN-001 tasks T004, data-model 2~5절)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from qello_knowledge.domain.generation import (
    CannotConfirmReason,
    Citation,
    GenerationFailure,
    GenerationFlags,
    GenerationRequest,
    GenerationResult,
    GenerationStatus,
    GenerationSummary,
    GenerationUsage,
    ProviderReply,
    RenderedInput,
)
from qello_knowledge.domain.retrieval import RetrievalResult, RetrievalSummary

SECRET_Q = "질문-표식-7f3a"
SECRET_A = "답변-표식-91bc"
NOW = datetime(2026, 10, 23, tzinfo=UTC)


def _citation(source_id: str = "S1") -> Citation:
    return Citation(source_id, "제목", "https://example.test/a", "v1", None, NOW)


def test_enum_values():
    assert [s.value for s in GenerationStatus] == [
        "answered", "cannot_confirm", "retrieval_failed", "outgoing_blocked", "generation_failed",
    ]  # fmt: skip
    assert [f.value for f in GenerationFailure] == [
        "transient", "timeout", "provider_quota", "auth_config", "bad_response", "input_too_long",
    ]  # fmt: skip
    assert [r.value for r in CannotConfirmReason] == [
        "no_results", "empty_context", "all_blocks_blocked", "model_cannot_confirm", "model_unconfirmable_parts",
    ]  # fmt: skip


def test_raw_text_not_in_repr():
    request = GenerationRequest(SECRET_Q, RetrievalResult(status="no_results"))
    reply = ProviderReply(SECRET_A)
    rendered = RenderedInput(SECRET_Q, SECRET_Q, ())
    result = GenerationResult(
        GenerationStatus.ANSWERED,
        SECRET_A,
        (_citation(),),
        GenerationSummary(GenerationStatus.ANSWERED),
        RetrievalSummary(),
    )
    for value in (request, reply, rendered, result):
        assert SECRET_Q not in repr(value) and SECRET_A not in repr(value)


def test_cannot_confirm_has_no_citations():
    with pytest.raises(ValueError):
        GenerationResult(
            GenerationStatus.CANNOT_CONFIRM,
            "x",
            (_citation(),),
            GenerationSummary(GenerationStatus.CANNOT_CONFIRM),
            RetrievalSummary(),
        )


def test_unsupported_answer_flag_requires_answered_without_citations():
    flags = GenerationFlags(unsupported_answer=True)
    GenerationResult(
        GenerationStatus.ANSWERED,
        "x",
        (),
        GenerationSummary(GenerationStatus.ANSWERED, flags=flags),
        RetrievalSummary(),
    )
    with pytest.raises(ValueError):
        GenerationResult(
            GenerationStatus.ANSWERED,
            "x",
            (_citation(),),
            GenerationSummary(GenerationStatus.ANSWERED, flags=flags),
            RetrievalSummary(),
        )
    with pytest.raises(ValueError):
        GenerationResult(
            GenerationStatus.GENERATION_FAILED,
            "",
            (),
            GenerationSummary(GenerationStatus.GENERATION_FAILED, flags=flags),
            RetrievalSummary(),
        )


def test_duplicate_citation_rejected():
    with pytest.raises(ValueError):
        GenerationResult(
            GenerationStatus.ANSWERED,
            "x",
            (_citation(), _citation()),
            GenerationSummary(GenerationStatus.ANSWERED),
            RetrievalSummary(),
        )


@pytest.mark.parametrize(
    "overrides",
    [{"attempt": 0}, {"attempt": 3}, {"outcome": "weird"}, {"neurons": -1.0}, {"estimated_input_tokens": -1}],
)
def test_usage_validation(overrides):
    values = {
        "run_id": "answer-1", "model_id": "m", "prompt_version": "gen-p1-x", "attempt": 1, "input_tokens": 1,
        "output_tokens": 1, "estimated_input_tokens": 1, "neurons": 0.1, "measured": True, "outcome": "ok",
    }  # fmt: skip
    values.update(overrides)
    with pytest.raises(ValueError):
        GenerationUsage(**values)


def test_usage_accepts_failure_outcomes():
    for failure in GenerationFailure:
        GenerationUsage("r", "m", "p", 2, None, None, 0, 0.0, False, failure.value)
