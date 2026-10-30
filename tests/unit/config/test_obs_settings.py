"""OBS 설정 기본값·범위·교차 검사."""

from datetime import UTC, datetime, timedelta

import pytest

from qello_knowledge.config.check import build_report
from qello_knowledge.config.loader import load
from qello_knowledge.config.registry import Entrypoint, specs_for
from tests.unit.fakes import valid_environ


def report(**values):
    return build_report(load(Entrypoint.QUERY, environ={**valid_environ(), **values}, env_file=None))


def test_defaults_and_entrypoints():
    specs = {s.name: s for s in specs_for(Entrypoint.QUERY)}
    for name, default in [
        ("QK_QUERY_LOG_ENABLED", "false"),
        ("QK_QUERY_PENDING_SECONDS", "3600"),
        ("QK_QUERY_PENDING_MAX", "500"),
        ("QK_QUERY_RECORD_TIMEOUT_MS", "1000"),
        ("QK_DISCORD_COMPONENT_TIMEOUT_MS", "1500"),
        ("QK_QUERY_TEXT_RETAIN_UNTIL", ""),
    ]:
        assert specs[name].default == default
    assert "QK_RELAY_TIMEOUT_SECONDS" in specs
    assert "QK_QUERY_TEXT_RETAIN_UNTIL" in {s.name for s in specs_for(Entrypoint.INDEX)}


@pytest.mark.parametrize(
    "name,value",
    [
        ("QK_QUERY_PENDING_SECONDS", "59"),
        ("QK_QUERY_PENDING_SECONDS", "3601"),
        ("QK_QUERY_PENDING_MAX", "9"),
        ("QK_QUERY_PENDING_MAX", "2001"),
        ("QK_QUERY_RECORD_TIMEOUT_MS", "99"),
        ("QK_DISCORD_COMPONENT_TIMEOUT_MS", "499"),
        ("QK_DISCORD_COMPONENT_TIMEOUT_MS", "2001"),
        ("QK_QUERY_TEXT_RETAIN_UNTIL", "2026-02-30"),
        ("QK_QUERY_LOG_ENABLED", "on"),
    ],
)
def test_invalid(name, value):
    assert not report(**{name: value}).ok


def test_cross_checks():
    assert not report(QK_QUERY_LOG_ENABLED="true").ok
    assert not report(QK_DISCORD_COMPONENT_TIMEOUT_MS="1500", QK_RELAY_TIMEOUT_SECONDS="1.5").ok
    past = (datetime.now(UTC).date() - timedelta(days=1)).isoformat()
    assert any("erase-texts" in w for w in report(QK_QUERY_TEXT_RETAIN_UNTIL=past).warnings)


def test_sources_capacity_warning(monkeypatch):
    monkeypatch.setattr("qello_knowledge.sources.config.load_sources", lambda path: (tuple(range(20)), ()))
    assert "sources_message_capacity" in report().warnings
