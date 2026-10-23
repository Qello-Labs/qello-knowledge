import json
from types import SimpleNamespace

import pytest

from qello_knowledge.domain.embedding import ProviderFailureKind
from qello_knowledge.domain.store import StoreUnavailable
from qello_knowledge.embedding.fake import FakeEmbeddingProvider
from qello_knowledge.indexer.cli import main
from qello_knowledge.ports.embedder import ProviderFailure
from tests.unit.fakes import valid_environ
from tests.unit.sync.helpers import cli_factory, harness


@pytest.fixture
def args(monkeypatch, tmp_path):
    for key, value in valid_environ().items():
        monkeypatch.setenv(key, value)
    return [
        "run",
        "--env-file",
        "/dev/null",
        "--sources",
        "tests/fixtures/sync/sources.toml",
        "--reviews",
        "tests/fixtures/sync/reviews",
    ]


def test_run_and_preview_emit_single_json_and_preview_has_no_writes(args, capsys):
    captured = []

    def factory(**kw):
        runtime = cli_factory(**kw)
        captured.append(runtime)
        return runtime

    assert main([*args, "--preview", "--json"], sync_factory=factory) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["preview"] and "run_id" not in output
    assert captured[0].deps.store.writes == 0
    assert main([*args, "--json"], sync_factory=factory) == 0
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "succeeded" and output["sources"][0]["counts"] == {"PROCESS": 5}


@pytest.mark.parametrize("mode,code", [("partial", 4), ("quota", 5), ("unavailable", 2), ("locked", 6)])
def test_exit_codes_use_real_flow_and_safe_errors(args, capsys, mode, code):
    def factory(**kw):
        provider = FakeEmbeddingProvider(
            fail_calls={
                1: ProviderFailure(
                    ProviderFailureKind.INPUT_TOO_LONG if mode == "partial" else ProviderFailureKind.PROVIDER_QUOTA
                )
            }
        )
        h = harness(provider=provider)
        if mode == "unavailable":
            h.store.index_state = lambda: (_ for _ in ()).throw(StoreUnavailable("QK-SYN-001-LEAK-MARKER"))
        if mode == "locked":
            h.store.try_lock = lambda kinds: None
        return SimpleNamespace(targets=h.targets, deps=h.deps, close=lambda: None)

    assert main([*args, "--json"], sync_factory=factory) == code
    assert "QK-SYN-001-LEAK-MARKER" not in capsys.readouterr().out


def test_preflight_rejection_never_builds_runtime(args, monkeypatch, capsys):
    def forbidden(**kw):
        pytest.fail("runtime must not be built")

    monkeypatch.setenv("QK_EMBED_INDEX_BUDGET", "invalid")
    assert main(args, sync_factory=forbidden) == 1
    capsys.readouterr()


def test_remote_gates_before_runtime(args, monkeypatch, capsys, tmp_path):
    monkeypatch.setenv("DATABASE_URL", "postgresql://placeholder@remote.example.invalid/db")
    missing = tmp_path / "store_policy.toml"

    def forbidden(**kw):
        pytest.fail("runtime must not be built")

    assert main(args, sync_factory=forbidden, store_policy_path=missing) == 3
    assert main([*args, "--allow-remote"], sync_factory=forbidden, store_policy_path=missing) == 1
    assert "remote.example.invalid" not in capsys.readouterr().out


def test_preview_and_explicit_trigger_are_incompatible(args):
    with pytest.raises(SystemExit) as error:
        main([*args, "--preview", "--trigger", "manual"], sync_factory=cli_factory)
    assert error.value.code == 2


def test_runs_prune_rejects_zero():
    with pytest.raises(SystemExit) as error:
        main(["runs", "prune", "--retention-days", "0"])
    assert error.value.code == 2


def test_run_read_commands_and_redaction_use_injected_store(monkeypatch, capsys):
    for key, value in valid_environ().items():
        monkeypatch.setenv(key, value)
    from qello_knowledge.domain.sync import ActivationCheck
    from qello_knowledge.ports.sync import IndexState
    from tests.unit.synthetic_secrets import SYNTHETIC

    class ReadStore:
        def load_sources(self):
            return {}

        def try_lock(self, kinds):
            return SimpleNamespace(close=lambda: None)

        def index_state(self):
            return IndexState(None, ("iv-test",))

        def list_runs(self, limit):
            return [{"run_id": "sync-test", "status": "partial"}]

        def run_detail(self, run):
            return {"run_id": run, "summary": {}}

        def run_failures(self, run):
            return [{"doc_display": SYNTHETIC["github-classic"], "stage": "embed", "failure": "input_too_long"}]

        def prune_runs(self, days):
            return 2

        def activate(self, version):
            return ActivationCheck(version, 1, 1, 0, "succeeded", ())

        def close(self):
            pass

    def factory(source, version):
        return ReadStore()

    for cmd in (
        ["runs", "list"],
        ["runs", "show", "sync-test", "--failures"],
        ["runs", "prune"],
        ["index", "status"],
        ["index", "activate", "iv-test"],
    ):
        assert main([*cmd, "--json", "--env-file", "/dev/null"], sync_store_factory=factory) == 0
        output = capsys.readouterr().out
        assert SYNTHETIC["github-classic"] not in output
        json.loads(output)


def test_preview_contains_the_source_contract_fields(args, capsys):
    assert main([*args, "--preview", "--json"], sync_factory=cli_factory) == 0
    source = json.loads(capsys.readouterr().out)["sources"][0]
    assert {
        "origin_version",
        "listing_complete",
        "stop_reason",
        "retry_at",
        "collection",
        "filter",
        "chunking",
        "embedding",
        "failures",
        "security_takedowns",
        "counts",
        "holds",
    } <= source.keys()


def test_runs_prune_preflight_failure_never_builds_store(monkeypatch):
    for key, value in valid_environ().items():
        monkeypatch.setenv(key, value)
    monkeypatch.setenv("QK_EMBED_INDEX_BUDGET", "invalid")

    def forbidden(*args):
        pytest.fail("store must not be built after failed preflight")

    assert main(["runs", "prune", "--env-file", "/dev/null"], sync_store_factory=forbidden) == 1
