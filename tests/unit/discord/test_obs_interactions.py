"""새 상호작용 해석. 기존 ask 결과 유지."""

import json

import pytest

from qello_knowledge.discord.interactions import parse
from qello_knowledge.domain.discord import InteractionKind
from tests.unit.query.obs_builders import QUESTIONER, RUN, component, sources


def test_component_and_sources():
    item = parse(component("down"))
    assert item.kind is InteractionKind.COMPONENT
    assert (item.user_id, item.component_action, item.component_run_id) == (QUESTIONER, "down", RUN)
    assert parse(component(custom_id="bad")).component_action is None
    item = parse(sources())
    assert item.kind is InteractionKind.COMMAND and item.command == "sources"


@pytest.mark.parametrize("change", ["member", "guild_id"])
def test_missing_user(change):
    payload = json.loads(component())
    payload.pop(change)
    assert parse(json.dumps(payload).encode()).user_id is None
