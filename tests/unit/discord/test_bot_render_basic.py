from dataclasses import replace
from datetime import UTC, datetime

from qello_knowledge.discord.render import render
from qello_knowledge.domain.generation import Citation, GenerationResult, GenerationStatus, GenerationSummary
from qello_knowledge.domain.retrieval import RetrievalSummary


def bot_answer(citations=(), answer="합성 답변 [S9]."):
    return GenerationResult(
        GenerationStatus.ANSWERED,
        answer,
        tuple(citations),
        GenerationSummary(GenerationStatus.ANSWERED),
        RetrievalSummary(),
    )


def bot_citation(source_id="S1", **changes):
    item = Citation(
        source_id,
        "합성 제목",
        "https://example.invalid/doc",
        "a" * 40,
        datetime(2026, 10, 19, 16, tzinfo=UTC),
        datetime(2026, 10, 24, 0, 30, tzinfo=UTC),
    )
    return replace(item, **changes)


def test_bot_basic_render_exact_source_order_and_kst():
    result = bot_answer(
        [bot_citation(), bot_citation("S2", source_version="release-123456789", source_modified_at=None)]
    )
    reply = render(result, private=True)
    text = "\n".join(reply.messages)
    assert text.startswith(result.answer + "\n\n자료 기준: 색인된 문서\n")
    assert (
        "[S1] 합성 제목 · <https://example.invalid/doc> · 버전 aaaaaaa · 수정 2026-10-20 · 수집 2026-10-24 09:30 KST"
        in text
    )
    assert "버전 release-1234 · 수정 미상" in text
    assert text.index("[S1]") < text.index("[S2]")
    assert "[S9] 합성 제목" not in text
    assert reply.ephemeral and all(len(m) <= 2000 for m in reply.messages)
    assert reply == render(result, private=True)


def test_bot_title_and_link_limits_without_cutting_url():
    result = bot_answer(
        [
            bot_citation(title="제" * 81, source_url="https://example.invalid/" + "x" * 300),
            bot_citation("S2", source_url=""),
        ]
    )
    text = "\n".join(render(result).messages)
    assert "제" * 80 + "…" in text and "제" * 81 not in text
    assert "링크 생략(길이 초과)" in text and "링크 없음" in text
    assert "https://example.invalid/" not in text


def test_bot_basic_render_long_result_keeps_each_message_bounded():
    result = bot_answer(
        [bot_citation(f"S{i}", title="a" * 80, source_url="https://example.invalid/" + "x" * 270) for i in range(1, 9)]
    )
    reply = render(result)
    assert all(len(m) <= 2000 for m in reply.messages)
    assert all(f"[S{i}]" in "\n".join(reply.messages) for i in range(1, 9))
