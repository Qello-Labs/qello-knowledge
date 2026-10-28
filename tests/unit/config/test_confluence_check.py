"""Confluence 켜짐 신호와 인덱스 대응표 막기(QK-ING-003 research R-10, contracts/source-config.md, SC-007·SC-014)."""

import json
from types import SimpleNamespace

import pytest

from qello_knowledge.config.check import CODE_INDEX_VERSION_UNREGISTERED, build_report
from qello_knowledge.config.loader import load
from qello_knowledge.config.registry import Entrypoint
from qello_knowledge.domain import keyword_rules
from qello_knowledge.domain.chunking import CodeChunkingSettings
from qello_knowledge.indexer.cli import main
from qello_knowledge.indexer.sync_cli import (
    _refresh_confluence,
    confluence_auth_issues,
    confluence_on,
    current_index_version,
)
from qello_knowledge.ports.sync import StoredSource
from qello_knowledge.sources.config import load_sources
from tests.unit.fakes import valid_environ

SOURCES = """[[source]]
name = "confluence-scrum"
kind = "confluence_pages"
enabled = {enabled}
auth = "ATLASSIAN_API_TOKEN"
[source.scope]
include = ["**"]
space_key = "SCRUM"
space_id = "12345"
judge_mode = "site_users"
"""

REVIEW = """source = "confluence-scrum"
reviewed_on = 2026-11-01
reviewer_role = "운영 담당"
method = "범위 페이지 열람"
result = "팀원 이름 외 개인 정보 없음"
team_member_names = "허용"
[scope]
include = ["**"]
space_key = "SCRUM"
space_id = "12345"
judge_mode = "site_users"
[site_users]
reviewed_on = 2026-11-01
user_count = 6
"""


def _files(tmp_path, enabled=True):
    sources = tmp_path / "sources.toml"
    sources.write_text(SOURCES.format(enabled="true" if enabled else "false"), encoding="utf-8")
    reviews = tmp_path / "reviews"
    reviews.mkdir()
    (reviews / "confluence-scrum.toml").write_text(REVIEW, encoding="utf-8")
    return sources, reviews


def _stored(kind):
    return StoredSource(source_name="x", source_kind=kind, scope_key="k", origin_id="1", origin_name="n")


def test_confluence_on_signal(tmp_path):
    sources, _ = _files(tmp_path)
    enabled, _ = load_sources(sources)
    (tmp_path / "off").mkdir()
    sources, _ = _files(tmp_path / "off", enabled=False)
    disabled, _ = load_sources(sources)
    assert confluence_on(enabled) is True
    assert confluence_on(disabled) is False
    assert confluence_on(disabled, [_stored("github_repo_files")]) is False
    assert confluence_on(disabled, [_stored("confluence_pages")]) is True


def test_versions_off_and_on():
    assert current_index_version() == "iv-4c0bc4fcc642"
    on = current_index_version(confluence=True)
    assert on != "iv-4c0bc4fcc642" and on not in keyword_rules.INDEX_KEYWORD_RULES
    both = current_index_version(code=CodeChunkingSettings(), confluence=True)
    assert both not in {on, current_index_version(code=CodeChunkingSettings())}


def test_sources_check_blocks_unregistered_on_version(tmp_path, capsys):
    sources, reviews = _files(tmp_path)
    assert main(["sources", "check", "--sources", str(sources), "--reviews", str(reviews), "--json"]) == 1
    assert "CONFLUENCE_INDEX_VERSION_UNREGISTERED" in capsys.readouterr().out


def test_sources_check_passes_when_disabled(tmp_path, capsys):
    sources, reviews = _files(tmp_path, enabled=False)
    assert main(["sources", "check", "--sources", str(sources), "--reviews", str(reviews), "--json"]) == 0


def _run(monkeypatch, sources, reviews, environ=None):
    for key, value in (environ or valid_environ()).items():
        monkeypatch.setenv(key, value)
    called = []
    command = ["run", "--json", "--env-file", "/dev/null", "--sources", str(sources), "--reviews", str(reviews)]
    return main(command, sync_factory=lambda **kw: called.append(kw)), called


def test_run_stops_before_any_source_call_when_on_version_unregistered(tmp_path, monkeypatch, capsys):
    sources, reviews = _files(tmp_path)
    code, called = _run(monkeypatch, sources, reviews)
    assert code == 1 and called == []
    assert json.loads(capsys.readouterr().out)["error"] == "confluence_index_version_unregistered"


def test_run_reports_missing_atlassian_settings(tmp_path, monkeypatch, capsys):
    sources, reviews = _files(tmp_path)
    environ = valid_environ()
    del environ["ATLASSIAN_EMAIL"]
    monkeypatch.delenv("ATLASSIAN_EMAIL", raising=False)
    code, called = _run(monkeypatch, sources, reviews, environ)
    assert code == 1 and called == []
    assert "AUTH_MISSING" in capsys.readouterr().out


def test_auth_issues_only_for_enabled_confluence(tmp_path):
    sources, _ = _files(tmp_path)
    configs, _ = load_sources(sources)
    settings = load(Entrypoint.INDEX, environ=valid_environ(), env_file=None)
    assert confluence_auth_issues(configs, settings) == ()
    environ = valid_environ()
    del environ["ATLASSIAN_CLOUD_ID"]
    settings = load(Entrypoint.INDEX, environ=environ, env_file=None)
    assert [(i.field, i.code) for i in confluence_auth_issues(configs, settings)] == [("auth", "AUTH_MISSING")]


def test_registered_confluence_keeps_version_after_disabling():
    from qello_knowledge.domain.chunking import ChunkingSettings
    from qello_knowledge.sync.run import SyncDependencies, current_spec

    store = SimpleNamespace(
        load_sources=lambda: {"confluence-scrum": _stored("confluence_pages")}, current_version=None
    )
    deps = SyncDependencies(store, None, None, None, ChunkingSettings(), None)
    runtime = SimpleNamespace(deps=deps)
    _refresh_confluence(runtime)
    assert runtime.deps.confluence is True
    assert store.current_version == current_spec(runtime.deps).id == current_index_version(confluence=True)


@pytest.mark.parametrize("registered", ["code_only", "code_and_confluence", "none"])
def test_code_check_accepts_either_registered_version(monkeypatch, registered):
    code_only = current_index_version(code=CodeChunkingSettings())
    both = current_index_version(code=CodeChunkingSettings(), confluence=True)
    extra = {"code_only": {code_only: "x"}, "code_and_confluence": {both: "x"}, "none": {}}[registered]
    monkeypatch.setattr(keyword_rules, "INDEX_KEYWORD_RULES", {**keyword_rules.INDEX_KEYWORD_RULES, **extra})
    report = build_report(load(Entrypoint.INDEX, environ=valid_environ() | {"QK_CODE_CHUNKING": "on"}, env_file=None))
    assert (CODE_INDEX_VERSION_UNREGISTERED in report.to_text()) is (registered == "none")
