"""`QK_CODE_CHUNKING`과 켜짐 교차 검사(QK-CHK-001 contracts 4절, research R-03·R-09, spec US6-5, tasks T029)."""

from __future__ import annotations

import pytest

from qello_knowledge.config.check import (
    CODE_INDEX_VERSION_UNREGISTERED,
    CODE_LIMIT_OVER_CONTEXT_BUDGET,
    build_report,
    code_chunking_from,
)
from qello_knowledge.config.loader import SettingStatus, load
from qello_knowledge.config.registry import SETTINGS, Entrypoint
from qello_knowledge.domain import keyword_rules
from qello_knowledge.domain.chunking import CodeChunkingSettings
from qello_knowledge.indexer.cli import main
from qello_knowledge.indexer.sync_cli import current_index_version
from tests.unit.chunking.code import fresh
from tests.unit.chunking.code.fresh import run_fresh
from tests.unit.fakes import valid_environ

SPEC = next(s for s in SETTINGS if s.name == "QK_CODE_CHUNKING")


def _load(entrypoint=Entrypoint.INDEX, **extra):
    return load(entrypoint, environ={**valid_environ(), **extra}, env_file=None)


def _names(report):
    return [c.name for c in report.checks if c.name.startswith("CODE_")]


def test_switch_values():
    assert SPEC.default == "off" and SPEC.entrypoints == frozenset({Entrypoint.INDEX})
    assert SPEC.rule("off") and SPEC.rule("on")
    assert not any(SPEC.rule(v) for v in ("ON", "true", "1", "yes", ""))
    assert code_chunking_from(_load()) is None
    assert code_chunking_from(_load(QK_CODE_CHUNKING="on")) == CodeChunkingSettings()
    invalid = _load(QK_CODE_CHUNKING="yes")
    assert dict((i.spec.name, i.status) for i in invalid.items)["QK_CODE_CHUNKING"] is SettingStatus.INVALID
    assert code_chunking_from(invalid) is None
    assert not build_report(invalid).ok


def test_off_keeps_report_shape():
    report = build_report(_load())
    assert report.ok and _names(report) == []


def test_on_is_blocked_until_index_version_is_registered(monkeypatch):
    report = build_report(_load(QK_CODE_CHUNKING="on"))
    assert not report.ok and _names(report) == [CODE_INDEX_VERSION_UNREGISTERED]
    on = current_index_version(code=CodeChunkingSettings())
    monkeypatch.setattr(keyword_rules, "INDEX_KEYWORD_RULES", {**keyword_rules.INDEX_KEYWORD_RULES, on: "x"})
    assert build_report(_load(QK_CODE_CHUNKING="on")).ok


def test_limit_over_context_budget(monkeypatch):
    on = current_index_version(code=CodeChunkingSettings())
    monkeypatch.setattr(keyword_rules, "INDEX_KEYWORD_RULES", {**keyword_rules.INDEX_KEYWORD_RULES, on: "x"})
    report = build_report(_load(QK_CODE_CHUNKING="on", QK_RETRIEVAL_CONTEXT_BUDGET="1499"))
    assert _names(report) == [CODE_LIMIT_OVER_CONTEXT_BUDGET] and not report.ok
    assert build_report(_load(QK_CODE_CHUNKING="on", QK_RETRIEVAL_CONTEXT_BUDGET="1500")).ok


def test_query_entrypoint_does_not_compute_code_checks():
    report = build_report(_load(Entrypoint.QUERY, QK_CODE_CHUNKING="on"))
    assert _names(report) == []


@pytest.mark.parametrize("args", [["run", "--preview"], ["run"]])
def test_run_stops_before_any_source_call(monkeypatch, capsys, args):
    for key, value in valid_environ().items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("QK_CODE_CHUNKING", "on")
    called = []
    command = [
        *args,
        "--json",
        "--env-file",
        "/dev/null",
        "--sources",
        "tests/fixtures/sync/sources.toml",
        "--reviews",
        "tests/fixtures/sync/reviews",
    ]
    assert main(command, sync_factory=lambda **kw: called.append(kw)) == 1
    assert called == []
    assert CODE_INDEX_VERSION_UNREGISTERED in capsys.readouterr().out


def test_query_path_does_not_import_chunker():
    assert run_fresh(fresh.after_query_imports) == []
