import pytest

from qello_knowledge.config.check import build_report
from qello_knowledge.config.loader import load
from qello_knowledge.config.registry import Entrypoint
from tests.unit.fakes import valid_environ


def bot_report(**overrides):
    environ = {**valid_environ(), "QK_DISCORD_GUILD_ID": "9" * 18, "QK_DISCORD_ALLOWED_CHANNELS": "8" * 18, **overrides}
    return build_report(load(Entrypoint.QUERY, environ=environ, env_file=None))


def test_bot_default_cross_rules_and_empty_channels_warning():
    from qello_knowledge.config.check import BUDGET_CHECK

    report = bot_report()
    assert report.ok
    assert [c.name for c in report.checks] == [BUDGET_CHECK]
    report = bot_report(QK_DISCORD_ALLOWED_CHANNELS="")
    assert report.ok and "WARNING" in report.to_text()
    assert "QK_DISCORD_ALLOWED_CHANNELS" in report.to_json()


@pytest.mark.parametrize(
    "overrides,rule",
    [
        ({"QK_GEN_TIMEOUT_SECONDS": "30", "QK_QUERY_DEADLINE_SECONDS": "60"}, "generation_fits_query"),
        ({"QK_QUERY_MIN_START_SECONDS": "55"}, "minimum_start_before_deadline"),
        ({"QK_DISCORD_MAX_MESSAGES": "10"}, "query_call_limit"),
    ],
)
def test_bot_cross_rules_reject(overrides, rule):
    report = bot_report(**overrides)
    assert not report.ok
    failed = [c for c in report.checks if not c.ok]
    assert any(c.name == rule and c.detail == rule for c in failed)


def test_bot_token_lifetime_rule_even_for_individually_invalid_values():
    # 단일 항목 범위 안에서는 닿지 못하므로 교차 규칙 자체를 시험한다.
    from dataclasses import replace

    settings = load(Entrypoint.QUERY, environ={**valid_environ(), "QK_DISCORD_GUILD_ID": "9" * 18}, env_file=None)
    settings = replace(
        settings,
        items=tuple(
            replace(i, value="895") if i.spec.name == "QK_QUERY_DEADLINE_SECONDS" else i for i in settings.items
        ),
    )
    report = build_report(settings)
    assert any(c.name == "notice_before_token_expiry" and not c.ok for c in report.checks)


def test_bot_cross_rules_boundary_equalities():
    assert bot_report(QK_QUERY_DEADLINE_SECONDS="45").ok
    assert bot_report(QK_QUERY_MIN_START_SECONDS="54", QK_QUERY_CALL_LIMIT="19").ok
    assert not bot_report(QK_QUERY_CALL_LIMIT="18").ok
    assert not bot_report(QK_QUERY_DEADLINE_SECONDS="44").ok
