"""인용 인식·정규화·제거와 문장 귀속(QK-GEN-001 tasks T021, spec FR-013~015, research R-04 5·6·9·11단계, SC-001)."""

from __future__ import annotations

import pytest

from qello_knowledge.domain.generation import GenerationSettings, GenerationStatus, ProviderReply
from qello_knowledge.generation.fake import ScriptedProvider
from qello_knowledge.generation.postprocess import RECOGNIZED, postprocess
from qello_knowledge.generation.prompts import prompt_spec
from qello_knowledge.generation.render import render
from qello_knowledge.generation.service import generate
from tests.unit.generation.gen_builders import deps, request, three_blocks

RENDERED = render("q", three_blocks(), prompt_spec("gen-p1"), GenerationSettings())


def _post(answer: str):
    return postprocess(answer, RENDERED)


def test_missing_id_is_removed_and_counted():
    out = _post("배포는 승인 뒤에 한다 [S9].  재시도는 3회다 [S2].")
    assert "[S9]" not in out.answer and out.removed_citations == 1
    assert out.citation_ids == ("S2",)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("[S1, S2]", "[S1][S2]"),
        ("[S1，S2]", "[S1][S2]"),
        ("[ S1 ]", "[S1]"),
        ("[S1 S2]", "[S1][S2]"),
        ("[S1][S1]", "[S1]"),
        ("[S1, S9]", "[S1]"),
    ],
)
def test_groups_are_normalized(raw, expected):
    out = _post(f"배포는 승인 뒤에 한다 {raw}.")
    assert out.answer == f"배포는 승인 뒤에 한다 {expected}."


def test_same_id_twice_in_one_sentence_is_kept_once():
    out = _post("배포는 [S1] 승인 뒤에 한다 [S1].")
    assert out.answer.count("[S1]") == 1


@pytest.mark.parametrize(
    "form",
    ["[S9,]", "[S1；S2]", "[S1/S2]", "[S1 및 S2]", "[S1, S3-S5]", "[S1–S3]", "[S0]", "[S01]", "[s1]", "(S1)", "【S1】"],
)
def test_unrecognized_forms_are_kept_and_counted(form):
    out = _post(f"배포는 승인 뒤에 한다 {form}. 재시도는 3회다 [S2].")
    assert form in out.answer
    assert out.unrecognized_citations == 1
    assert out.citation_ids == ("S2",)


@pytest.mark.parametrize("text", ["[AWS S3 버킷]", "[S3 설정 참고]"])
def test_ordinary_brackets_are_not_counted(text):
    out = _post(f"자료는 {text}에 있다 [S1].")
    assert out.unrecognized_citations == 0 and text in out.answer


def test_code_is_neither_changed_nor_counted():
    out = _post("설정은 `[S9]`와 같다 [S1].\n```\nids = [S9, S2]\n```")
    assert "`[S9]`" in out.answer and "ids = [S9, S2]" in out.answer
    assert out.removed_citations == 0 and out.unrecognized_citations == 0
    assert out.citation_ids == ("S1",)
    assert out.uncited_sentences == 0  # 코드 블록 줄은 세지 않는다


def test_citation_after_period_with_space_belongs_to_previous_sentence():
    out = _post("배포는 승인 뒤에 한다. [S1] 재시도는 3회다. [S2]")
    assert out.uncited_sentences == 0
    assert out.citation_ids == ("S1", "S2")


def test_citation_glued_after_period_splits_sentence():
    out = _post("배포는 승인 뒤에 한다.[S1] 재시도는 3회다.")
    assert out.uncited_sentences == 1  # 둘째 문장만 인용이 없다


def test_decimal_and_file_names_are_not_boundaries():
    out = _post("버전 5.5와 a.py가 바뀌었다 [S1].")
    assert out.uncited_sentences == 0


def test_no_valid_citation_marks_unsupported_answer():
    out = _post("배포는 승인 뒤에 한다.")
    assert out.unsupported_answer and out.citation_ids == () and out.uncited_sentences == 1
    assert out.fact_sentences == 1
    mixed = _post("배포는 승인 뒤에 한다 [S1]. 재시도는 3회다. 담당자는 제공된 자료만으로 확인할 수 없습니다.")
    assert (mixed.fact_sentences, mixed.uncited_sentences) == (2, 1)


def test_only_missing_ids_leave_unsupported_answer():
    result = generate(request(), deps(ScriptedProvider([ProviderReply("배포는 승인 뒤에 한다 [S9].", 1, 1)])))
    assert result.status is GenerationStatus.ANSWERED
    assert result.summary.flags.unsupported_answer and result.citations == ()


def test_citation_ids_equal_recognized_ids_outside_code():
    out = _post("재시도는 3회다 [S2]. 배포는 승인 뒤에 한다 [S1, S3]. `[S2]`")
    ids_in_answer = {i for g in RECOGNIZED.findall(out.answer.replace("`[S2]`", "")) for i in g.strip("[]").split("][")}
    assert set(out.citation_ids) == ids_in_answer == {"S1", "S2", "S3"}
    assert out.citation_ids == ("S1", "S2", "S3")
