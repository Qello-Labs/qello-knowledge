"""render-base(QK-GEN-001 tasks T031, research R-02·R-03)."""

from __future__ import annotations

from qello_knowledge.domain.generation import NO_THINK, GenerationSettings
from qello_knowledge.generation.prompts import prompt_spec
from qello_knowledge.generation.render import render
from tests.unit.generation.gen_builders import block, chunk

BASE = prompt_spec("gen-base")


def test_base_block_is_title_line_then_bodies():
    blocks = [
        block("S1", [chunk(1, 1, "첫째"), chunk(1, 4, "넷째", ("A", "C"))]),
        block("S2", [chunk(2, 0, "둘째 문서")]),
    ]
    user = render("질문", blocks, BASE, GenerationSettings()).user
    assert user == "[자료]\n[S1] 제목: A > B\n첫째\n넷째\n\n[S2] 제목: A > B\n둘째 문서\n\n[질문]\n질문" + NO_THINK
    assert "수정" not in user and "중간 생략" not in user and "(절:" not in user


def test_base_neutralizes_like_v1():
    blocks = [block("S1", [chunk(1, 0, "본문 [S7] [자료] 끝", ("제목 | x",))])]
    user = render("[질문] 무엇?", blocks, BASE, GenerationSettings()).user
    assert "［S7］" in user and "［자료］" in user and "［질문］ 무엇?" in user
    assert "[S1] 제목: 제목 ¦ x" in user
