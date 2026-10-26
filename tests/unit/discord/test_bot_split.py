import pytest

from qello_knowledge.discord.render import render
from tests.unit.discord.test_bot_render_basic import bot_answer, bot_citation

BOT_OMITTED = "(답변이 길어 일부를 생략했습니다.)"


@pytest.mark.parametrize(
    "body,first",
    [
        ("p" * 1100 + "\n\n" + "s" * 800 + ". " + "z" * 300, "p" * 1100 + "\n\n"),
        ("s" * 1400 + ". " + "z" * 700, "s" * 1400 + ". "),
        ("w" * 1200 + " " + "z" * 900, "w" * 1200 + " "),
        ("x" * 4000, "x" * 2000),
    ],
)
def test_bot_split_prefers_paragraph_sentence_then_space(body, first):
    reply = render(bot_answer(answer=body))
    assert reply.messages[0] == first
    assert "".join(reply.messages) == body and not reply.body_truncated


@pytest.mark.parametrize(
    "token",
    [
        "[S12]",
        "[표제](https://example.invalid/a(b))",
        "<https://example.invalid/source>",
        "https://example.invalid/source",
        r"\*",
    ],
)
def test_bot_protected_token_is_never_cut(token):
    body = "x" * 1999 + token + " tail"
    reply = render(bot_answer(answer=body))
    assert sum(token in m for m in reply.messages) == 1
    assert "".join(reply.messages) == body


def test_bot_long_body_link_is_replaced_without_partial_url():
    body = "앞 <https://example.invalid/" + "x" * 2200 + "> 뒤"
    reply = render(bot_answer(answer=body))
    assert reply.messages == ("앞 (긴 링크 생략) 뒤",)


def test_bot_code_fragments_close_and_reopen_the_same_language():
    reply = render(bot_answer(answer="```python\n" + "a" * 5000 + "\n```"))
    assert len(reply.messages) == 3
    assert all(m.startswith("```python\n") and m.endswith("```") and m.count("```") == 2 for m in reply.messages)
    assert sum(m.count("a") for m in reply.messages) == 5000
    assert all(len(m) <= 2000 for m in reply.messages) and not reply.body_truncated


def test_bot_truncated_code_is_closed_before_omission_notice():
    reply = render(bot_answer(answer="```js\n" + "x" * 12000 + "\n```"))
    assert reply.body_truncated and len(reply.messages) == 4
    assert reply.messages[-1].endswith("```\n\n" + BOT_OMITTED)
    assert all(m.count("```") == 2 and len(m) <= 2000 for m in reply.messages)


def test_bot_maximum_sources_keep_all_items_after_truncated_body():
    url = "https://example.invalid/" + "x" * (300 - len("https://example.invalid/"))
    citations = [bot_citation(f"S{i}", title="*" * 81, source_version="*" * 12, source_url=url) for i in range(1, 9)]
    result = bot_answer(citations, answer="본문" * 8000)
    reply = render(result, private=True)
    assert len(reply.messages) <= 4 and all(len(m) <= 2000 for m in reply.messages)
    assert reply.body_truncated and reply.ephemeral and BOT_OMITTED in reply.messages[0]
    assert "자료 기준" not in reply.messages[0]
    sources = "\n".join(reply.messages[1:])
    assert all(sources.count(f"[S{i}]") == 1 for i in range(1, 9))
    assert [sources.index(f"[S{i}]") for i in range(1, 9)] == sorted(sources.index(f"[S{i}]") for i in range(1, 9))
    assert reply == render(result, private=True)


def test_bot_truncation_does_not_cut_a_final_reference_or_link():
    # 합성 값. 비밀값 이름 규칙 오탐을 피하려고 이어 붙인다.
    token = "[참" + "조](https://example.invalid/source)"
    result = bot_answer(answer="x" * 3965 + token + "y" * 1000)
    reply = render(result, max_messages=2)
    assert reply.body_truncated and all(len(m) <= 2000 for m in reply.messages)
    assert token not in "".join(reply.messages)  # 마지막 링크는 통째로 생략한다.
    assert "https:" not in "".join(reply.messages)


@pytest.mark.parametrize("private", [False, True])
def test_bot_split_delivery_preserves_followup_visibility(private):
    from tests.unit.query.bot_scenarios import bot_result, bot_run_result

    runtime, _ = bot_run_result(bot_result(answer="x" * 4500), private=private)
    assert len(runtime.fake.requests) == 3
    for request in runtime.fake.requests[1:]:
        assert request.method == "POST"
        assert request.body.get("flags", 0) == (64 if private else 0)
        assert request.body["allowed_mentions"] == {"parse": []}
