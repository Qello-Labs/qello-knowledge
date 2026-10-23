"""생성 호출 없는 판정(QK-GEN-001 tasks T017, spec US2 1·2, FR-007·008, SC-002)."""

from __future__ import annotations

import pytest

from qello_knowledge.domain.generation import CANNOT_CONFIRM, CannotConfirmReason, GenerationStatus
from qello_knowledge.domain.retrieval import RetrievalFailure
from qello_knowledge.generation.fake import ScriptedProvider
from qello_knowledge.generation.service import generate
from tests.unit.generation.gen_builders import deps, request, retrieval


def _generate(result):
    provider = ScriptedProvider()
    out = generate(request(result=result), deps(provider))
    return out, provider


def test_no_results_answers_cannot_confirm_without_call():
    out, provider = _generate(retrieval(status="no_results"))
    assert provider.calls == []
    assert out.status is GenerationStatus.CANNOT_CONFIRM
    assert out.answer == CANNOT_CONFIRM == "제공된 자료만으로 확인할 수 없습니다."
    assert out.citations == ()
    assert out.summary.cannot_confirm_reason is CannotConfirmReason.NO_RESULTS
    assert out.summary.generation_calls == 0


def test_empty_context_answers_cannot_confirm_without_call():
    out, provider = _generate(retrieval([], status="ok"))
    assert provider.calls == []
    assert out.answer == CANNOT_CONFIRM
    assert out.summary.cannot_confirm_reason is CannotConfirmReason.EMPTY_CONTEXT


@pytest.mark.parametrize(
    "failure",
    [f for f in RetrievalFailure if f is not RetrievalFailure.OUTGOING_BLOCKED],
)
def test_retrieval_failure_is_passed_through_without_call(failure):
    out, provider = _generate(retrieval(status=failure.value))
    assert provider.calls == []
    assert out.status is GenerationStatus.RETRIEVAL_FAILED
    assert out.summary.retrieval_failure == failure.value
    assert out.answer == "" and out.citations == ()
