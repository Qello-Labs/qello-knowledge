"""`qk-index index rollback`(QK-STO-002 contracts/cli.md 4절)."""

import json
from dataclasses import replace

import pytest

from qello_knowledge.indexer.cli import main
from tests.unit.fakes import valid_environ
from tests.unit.indexer.index_fakes import V1, V2, FakeStore, FakeVersions, verifier, with_store

REASON = "합성 사유 문장"


@pytest.fixture(autouse=True)
def env(monkeypatch):
    from types import MappingProxyType

    from qello_knowledge.domain import keyword_rules

    for key, value in valid_environ().items():
        monkeypatch.setenv(key, value)
    rules = {**keyword_rules.INDEX_KEYWORD_RULES, V2: keyword_rules.INDEX_BASELINE}
    monkeypatch.setattr(keyword_rules, "INDEX_KEYWORD_RULES", MappingProxyType(rules))


def _main(args, store):
    return main(
        [*args, "--json", "--env-file", "/dev/null"],
        sync_store_factory=with_store(store),
        history_factory=lambda root: None,
        gate_verifier=verifier(),
    )


def _out(capsys):
    text = capsys.readouterr().out
    assert REASON not in text  # 사유는 전환 기록에만 남긴다
    return json.loads(text)


def test_rollback_preview_confirm_and_mismatch_after(capsys):
    versions = FakeVersions()
    store = FakeStore(versions=versions)
    assert _main(["index", "rollback", V1, "--reason", REASON], store) == 4
    out = _out(capsys)
    assert set(out) == {
        "target",
        "active",
        "missing_documents",
        "provenance_mismatch",
        "purge_pending_documents",
        "failed_conditions",
        "applied",
    }
    assert out["missing_documents"] == 1 and versions.calls == []
    assert _main(["index", "rollback", V1, "--reason", REASON, "--confirm"], store) == 0
    out = _out(capsys)
    assert out["applied"] is True and out["mismatch_after"] is True and len(out["resolutions"]) == 2
    (_, version, kind, kw) = versions.calls[0]
    assert (version, kind, kw["reason"]) == (V1, "rollback", REASON)


def test_rollback_failures(capsys):
    assert _main(["index", "rollback", V1], FakeStore()) == 1
    assert _out(capsys)["failed_conditions"] == ["reason_required"]
    versions = FakeVersions()
    versions.rollback = replace(versions.rollback, provenance_mismatch=3)
    assert _main(["index", "rollback", V1, "--reason", REASON, "--confirm"], FakeStore(versions=versions)) == 1
    assert _out(capsys)["failed_conditions"] == ["provenance_unconfirmed"]
    assert (
        _main(
            ["index", "rollback", V1, "--reason", REASON, "--confirm", "--confirm-stale"], FakeStore(versions=versions)
        )
        == 0
    )
    _out(capsys)


def test_rollback_without_version_store(capsys):
    assert _main(["index", "rollback", V1, "--reason", REASON], FakeStore(with_versions=False)) == 2
    assert _out(capsys)["error"] == "store_unavailable"
