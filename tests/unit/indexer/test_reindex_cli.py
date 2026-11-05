"""`qk-index run --reindex`(QK-STO-002 contracts/cli.md 1절). 가짜 자료원·가짜 임베딩만 주입한다."""

import json
from dataclasses import replace
from types import SimpleNamespace

import pytest

from qello_knowledge.domain.embedding import BudgetSettings
from qello_knowledge.domain.store import SchemaOutdated
from qello_knowledge.indexer.cli import main
from qello_knowledge.sync.run import SyncOptions, current_spec, run_sync
from tests.unit.fakes import valid_environ
from tests.unit.sync.helpers import harness
from tests.unit.sync.reindex_fakes import DOCS, NEW_CHUNKING, ReindexMemoryStore

URL_SCHEME = "postgres" + "ql://"


@pytest.fixture
def args(monkeypatch):
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


def _factory(store, *, chunking=NEW_CHUNKING, cache=None, settings=None, created=None):
    def factory(**kw):
        h = harness(DOCS, store=store, cache_store=cache, chunking=chunking, settings=settings)
        runtime = SimpleNamespace(targets=h.targets, deps=replace(h.deps, policy=kw["policy"]), close=lambda: None)
        if created is not None:
            created.append(h)
        return runtime

    return factory


def _seed(active=True):
    store = ReindexMemoryStore()
    first = harness(DOCS, store=store)
    run_sync(first.targets, first.deps, SyncOptions())
    if active:
        store.indexes[current_spec(first.deps).id] = "active"
    return store


def _out(capsys):
    text = capsys.readouterr().out
    assert "Text for" not in text and URL_SCHEME not in text  # SC-007
    return json.loads(text)


@pytest.mark.parametrize("extra", [["--trigger", "schedule"], ["--source", "docs"]])
def test_reindex_option_combinations_are_argument_errors(args, extra):
    with pytest.raises(SystemExit) as raised:
        main([*args, "--reindex", *extra], sync_factory=_factory(ReindexMemoryStore()))
    assert raised.value.code == 2


def test_reindex_refusals_exit_1(args, capsys):
    assert main([*args, "--reindex"], sync_factory=_factory(_seed(active=False))) == 1
    assert _out(capsys)["error"] == "no_active_version"
    store = _seed()
    assert main([*args, "--reindex"], sync_factory=_factory(store, chunking=None)) == 1
    assert _out(capsys)["error"] == "not_mismatched"
    assert main([*args, "--reindex", "--preview"], sync_factory=_factory(store, chunking=None)) == 1
    assert _out(capsys)["error"] == "not_mismatched"


def test_reindex_preview_has_keys_and_no_writes(args, capsys):
    store = _seed()
    writes = store.writes
    assert main([*args, "--reindex", "--preview", "--json"], sync_factory=_factory(store)) == 0
    output = _out(capsys)
    assert output["preview"] is True
    assert {
        "candidate",
        "embedding",
        "budget",
        "estimated_days",
        "coverage",
        "hidden_held",
        "security_takedowns",
    } <= set(output["reindex"])
    assert store.writes == writes


def test_reindex_run_and_budget_refusal(args, capsys):
    store = _seed()
    created = []
    tight = BudgetSettings(index_budget=0)
    code = main(
        [*args, "--reindex"], sync_factory=_factory(store, cache=ReindexMemoryStore(), settings=tight, created=created)
    )
    assert code == 5 and _out(capsys)["error"] == "budget_exceeded"
    assert created[0].provider.calls == []
    assert main([*args, "--reindex", "--json"], sync_factory=_factory(store)) == 0
    output = _out(capsys)
    assert output["kind"] == "reindex" and output["status"] == "succeeded"
    assert list(store.run_kinds.values())[-1] == "reindex"


def test_schema_outdated_exits_1(args, capsys):
    store = _seed()

    def outdated(run, names):
        raise SchemaOutdated("schema_outdated")

    store.begin_run = outdated
    assert main([*args, "--reindex"], sync_factory=_factory(store)) == 1
    assert _out(capsys)["error"] == "schema_outdated"


def test_remote_reindex_requires_confirmation(args, monkeypatch, capsys):
    monkeypatch.setenv("DATABASE_URL", "postgresql://placeholder@remote.example.invalid/db")

    def forbidden(**kw):
        raise AssertionError("runtime must not be built")

    assert main([*args, "--reindex"], sync_factory=forbidden) == 3
    assert "remote.example.invalid" not in capsys.readouterr().out
