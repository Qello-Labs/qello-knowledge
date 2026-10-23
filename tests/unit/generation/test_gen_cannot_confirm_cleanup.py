"""후처리 1~6단계를 거치는 확인 불가·빈 결과(QK-GEN-001 tasks T024, research R-04 7·8단계, 독립 검토 M1)."""

from __future__ import annotations

import pytest

from qello_knowledge.domain.generation import (
    CANNOT_CONFIRM,
    CannotConfirmReason,
    GenerationFailure,
    GenerationStatus,
    ProviderReply,
)
from qello_knowledge.generation.fake import ScriptedProvider
from qello_knowledge.generation.service import generate
from tests.unit.generation.gen_builders import deps, request


def _generate(answer: str):
    return generate(request(), deps(ScriptedProvider([ProviderReply(answer, 10, 5)])))


@pytest.mark.parametrize(
    "answer", ["제공된 자료만으로 확인할 수 없습니다 (S1).", "제공된 자료만으로 확인할 수 없습니다 [S1, S9]."]
)
def test_cannot_confirm_with_citation_like_marks(answer):
    out = _generate(answer)
    assert out.status is GenerationStatus.CANNOT_CONFIRM
    assert out.summary.cannot_confirm_reason is CannotConfirmReason.MODEL_CANNOT_CONFIRM
    assert out.answer == CANNOT_CONFIRM


@pytest.mark.parametrize(
    "answer",
    ["출처: [S1]", "https://elsewhere.example.test/x", "<think>생각만</think>", "<think>끝나지 않은 생각", "[S1]"],
)
def test_nothing_left_is_bad_response_not_cannot_confirm(answer):
    out = _generate(answer)
    assert out.status is GenerationStatus.GENERATION_FAILED
    assert out.summary.failure is GenerationFailure.BAD_RESPONSE
