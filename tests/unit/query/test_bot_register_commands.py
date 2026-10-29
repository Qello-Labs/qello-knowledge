import json
from pathlib import Path

import pytest

from qello_knowledge.adapters.discord.webhook import DiscordWebhook
from qello_knowledge.config.loader import load
from qello_knowledge.config.registry import Entrypoint
from qello_knowledge.domain.retrieval import RetrievalSettings
from qello_knowledge.query import server
from tests.unit.discord.bot_builders import FakeDiscord
from tests.unit.fakes import valid_environ


def bot_registration(monkeypatch, *, changes=None, script=()):
    source = {**valid_environ(), **(changes or {})}
    fake = FakeDiscord(script)
    loads = []

    def bot_load(entrypoint, *, env_file):
        loads.append((entrypoint, env_file))
        return load(entrypoint, environ=source, env_file=None)

    monkeypatch.setattr(server, "load", bot_load)
    monkeypatch.setattr(server, "DiscordWebhook", lambda app: DiscordWebhook(app, transport=fake), raising=False)
    return source, fake, loads


def bot_expected_commands():
    return [
        {
            "name": "ask",
            "type": 1,
            "description": "팀 자료에서 찾아 출처와 함께 답합니다",
            "contexts": [0],
            "options": [
                {
                    "type": 3,
                    "name": "질문",
                    "description": "물어볼 내용",
                    "required": True,
                    "min_length": 1,
                    "max_length": RetrievalSettings().question_max_chars,
                },
                {"type": 5, "name": "나만_보기", "description": "켜면 답변을 나만 봅니다", "required": False},
            ],
        },
        {"name": "sources", "type": 1, "description": "봇이 검색하는 자료와 기준 시각을 봅니다", "contexts": [0]},
    ]


def test_bot_registration_dry_run_without_token_prints_only_contract_json(monkeypatch, capsys):
    _, fake, loads = bot_registration(monkeypatch, changes={"DISCORD_BOT_TOKEN": ""})
    assert server.main(["register-commands", "--env-file", "settings.conf", "--dry-run"]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == bot_expected_commands() and captured.err == ""
    assert loads == [(Entrypoint.REGISTER, Path("settings.conf"))] and not fake.requests


def test_bot_registration_put_is_idempotent_and_uses_bot_authorization(monkeypatch, capsys):
    source, fake, _ = bot_registration(monkeypatch)
    for _ in range(2):
        assert server.main(["register-commands", "--env-file", "settings.conf"]) == 0
    assert len(fake.requests) == 2 and fake.requests[0].body == fake.requests[1].body == bot_expected_commands()
    for request in fake.requests:
        assert request.method == "PUT"
        assert request.path == (
            f"/api/v10/applications/{source['DISCORD_APPLICATION_ID']}/guilds/{source['QK_DISCORD_GUILD_ID']}/commands"
        )
        assert request.headers["Authorization"] == "Bot " + source["DISCORD_BOT_TOKEN"]
    captured = capsys.readouterr()
    assert source["DISCORD_BOT_TOKEN"] not in captured.out + captured.err


@pytest.mark.parametrize("name", ["DISCORD_APPLICATION_ID", "QK_DISCORD_GUILD_ID", "DISCORD_BOT_TOKEN"])
@pytest.mark.parametrize("value", ["", "bad value"])
def test_bot_registration_invalid_settings_return_two_without_transport(name, value, monkeypatch, capsys):
    _, fake, _ = bot_registration(monkeypatch, changes={name: value})
    assert server.main(["register-commands", "--env-file", "settings.conf"]) == 2
    captured = capsys.readouterr()
    assert not fake.requests
    if value:
        assert value not in captured.err


@pytest.mark.parametrize(
    "failure", [400, 401, 403, 429, 500, TimeoutError("synthetic raw detail"), OSError("synthetic raw detail")]
)
def test_bot_registration_discord_error_prints_status_only(failure, monkeypatch, capsys):
    script = [failure] if isinstance(failure, Exception) else [(failure, {"message": "synthetic raw detail"})]
    source, fake, _ = bot_registration(monkeypatch, script=script)
    assert server.main(["register-commands", "--env-file", "settings.conf"]) == 3
    captured = capsys.readouterr()
    assert (
        captured.out == ""
        and captured.err.strip() == f"Discord status: {failure if isinstance(failure, int) else 'unavailable'}"
    )
    assert source["DISCORD_BOT_TOKEN"] not in captured.err and len(fake.requests) == 1
