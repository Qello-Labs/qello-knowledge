import itertools

import pytest

from qello_knowledge.discord.render import SOURCE_ITEM_MAX_CHARS, citation_line, source_capacity, source_item_max_chars
from tests.unit.config.test_bot_cross_check import bot_report
from tests.unit.discord.test_bot_render_basic import bot_citation


def test_bot_item_bound_matches_actual_worst_rendered_item():
    url = "https://example.invalid/" + "x" * (300 - len("https://example.invalid/"))
    item = bot_citation("S20", title="*" * 81, source_version="*" * 12, source_url=url)
    assert len(citation_line(item) + "\n") == SOURCE_ITEM_MAX_CHARS == source_item_max_chars(80, 300)
    assert source_capacity(80, 300, expand_top=8) == (3, 3)
    assert bot_report().ok


@pytest.mark.parametrize("title,link,messages", list(itertools.product((20, 80, 200), (50, 300, 1000), (2, 4, 10))))
def test_bot_capacity_rule_rejects_source_lists_that_leave_no_body_message(title, link, messages):
    per_message, required = source_capacity(title, link, expand_top=8)
    report = bot_report(
        QK_DISCORD_TITLE_MAX_CHARS=str(title),
        QK_DISCORD_LINK_MAX_CHARS=str(link),
        QK_DISCORD_MAX_MESSAGES=str(messages),
        QK_QUERY_CALL_LIMIT="50",
    )
    expected = per_message >= 1 and required <= messages - 1
    assert report.ok is expected
    if not expected:
        assert any(c.name == "discord_source_capacity" and not c.ok for c in report.checks)
