"""모델 출력의 확인 불가 판정(QK-GEN-001 tasks T018, spec US2 3~5, FR-009, research R-04 7·8단계)."""

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
    "answer",
    [
        "제공된 자료만으로 확인할 수 없습니다.",
        "  제공된 자료만으로 확인할 수 없습니다.  ",
        "'제공된 자료만으로 확인할 수 없습니다.'",
        "“제공된 자료만으로 확인할 수 없습니다.”",
        "제공된 자료만으로 확인할 수 없습니다 [S1].",
        "제공된 자료만으로 확인할 수 없습니다",
        "제공된 자료만으로 확인할 수 없습니다.\n제공된 자료만으로 확인할 수 없습니다.",
    ],
)
def test_model_cannot_confirm(answer):
    out = _generate(answer)
    assert out.status is GenerationStatus.CANNOT_CONFIRM
    assert out.summary.cannot_confirm_reason is CannotConfirmReason.MODEL_CANNOT_CONFIRM
    assert out.answer == CANNOT_CONFIRM
    assert out.citations == ()


@pytest.mark.parametrize(
    "answer",
    [
        "배포 일정은 제공된 자료만으로 확인할 수 없습니다. 담당자는 제공된 자료만으로 확인할 수 없습니다.",
        "제공된 자료만으로 확인할 수 없습니다. 현재 상태는 원본에서 확인해야 합니다.",
        # 2026-10-23 사용자 결정: spec FR-009 (나) 그대로. 유효 인용이 있는 사실 문장도 확인 불가가 된다
        # (research R-04 남는 위험)
        "재시도는 3회이며 나머지는 제공된 자료만으로 확인할 수 없습니다 [S1].",
    ],
)
def test_unconfirmable_parts_only(answer):
    out = _generate(answer)
    assert out.status is GenerationStatus.CANNOT_CONFIRM
    assert out.summary.cannot_confirm_reason is CannotConfirmReason.MODEL_UNCONFIRMABLE_PARTS
    assert out.citations == ()
    assert "[S" not in out.answer
    assert out.answer.startswith(answer.split(" [S")[0].split(".")[0])


def test_fact_with_unconfirmable_part_is_answered():
    out = _generate("재시도는 3회다 [S2]. 담당자는 제공된 자료만으로 확인할 수 없습니다.")
    assert out.status is GenerationStatus.ANSWERED
    assert [c.source_id for c in out.citations] == ["S2"]
    assert out.summary.uncited_sentences == 0


@pytest.mark.parametrize("answer", ["", "   ", "\n\n"])
def test_empty_output_is_bad_response(answer):
    out = _generate(answer)
    assert out.status is GenerationStatus.GENERATION_FAILED
    assert out.summary.failure is GenerationFailure.BAD_RESPONSE
    assert out.answer == ""
