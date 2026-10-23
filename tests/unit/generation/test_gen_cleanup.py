"""추론 블록·코드 펜스·출처 줄·URL 정리(QK-GEN-001 tasks T022, research R-04 1~4단계, spec FR-014, SC-001·005)."""

from __future__ import annotations

import pytest

from qello_knowledge.domain.generation import GenerationSettings
from qello_knowledge.generation.postprocess import postprocess
from qello_knowledge.generation.prompts import prompt_spec
from qello_knowledge.generation.render import render
from tests.unit.generation.gen_builders import block, chunk

EXCERPT = (
    "주소는 https://wiki.example.test/deploy 에 있다. "
    "설계는 https://github.example.test/o/r/blob/main/docs/설계.md 이다. "
    "괄호 경로는 https://wiki.example.test/Foo_(bar) 이다."
)
RENDERED = render("q", [block("S1", [chunk(1, 0, EXCERPT)])], prompt_spec("gen-p1"), GenerationSettings())


def _post(answer: str):
    return postprocess(answer, RENDERED)


@pytest.mark.parametrize(
    ("answer", "detected"),
    [
        ("<think>생각</think>배포는 승인 뒤에 한다 [S1].", True),
        ("<think>\n\n</think>\n\n배포는 승인 뒤에 한다 [S1].", False),
        ("<think>a</think>배포는 [S1].<think>b</think>", True),
        ("배포는 승인 뒤에 한다 [S1].<think>남은 생각", True),
        ("생각 조각</think>배포는 승인 뒤에 한다 [S1].", True),
    ],
)
def test_thinking_is_removed(answer, detected):
    out = _post(answer)
    assert "think" not in out.answer and "생각" not in out.answer
    assert out.thinking_detected is detected


def test_unclosed_code_fence_runs_to_end():
    out = _post("설정은 다음과 같다 [S1].\n```\nretry: 3\n[S9]")
    assert out.answer.endswith("```\nretry: 3\n[S9]") and out.removed_citations == 0


@pytest.mark.parametrize("head", ["출처:", "참고：", "Sources:", "Source:", "References:"])
def test_source_list_lines_are_removed(head):
    out = _post(
        f"배포는 승인 뒤에 한다 [S1].\n{head}\n- [S1] docs/a.md\n1. https://wiki.example.test/deploy\n끝 문장이다 [S1]."
    )
    assert head not in out.answer and "docs/a.md" not in out.answer
    assert out.removed_source_lines == 3
    assert "끝 문장이다 [S1]." in out.answer


def test_sentence_starting_with_reference_word_is_kept():
    out = _post("참고로 배포는 승인 뒤에 한다 [S1].")
    assert out.answer == "참고로 배포는 승인 뒤에 한다 [S1]." and out.removed_source_lines == 0


@pytest.mark.parametrize(
    "answer",
    [
        "주소는 https://wiki.example.test/deploy 이다 [S1].",
        "주소는 https://wiki.example.test/deploy에 있다 [S1].",
        "주소는 https://wiki.example.test/deploy. 확인하라 [S1].",
        "설계는 https://github.example.test/o/r/blob/main/docs/설계.md 이다 [S1].",
        "경로는 https://wiki.example.test/Foo_(bar) 이다 [S1].",
    ],
)
def test_urls_in_excerpt_are_kept(answer):
    out = _post(answer)
    assert out.answer == answer and out.removed_urls == 0


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("문서는 https://docs.example.test 에 있다 [S1].", "문서는 에 있다 [S1]."),
        ("주소는 https://wiki.example.test 이다 [S1].", "주소는 이다 [S1]."),
        ("설계는 https://github.example.test/o/r/blob/main/docs/가짜.md 이다 [S1].", "설계는 이다 [S1]."),
        ("경로는 https://wiki.example.test/Foo_(baz) 이다 [S1].", "경로는 ) 이다 [S1]."),
    ],
)
def test_urls_not_in_excerpt_are_removed(answer, expected):
    out = _post(answer)
    assert out.answer == expected and out.removed_urls == 1


def test_url_inside_code_is_untouched():
    out = _post("예시는 `https://other.example.test/x` 이다 [S1].")
    assert "`https://other.example.test/x`" in out.answer and out.removed_urls == 0
