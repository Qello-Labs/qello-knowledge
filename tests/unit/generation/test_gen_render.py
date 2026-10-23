"""render-v1 렌더링(QK-GEN-001 tasks T012, research R-03, spec FR-004·006, SC-005·010)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from qello_knowledge.domain.generation import NO_THINK, GenerationSettings
from qello_knowledge.generation.prompts import prompt_spec
from qello_knowledge.generation.render import render
from tests.unit.generation.gen_builders import block, chunk, three_blocks

GOLDEN = Path(__file__).parent / "golden"
SETTINGS = GenerationSettings()
P1 = prompt_spec("gen-p1")


def _user(blocks, question="질문") -> str:
    return render(question, blocks, P1, SETTINGS).user


def test_header_uses_heading_path_and_korean_date():
    text = _user([block("S1", [chunk(1, 0, "본문")])])
    assert "[S1] A > B | 수정 2026-10-10\n본문" in text  # UTC 10-09 16:00 → 한국 10-10


def test_unknown_modified_date():
    text = _user([block("S1", [chunk(1, 0, "본문")], modified=None)])
    assert "[S1] A > B | 수정 미상\n본문" in text


def test_naive_datetime_is_treated_as_utc():
    text = _user([block("S1", [chunk(1, 0, "본문")], modified=datetime(2026, 10, 9, 23, 30))])
    assert "| 수정 2026-10-10" in text


@pytest.mark.parametrize(
    ("heading", "path", "title"),
    [((), "docs/a.md", "docs/a.md"), ((), None, "제목 없음"), (("문서", "절"), "docs/a.md", "문서 > 절")],
)
def test_title_fallbacks(heading, path, title):
    text = _user([block("S1", [chunk(1, 0, "본문", heading, path=path)])])
    assert f"[S1] {title} | 수정" in text


def test_gap_and_section_lines():
    chunks = [chunk(1, 1, "첫째", ("A", "B")), chunk(1, 2, "둘째", ("A", "B")), chunk(1, 5, "다섯째", ("A", "C"))]
    text = _user([block("S1", chunks)])
    assert "첫째\n둘째\n…(중간 생략)…\n(절: A > C)\n다섯째" in text


def test_blocks_separated_by_one_blank_line_in_rank_order():
    text = _user(three_blocks())
    assert text.index("[S1]") < text.index("[S2]") < text.index("[S3]")
    assert "배포는 승인 뒤에 한다.\n\n[S2]" in text


def test_user_message_is_template_and_ends_with_no_think():
    rendered = render("배포 절차?", three_blocks(), P1, SETTINGS)
    assert rendered.user.startswith("[자료 시작]\n[S1]")
    assert rendered.user.endswith("[자료 끝]\n\n[질문]\n배포 절차?" + NO_THINK)
    assert rendered.user.count(NO_THINK) == 1
    assert rendered.system == P1.system


def test_same_input_same_bytes():
    assert render("q", three_blocks(), P1, SETTINGS) == render("q", three_blocks(), P1, SETTINGS)


def test_context_text_with_template_slots_is_not_refilled():
    text = _user([block("S1", [chunk(1, 0, "{question} {context}")])], question="Q")
    assert "{question} {context}" in text and text.endswith("Q" + NO_THINK)


def _golden_cases():
    return {
        "render-v1-three": (three_blocks(), "배포 절차가 뭐야?"),
        "render-v1-gaps": (
            [block("S1", [chunk(1, 1, "첫째"), chunk(1, 2, "둘째"), chunk(1, 5, "다섯째", ("A", "C"))])],
            "절이 바뀌는 문서",
        ),
        "render-v1-fallback": (
            [
                block("S1", [chunk(1, 0, "머리말", (), path="docs/readme.md")], modified=None),
                block("S2", [chunk(2, 0, "제목 없는 본문", ())]),
            ],
            "제목이 없을 때",
        ),
    }


@pytest.mark.parametrize("name", sorted(_golden_cases()))
def test_golden_render(name):
    blocks, question = _golden_cases()[name]
    expected = (GOLDEN / f"{name}.txt").read_text(encoding="utf-8").replace("\r\n", "\n")
    assert render(question, blocks, P1, SETTINGS).user == expected


def test_rendered_block_keeps_original_values():
    rendered = render("q", three_blocks(), P1, SETTINGS)
    first = rendered.blocks[0]
    assert first.raw_title == "A > B" and first.block.source_url.endswith("doc1.md")
    assert rendered.estimated_input_tokens > 0
    assert rendered.blocks[0].block.collected_at == datetime(2026, 10, 21, 3, 0, tzinfo=UTC)
