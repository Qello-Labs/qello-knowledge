"""서식 여유와 보호 구간이 겹쳐도 답변 분할이 끝나는지 확인한다."""

import pytest

from qello_knowledge.discord.render import LONG_LINK_OMITTED, render
from tests.unit.discord.test_bot_render_basic import bot_answer


def bot_link(length):
    start = "<https://example.invalid/"
    return start + "x" * (length - len(start) - 1) + ">"


def test_bot_1995_character_link_inside_fence_is_replaced_before_split():
    link = bot_link(1995)
    result = render(bot_answer(answer="```python\n" + link + "\n```"))
    assert LONG_LINK_OMITTED in "".join(result.messages)
    assert link not in "".join(result.messages)
    assert all(len(message) <= 2000 for message in result.messages)
    assert all(message.count("```") % 2 == 0 for message in result.messages)


def test_bot_long_language_and_source_reference_boundary_do_not_raise():
    language = "lang" * 500
    source = "[S12]"
    answer = "```" + language + "\n" + "x" * 1975 + source + "z" * 2100 + "\n```"
    reply = render(bot_answer(answer=answer))
    assert all(len(message) <= 2000 for message in reply.messages)
    assert sum(source in message for message in reply.messages) == 1


@pytest.mark.parametrize("length", [1, 1970, 1988, 1995, 2000, 2001, 3000])
@pytest.mark.parametrize("language", ["", "python", "syntax" * 30, "lang" * 500])
def test_bot_fence_link_capacity_boundaries_never_raise(length, language):
    link = bot_link(length) if length > len("<https://example.invalid/>") else "x"
    answer = "```" + language + "\n" + "앞 " + link + " 뒤" + "y" * 2100 + "\n```"
    reply = render(bot_answer(answer=answer), max_messages=2)
    assert 1 <= len(reply.messages) <= 2
    assert all(len(message) <= 2000 for message in reply.messages)


def test_bot_pipeline_delivers_answer_when_fenced_link_cannot_fit():
    from tests.unit.query.bot_scenarios import bot_run_result

    result = bot_answer(answer="```python\n" + bot_link(1995) + "\n```")
    runtime, _ = bot_run_result(result)
    assert len(runtime.fake.requests) == 1
    content = runtime.fake.requests[0].body["content"]
    assert LONG_LINK_OMITTED in content and "요청을 처리하지 못했습니다" not in content


def test_bot_many_protected_fence_boundaries_split_without_exception():
    fragments = (
        "x" * 1970,
        "[S12]",
        "\\[",
        bot_link(1988),
        bot_link(1995),
        "```" + "lang" * 500 + "\n",
        "```python\n",
        "```",
        "\n\n",
        "<https://example.invalid/x>",
    )
    for index in range(100):
        answer = "".join(
            fragments[(index * 17 + position * 23 + position * index) % len(fragments)]
            for position in range(3 + index % 6)
        )
        reply = render(bot_answer(answer=answer), max_messages=2 + index % 3)
        assert reply.messages
        assert all(len(message) <= 2000 for message in reply.messages)


@pytest.mark.parametrize(
    "answer,body_text",
    [
        ("```" + "x" * 120 + "```", "x" * 120),
        ("```python\nprint(1)\n```" + "y" * 120, "y" * 120),
        ("```" + "lang" * 40 + "\n" + "code-content" + "\n```", "code-content"),
        ("```\n" + "z" * 120 + "\n```", "z" * 120),
    ],
)
def test_bot_fence_body_text_is_preserved_without_silent_truncation(answer, body_text):
    reply = render(bot_answer(answer=answer))
    joined = "".join(reply.messages)
    assert body_text in joined
    assert not reply.body_truncated


def test_bot_unbreakable_one_line_code_reports_omission():
    reply = render(bot_answer(answer="```" + "x" * 2100 + "```"), max_messages=2)
    assert reply.body_truncated
    assert "(답변이 길어 일부를 생략했습니다.)" in "".join(reply.messages)
