import json

import pytest

from qello_knowledge.discord.interactions import deferred, notice, parse, pong
from qello_knowledge.domain.discord import ChannelKind, InteractionKind
from tests.unit.discord.bot_builders import CHANNEL, GUILD, ROLE, TOKEN, ask, component, other_command, ping


def test_bot_ping_and_first_responses():
    assert parse(ping()).kind is InteractionKind.PING
    assert pong().to_dict() == {"type": 1}
    assert notice("synthetic notice").to_dict() == {
        "type": 4,
        "data": {"content": "synthetic notice", "flags": 64, "allowed_mentions": {"parse": []}},
    }
    assert deferred(False).to_dict() == {"type": 5}
    assert deferred(True).to_dict() == {"type": 5, "data": {"flags": 64}}
    assert deferred(False, run_id="run").run_id == "run"


@pytest.mark.parametrize(
    "private,expected", [(None, False), (False, False), (True, True), ("false", True), (0, True), (1, True)]
)
def test_bot_ask_private(private, expected):
    item = parse(ask("synthetic question", private=private, roles=(ROLE,)))
    assert item.kind is InteractionKind.COMMAND
    assert item.question == "synthetic question" and item.command == "ask"
    assert item.private is expected and item.member_roles == (ROLE,)
    assert item.guild_id == GUILD and item.channel_id == CHANNEL and item.token == TOKEN


@pytest.mark.parametrize(
    "channel_type,expected",
    [
        (0, ChannelKind.TEXT),
        (5, ChannelKind.TEXT),
        (10, ChannelKind.THREAD),
        (11, ChannelKind.THREAD),
        (12, ChannelKind.THREAD),
        (15, ChannelKind.OTHER),
    ],
)
def test_bot_channel_kinds(channel_type, expected):
    assert parse(ask("q", channel_type=channel_type)).channel_kind is expected
    assert parse(ask("q", guild=None, channel_type=channel_type)).channel_kind is ChannelKind.DM


@pytest.mark.parametrize(
    "body", [b"x" * (65536 + 1), b"{", b"[]", b"null", b"\xff", b'{"type":2}', component(), other_command("other")]
)
def test_bot_invalid_input_is_other(body):
    assert parse(body).kind is InteractionKind.OTHER


@pytest.mark.parametrize("field", ["id", "token", "data", "channel_id"])
def test_bot_missing_fields(field):
    payload = json.loads(ask("q"))
    del payload[field]
    assert parse(json.dumps(payload).encode()).kind is InteractionKind.OTHER


@pytest.mark.parametrize(
    "change",
    [
        {"data": []},
        {"member": []},
        {"channel": []},
        {"id": 1},
        {"token": None},
        {"data": {"name": "ask", "options": [None]}},
        {"data": {"name": "ask", "options": [{"name": "질문", "value": 4}]}},
    ],
)
def test_bot_malformed_nested_fields(change):
    payload = {**json.loads(ask("q")), **change}
    assert parse(json.dumps(payload).encode()).kind is InteractionKind.OTHER


def test_bot_user_fields_are_ignored_and_body_boundary():
    payload = json.loads(ask("q"))
    payload["member"]["user"] = {"id": "synthetic-user", "username": "synthetic-name"}
    payload["user"] = payload["member"]["user"]
    item = parse(json.dumps(payload).encode())
    assert "synthetic-user" not in repr(item) and "synthetic-name" not in repr(item)
    assert not hasattr(item, "user_id") and not hasattr(item, "username")
    body = ask("q")
    assert parse(body + b" " * (65536 - len(body))).kind is InteractionKind.COMMAND
