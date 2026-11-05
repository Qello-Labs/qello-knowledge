"""`qk-index index status|activate`(QK-STO-002 contracts/cli.md 2·3절). 가짜 버전 저장소·가짜 게이트 확인만 쓴다."""

import json
from dataclasses import replace

import pytest

from qello_knowledge.domain.store import SchemaOutdated
from qello_knowledge.indexer.cli import main
from qello_knowledge.ports.index_versions import SwitchResult
from tests.unit.fakes import valid_environ
from tests.unit.indexer.index_fakes import BODY, DB_URL, V1, V2, FakeStore, FakeVersions, verifier, with_store


@pytest.fixture(autouse=True)
def env(monkeypatch):
    from types import MappingProxyType

    from qello_knowledge.domain import keyword_rules

    for key, value in valid_environ().items():
        monkeypatch.setenv(key, value)
    # 시험 인덱스 버전을 키워드 규칙 대응표에 넣는다(파일은 고치지 않는다, tasks 공통 규칙).
    rules = {**keyword_rules.INDEX_KEYWORD_RULES, V2: keyword_rules.INDEX_BASELINE}
    monkeypatch.setattr(keyword_rules, "INDEX_KEYWORD_RULES", MappingProxyType(rules))


def _main(args, store, *, gate=None, **kw):
    return main(
        [*args, "--json", "--env-file", "/dev/null"],
        sync_store_factory=with_store(store),
        history_factory=lambda root: None,
        gate_verifier=gate or verifier(),
        **kw,
    )


def _out(capsys):
    text = capsys.readouterr().out
    assert BODY not in text and DB_URL not in text  # SC-007
    return json.loads(text)


def test_status_without_version_store_keeps_current_keys(capsys):
    assert _main(["index", "status"], FakeStore(with_versions=False)) == 0
    assert set(_out(capsys)) == {"active", "ready", "current", "matches"}


def test_status_with_version_store_adds_keys(capsys):
    assert _main(["index", "status"], FakeStore()) == 0
    out = _out(capsys)
    assert {"active", "ready", "current", "matches", "mismatch_since", "versions", "coverage", "resolutions"} <= set(
        out
    )
    assert out["matches"] is False and out["resolutions"] == ["reindex_gate_activate", "redeploy_active_settings"]
    assert out["coverage"]["remaining"] == 2


def test_first_activation_unchanged(capsys):
    assert _main(["index", "activate", "iv-x"], FakeStore(active=None, with_versions=False)) == 0
    assert _out(capsys)["failed_conditions"] == []


def test_activate_requires_gate_then_version_store(capsys):
    assert _main(["index", "activate", V2], FakeStore(with_versions=False)) == 1
    assert _out(capsys)["error"] == "gate_record_required"
    assert _main(["index", "activate", V2, "--gate", "g.json"], FakeStore(with_versions=False)) == 2
    assert _out(capsys)["error"] == "store_unavailable"


def test_activate_preview_then_confirm(capsys):
    versions = FakeVersions()
    store = FakeStore(versions=versions)
    assert _main(["index", "activate", V2, "--gate", "g.json"], store) == 4
    out = _out(capsys)
    assert out["applied"] is False and out["failed_conditions"] == []
    assert out["uncovered_sources"] == [{"name": "wiki", "kind": "confluence_pages"}]
    assert out["retrieval_settings"]["policy"] == out["retrieval_settings"]["code_defaults"]
    assert out["notes"] and out["gate"]["gate_id"] == "gate-x" and versions.calls == []
    assert _main(["index", "activate", V2, "--gate", "g.json", "--confirm"], store) == 0
    out = _out(capsys)
    assert out["applied"] is True and out["transition_id"] == 7
    (_, version, kind, kw) = versions.calls[0]
    assert (version, kind, kw["gate_record_id"], kw["gate_record_sha256"]) == (V2, "activation", "gate-x", "a" * 64)


def test_activate_reports_all_failed_conditions(capsys):
    versions = FakeVersions()
    versions.activation = replace(versions.activation, purge_pending=1, sync_running=True)
    gate = verifier(failed=("gate_policy",))
    assert (
        _main(["index", "activate", V2, "--gate", "g.json", "--confirm"], FakeStore(versions=versions), gate=gate) == 1
    )
    assert set(_out(capsys)["failed_conditions"]) >= {"gate_policy", "purge_pending", "sync_running"}
    assert versions.calls == []


def test_lock_contention_is_exit_6(capsys):
    versions = FakeVersions(switch=SwitchResult(False, ("sync_running",)))
    assert _main(["index", "activate", V2, "--gate", "g.json", "--confirm"], FakeStore(versions=versions)) == 6
    assert _out(capsys)["failed_conditions"] == ["sync_running"]


def test_schema_outdated_is_exit_1(capsys):
    store = FakeStore()

    def outdated():
        raise SchemaOutdated("schema_outdated")

    store.index_versions = outdated
    assert _main(["index", "status"], store) == 1
    assert _out(capsys)["error"] == "schema_outdated"


@pytest.mark.parametrize(
    "cmd", [["index", "activate", V2, "--gate", "g.json"], ["index", "rollback", V1], ["index", "prune", V1]]
)
def test_remote_writes_need_confirmation(cmd, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql://placeholder@remote.example.invalid/db")
    assert _main(cmd, FakeStore()) == 3
    assert "remote.example.invalid" not in capsys.readouterr().out
