"""버튼 값과 표시 계약."""

import pytest

from qello_knowledge.discord.components import (
    consent_buttons,
    consent_text,
    custom_id,
    feedback_buttons,
    parse_custom_id,
)
from tests.unit.query.obs_builders import RUN


@pytest.mark.parametrize("action", ["up", "down", "keep", "skip"])
def test_roundtrip(action):
    value = custom_id(action, RUN)
    assert len(value) <= 35 and parse_custom_id(value) == (action, RUN)


@pytest.mark.parametrize("value", ["qk2:up:" + RUN, "qk1:bad:" + RUN, "qk1:up:bad", "x" * 101, None])
def test_bad_value(value):
    assert parse_custom_id(value) is None


def test_buttons_and_consent():
    buttons = feedback_buttons(RUN)
    assert len(buttons) == 1 and buttons[0]["type"] == 1
    assert [(b["label"], b["style"]) for b in buttons[0]["components"]] == [("👍", 2), ("👎", 2)]
    assert [(b["label"], b["style"]) for b in consent_buttons(RUN)[0]["components"]] == [
        ("저장 동의", 1),
        ("저장 안 함", 2),
    ]
    text = consent_text("2026-12-31")
    assert all(s in text for s in ["저장하는 것", "보관 기간", "보는 사람", "지우기", "2026-12-31"])
