from qello_knowledge.discord.render import citation_line, neutralize, render
from tests.unit.discord.test_bot_render_basic import bot_answer, bot_citation


def test_bot_source_formatting_is_escaped_but_answer_markdown_survives():
    raw = "[]()*_~`|>\\<"
    escaped = "".join("\\" + c for c in raw)
    assert neutralize(raw) == escaped
    citation = bot_citation(title=raw, source_version=raw)
    line = citation_line(citation)
    assert escaped in line
    reply = render(bot_answer([citation], answer="**굵게**\n- 목록\n`코드`"))
    assert reply.messages[0].startswith("**굵게**\n- 목록\n`코드`")
    assert escaped in reply.messages[0]


def test_bot_mentions_never_enable_notifications():
    mentions = "@everyone @here <@900000000000000007> <@&900000000000000008>"
    reply = render(bot_answer([bot_citation(title=mentions)], answer=mentions))
    assert reply.allowed_mentions == {"parse": []}
    assert mentions in reply.messages[0]  # 답변 본문 서식은 유지한다.


def test_bot_source_url_cannot_close_the_link_wrapper():
    line = citation_line(bot_citation(source_url="https://example.invalid/x> @everyone"))
    assert "<https://example.invalid/x%3E%20@everyone>" in line


def test_bot_generated_date_labels_are_also_neutralized():
    class BotDate:
        def astimezone(self, zone):
            return self

        def strftime(self, pattern):
            return "[합성](날짜)"

    line = citation_line(bot_citation(source_modified_at=BotDate(), collected_at=BotDate()))
    assert line.count("\\[합성\\]\\(날짜\\)") == 2
