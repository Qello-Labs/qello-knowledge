"""예산 설정 3항목과 교차 검사(FR-017, US4 AS6)."""

import pytest

from qello_knowledge.config.check import BUDGET_CHECK, budget_settings, build_report
from qello_knowledge.config.loader import SettingStatus, load
from qello_knowledge.config.registry import Entrypoint
from qello_knowledge.domain.embedding import BudgetSettings
from tests.unit.fakes import valid_environ


def _report(entrypoint: Entrypoint, **extra: str):
    return build_report(load(entrypoint, environ={**valid_environ(), **extra}, env_file=None))


@pytest.mark.parametrize("entrypoint", [Entrypoint.INDEX, Entrypoint.QUERY])
def test_defaults_pass(entrypoint) -> None:
    report = _report(entrypoint)
    assert report.ok
    assert [(c.name, c.ok, c.detail) for c in report.checks] == [(BUDGET_CHECK, True, "5000 + 3000 <= 10000")]
    settings = load(entrypoint, environ=valid_environ(), env_file=None)
    assert budget_settings(settings) == BudgetSettings(10000, 5000, 3000)


def test_index_budget_over_allowance_fails_and_prints_numbers_only() -> None:
    report = _report(Entrypoint.INDEX, QK_EMBED_INDEX_BUDGET="8000")
    assert not report.ok
    assert f"FAIL     {BUDGET_CHECK} (8000 + 3000 <= 10000)" in report.to_text()
    assert '"ok": false' in report.to_json()


@pytest.mark.parametrize("value", ["0", "-1", "abc", "1.5"])
def test_non_positive_or_non_integer_is_invalid(value) -> None:
    report = _report(Entrypoint.INDEX, QK_EMBED_QUERY_RESERVE=value)
    assert ("QK_EMBED_QUERY_RESERVE", SettingStatus.INVALID) in report.items
    assert not report.ok
    assert report.checks == ()
