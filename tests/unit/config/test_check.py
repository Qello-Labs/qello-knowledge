import json

from qello_knowledge.config.check import build_report
from qello_knowledge.config.loader import SettingStatus, load
from qello_knowledge.config.registry import Entrypoint
from tests.unit.fakes import valid_environ


def _report(entrypoint: Entrypoint, environ: dict[str, str]):
    return build_report(load(entrypoint, environ=environ, env_file=None))


def test_two_missing_index_settings_are_reported_together() -> None:
    environ = valid_environ()
    del environ["GITHUB_API_TOKEN"]
    del environ["CLOUDFLARE_API_TOKEN"]
    report = _report(Entrypoint.INDEX, environ)
    assert not report.ok
    missing = {name for name, status in report.items if status is SettingStatus.MISSING}
    assert missing == {"GITHUB_API_TOKEN", "CLOUDFLARE_API_TOKEN"}


def test_invalid_secret_reports_name_only() -> None:
    environ = valid_environ()
    environ["GITHUB_API_TOKEN"] = "형식이-틀린-값-0123456789"
    report = _report(Entrypoint.INDEX, environ)
    assert ("GITHUB_API_TOKEN", SettingStatus.INVALID) in report.items
    assert "형식이-틀린-값" not in report.to_text()
    assert "형식이-틀린-값" not in report.to_json()


def test_query_passes_without_index_only_settings() -> None:
    environ = {k: v for k, v in valid_environ().items() if not k.startswith(("GITHUB_", "CLOUDFLARE_"))}
    assert _report(Entrypoint.QUERY, environ).ok


def test_optional_invalid_value_fails() -> None:
    environ = valid_environ()
    environ["QK_LOG_LEVEL"] = "LOUD"
    assert not _report(Entrypoint.QUERY, environ).ok


def test_all_valid_settings_pass_and_list_names() -> None:
    report = _report(Entrypoint.INDEX, valid_environ())
    assert report.ok
    assert all(status is SettingStatus.OK for _, status in report.items)
    assert "결과: 통과" in report.to_text()
    payload = json.loads(report.to_json())
    assert payload["entrypoint"] == "index"
    assert {item["name"] for item in payload["items"]} == {name for name, _ in report.items}
