"""`qk-index index prune`와 `status` 새 키(QK-STO-002 contracts/cli.md 2·5절)."""

import json
from dataclasses import replace

import pytest

from qello_knowledge.indexer.cli import main
from qello_knowledge.ports.index_versions import PruneState
from tests.unit.fakes import valid_environ
from tests.unit.indexer.index_fakes import V1, V2, FakeStore, FakeVersions, row, verifier, with_store


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


def test_prune_preview_and_confirm(capsys):
    versions = FakeVersions()
    store = FakeStore(versions=versions)
    assert _main(["index", "prune", V1], store) == 4
    out = json.loads(capsys.readouterr().out)
    assert set(out) == {
        "version",
        "status",
        "chunks_to_delete",
        "deleted_chunks",
        "pruned",
        "failed_conditions",
        "applied",
    }
    assert out["chunks_to_delete"] == 6 and versions.calls == []
    assert _main(["index", "prune", V1, "--confirm"], store) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["applied"] is True and out["deleted_chunks"] == 6 and out["pruned"] is True


def test_prune_refusals(capsys):
    versions = FakeVersions(prune=PruneState(row(V1, "archived"), V2, V2, V1, 6, False))
    assert _main(["index", "prune", V1, "--confirm"], FakeStore(versions=versions)) == 1
    assert json.loads(capsys.readouterr().out)["failed_conditions"] == ["rollback_target_unconfirmed"]
    assert _main(["index", "prune", V1, "--confirm", "--confirm-rollback-target"], FakeStore(versions=versions)) == 0
    capsys.readouterr()
    versions.prune_snapshot = replace(versions.prune_snapshot, target=row(V2, "active"), rollback_target=None)
    assert _main(["index", "prune", V2], FakeStore(versions=versions)) == 1
    assert "active_version" in json.loads(capsys.readouterr().out)["failed_conditions"]
    assert _main(["index", "prune", V1], FakeStore(with_versions=False)) == 2
    assert json.loads(capsys.readouterr().out)["error"] == "store_unavailable"


def test_status_versions_have_coverage_note(capsys):
    assert _main(["index", "status"], FakeStore()) == 0
    out = json.loads(capsys.readouterr().out)
    by_id = {v["id"]: v for v in out["versions"]}
    assert by_id[V1]["coverage"] is None and by_id[V1]["coverage_note"] == "not_current_version"
    assert set(by_id[V1]) >= {"prune_candidate", "rollback_target", "last_reindex", "ever_active", "pruned_at"}
