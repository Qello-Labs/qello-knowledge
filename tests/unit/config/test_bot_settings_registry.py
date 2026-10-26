import pytest

from qello_knowledge.config.loader import load
from qello_knowledge.config.registry import SETTINGS, Entrypoint, specs_for

BOT_RANGES = [
    ("QK_RELAY_TIMEOUT_SECONDS", "0.5", "2.8", "0.49", "2.81", "2.5"),
    ("QK_QUERY_DEADLINE_SECONDS", "15", "120", "14", "121", "55"),
    ("QK_QUERY_START_WAIT_SECONDS", "4", "10", "3", "11", "5"),
    ("QK_QUERY_MIN_START_SECONDS", "8", "60", "7", "61", "15"),
    ("QK_QUERY_NOTICE_GRACE_SECONDS", "1", "30", "0", "31", "5"),
    ("QK_QUERY_CALL_LIMIT", "11", "50", "10", "51", "20"),
    ("QK_DISCORD_MAX_MESSAGES", "2", "10", "1", "11", "4"),
    ("QK_DISCORD_TITLE_MAX_CHARS", "20", "200", "19", "201", "80"),
    ("QK_DISCORD_LINK_MAX_CHARS", "50", "1000", "49", "1001", "300"),
    ("QK_QUERY_WORKERS", "1", "8", "0", "9", "2"),
    ("QK_QUERY_QUEUE_SIZE", "1", "16", "0", "17", "4"),
]


def test_bot_entrypoints():
    assert Entrypoint.RELAY.value == "relay" and Entrypoint.REGISTER.value == "register"
    assert {s.name for s in specs_for(Entrypoint.RELAY)} == {"DISCORD_PUBLIC_KEY", "QK_RELAY_TIMEOUT_SECONDS"}
    specs = {s.name: s for s in SETTINGS}
    assert specs["DISCORD_BOT_TOKEN"].entrypoints == {Entrypoint.REGISTER}
    assert specs["DISCORD_BOT_TOKEN"].required
    for name in ("DISCORD_APPLICATION_ID", "QK_DISCORD_GUILD_ID"):
        assert specs[name].entrypoints == {Entrypoint.QUERY, Entrypoint.REGISTER}
        assert specs[name].required
    for name in ("CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID"):
        assert specs[name].entrypoints == {Entrypoint.QUERY, Entrypoint.INDEX}


@pytest.mark.parametrize("name,low,high,below,above,default", BOT_RANGES)
def test_bot_ranges(name, low, high, below, above, default):
    spec = next(s for s in SETTINGS if s.name == name)
    assert spec.default == default
    assert spec.rule(low) and spec.rule(high)
    for invalid in (below, above, "NaN", "inf", "-1", "1e1", "private-invalid-marker"):
        assert not spec.rule(invalid)
    if name != "QK_RELAY_TIMEOUT_SECONDS":
        assert not spec.rule("4.0")


@pytest.mark.parametrize("name", ["QK_DISCORD_ALLOWED_CHANNELS", "QK_DISCORD_ALLOWED_ROLES"])
def test_bot_snowflake_lists(name):
    spec = next(s for s in SETTINGS if s.name == name)
    assert spec.rule("") and spec.rule("9" * 17 + "," + "8" * 20)
    for value in (
        "9" * 16,
        "9" * 21,
        "9" * 18 + ",",
        "," + "9" * 18,
        "9" * 18 + ", " + "8" * 18,
        "9" * 18 + "," + "9" * 18,
        " ",
    ):
        assert not spec.rule(value)


def test_bot_guild_and_error_output():
    spec = next(s for s in SETTINGS if s.name == "QK_DISCORD_GUILD_ID")
    assert spec.rule("9" * 17) and spec.rule("9" * 20)
    assert not spec.rule("9" * 16) and not spec.rule("9" * 21)
    from qello_knowledge.config.check import build_report

    report = build_report(load(Entrypoint.QUERY, environ={"QK_QUERY_WORKERS": "private-invalid-marker"}, env_file=None))
    assert "private-invalid-marker" not in report.to_json() + report.to_text()
