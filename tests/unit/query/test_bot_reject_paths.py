import json

import pytest

from qello_knowledge.discord.notices import FIXED_NOTICES
from tests.unit.discord.bot_builders import ROLE, ask, component, other_command
from tests.unit.query.bot_runtime import bot_request
from tests.unit.query.bot_security import bot_secured_runtime
from tests.unit.synthetic_secrets import SYNTHETIC


@pytest.mark.parametrize("case", ["missing", "wrong", "past", "future"])
def test_bot_bad_signatures_have_no_work_or_operational_log(case, capsys, caplog):
    runtime = bot_secured_runtime()
    body = ask("합성 질문")
    headers = runtime.key.sign(body, "1000")
    if case == "missing":
        headers = {"X-Signature-Timestamp": "1000"}
    elif case == "wrong":
        headers = runtime.key.other_key_sign(body, "1000")
    else:
        headers = runtime.key.sign(body, "699" if case == "past" else "1301")
    assert bot_request(runtime, body, headers=headers)[0] == 401
    assert not runtime.calls and not runtime.fake.requests and runtime.jobs.in_flight == 0
    assert capsys.readouterr().err == "" and not caplog.records


@pytest.mark.parametrize("private", [False, True])
@pytest.mark.parametrize(
    "options,changes",
    [
        ({}, {"guild": "8" * 18}),
        ({}, {"channel": "8" * 18}),
        ({}, {"guild": None}),
        ({}, {"channel_type": 11}),
        ({"roles": (ROLE,)}, {}),
        ({"channels": ()}, {}),
        ({"guild": None}, {}),
    ],
)
def test_bot_outside_access_is_always_private(options, changes, private):
    runtime = bot_secured_runtime(**options)
    status, raw, headers = bot_request(runtime, ask("합성 질문", private=private, **changes))
    data = json.loads(raw)["data"]
    assert status == 200 and not headers and data["flags"] == 64
    assert data["content"] == FIXED_NOTICES["access"] and data["allowed_mentions"] == {"parse": []}
    assert not runtime.calls and not runtime.fake.requests and runtime.jobs.in_flight == 0


@pytest.mark.parametrize("private", [False, True])
@pytest.mark.parametrize("name", list(SYNTHETIC))
def test_bot_synthetic_secrets_are_blocked_before_deferral(name, private, capsys, caplog):
    runtime = bot_secured_runtime()
    value = SYNTHETIC[name]
    _, raw, headers = bot_request(runtime, ask("합성 질문 " + value, private=private))
    data = json.loads(raw)["data"]
    assert data["flags"] == 64 and data["content"] == FIXED_NOTICES["secret"] and not headers
    assert not runtime.calls and not runtime.fake.requests and runtime.jobs.in_flight == 0
    assert value not in raw + capsys.readouterr().err + caplog.text


@pytest.mark.parametrize("body", [component(), other_command("other")])
def test_bot_unsupported_requests_are_private(body):
    runtime = bot_secured_runtime()
    _, raw, _ = bot_request(runtime, body)
    assert json.loads(raw)["data"]["flags"] == 64
    assert json.loads(raw)["data"]["content"] == FIXED_NOTICES["unsupported"]
    assert not runtime.calls and not runtime.fake.requests


def test_bot_production_composition_loads_policy_once_and_enforces_guards(monkeypatch):
    from types import SimpleNamespace

    from qello_knowledge.config.loader import load
    from qello_knowledge.config.registry import Entrypoint
    from qello_knowledge.query.server import create_app
    from qello_knowledge.security.policy import SecurityPolicy
    from tests.unit.discord.bot_builders import CHANNEL, GUILD, signing_key
    from tests.unit.fakes import valid_environ

    reads = []
    monkeypatch.setattr("qello_knowledge.sources.config.load_sources", lambda path: ((), ()))

    def policy(path, configs):
        reads.append(path)
        return SecurityPolicy(), ()

    monkeypatch.setattr("qello_knowledge.security.policy.load_policy", policy)
    monkeypatch.setattr("qello_knowledge.query.pipeline.configured_pipeline", lambda *a: None)
    monkeypatch.setattr("qello_knowledge.adapters.discord.webhook.DiscordWebhook", lambda *a: SimpleNamespace())
    key = signing_key()
    settings = load(
        Entrypoint.QUERY,
        environ={
            **valid_environ(),
            "DISCORD_PUBLIC_KEY": key.public_key,
            "QK_DISCORD_GUILD_ID": GUILD,
            "QK_DISCORD_ALLOWED_CHANNELS": CHANNEL,
        },
        env_file=None,
    )
    app = create_app(settings)
    app.wall_clock = lambda: 1000
    try:
        for body, expected in [
            (ask("합성 질문", channel="8" * 18), FIXED_NOTICES["access"]),
            (ask(SYNTHETIC["github-classic"]), FIXED_NOTICES["secret"]),
        ]:
            _, raw, headers = app.respond("/discord/interactions", body, key.sign(body, "1000"))
            assert json.loads(raw)["data"]["content"] == expected and not headers
        assert len(reads) == 1 and app.jobs.in_flight == 0
    finally:
        app.jobs.close()


def test_bot_policy_read_failure_stops_serve_without_exposing_details(monkeypatch, capsys):
    from qello_knowledge.config.loader import load
    from qello_knowledge.config.registry import Entrypoint
    from qello_knowledge.query import server
    from tests.unit.fakes import valid_environ

    settings = load(Entrypoint.QUERY, environ=valid_environ(), env_file=None)
    monkeypatch.setattr(server, "load", lambda *a, **k: settings)
    monkeypatch.setattr("qello_knowledge.sources.config.load_sources", lambda path: ((), ("합성 원문 오류",)))
    assert server.main(["serve"]) == 2
    assert "합성 원문 오류" not in capsys.readouterr().err
