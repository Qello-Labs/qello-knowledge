import json
from pathlib import Path

from qello_knowledge.sources.config import load_sources
from qello_knowledge.sources.report import render_report, source_report


def test_table_and_single_line_json_show_status_and_scope():
    path = Path("tests/fixtures/sources/valid.toml")
    report = source_report(path, *load_sources(path))
    assert [s["status"] for s in report["sources"]] == ["OK", "DISABLED"]
    assert report["sources"][0]["scope"]["include"] == ["**/*.md"]
    output = render_report(report)
    assert "OK" in output and "비활성" in output and "include=1" in output
    line = render_report(report, json_output=True)
    assert "\n" not in line
    assert json.loads(line) == report


def test_invalid_report_has_codes_and_never_token_values(tmp_path):
    token = "sk" + "-" + "synthetic" * 5
    path = tmp_path / "sources.toml"
    path.write_text(Path("tests/fixtures/sources/token_value.toml").read_text().replace("TOKEN_PLACEHOLDER", token))
    report = source_report(path, *load_sources(path))
    assert not report["ok"]
    assert report["sources"][0]["status"] == "INVALID"
    assert {"field": "auth", "code": "TOKEN_VALUE"} in report["sources"][0]["issues"]
    assert token not in render_report(report)
    assert token not in render_report(report, json_output=True)
