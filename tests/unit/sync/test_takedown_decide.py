from dataclasses import replace

import pytest

from qello_knowledge.domain.sync import HoldReason, Operation, allowed
from qello_knowledge.sync.decide import exceeds_takedown_ratio
from qello_knowledge.sync.run import SyncOptions, run_sync
from tests.unit.sync.helpers import DEFAULT_DOCS, harness


@pytest.mark.parametrize(
    "hold, operations",
    [
        (
            "BUDGET_EXCEEDED",
            {"SECURITY_HIDE", "SECURITY_PURGE", "SOURCE_MISSING", "GENERAL_TAKEDOWN", "PURGE", "MARK_SEEN"},
        ),
        ("BUDGET_EXHAUSTED", set(Operation)),
        ("INDEX_MISMATCH", {"SECURITY_HIDE", "SECURITY_PURGE", "PURGE", "MARK_SEEN"}),
        ("TAKEDOWN_RATIO", {"PROCESS", "SECURITY_HIDE", "MARK_SEEN"}),
        ("ORIGIN_MISMATCH", {"SECURITY_HIDE", "SECURITY_PURGE"}),
        ("ORIGIN_MISSING", {"SECURITY_HIDE", "SECURITY_PURGE"}),
        (
            "COLLECTION_INCOMPLETE",
            {"PROCESS", "SECURITY_HIDE", "SECURITY_PURGE", "GENERAL_TAKEDOWN", "PURGE", "MARK_SEEN"},
        ),
    ],
)
def test_all_49_hold_operation_cells(hold, operations):
    for operation in Operation:
        assert allowed({HoldReason(hold)}, operation) == (operation in operations)
        assert allowed({HoldReason(hold), HoldReason.ORIGIN_MISSING}, operation) == (
            operation in operations and operation in {"SECURITY_HIDE", "SECURITY_PURGE"}
        )


@pytest.mark.parametrize(
    "base, general, purge, expected",
    [(5, 1, 0, False), (5, 2, 0, True), (5, 0, 2, True), (0, 0, 0, False), (0, 1, 0, True)],
)
def test_takedown_ratio_boundaries(base, general, purge, expected):
    assert exceeds_takedown_ratio(base, general, purge) is expected


def test_incomplete_listing_does_not_hide_missing_but_does_apply_stored_exclusion(monkeypatch):
    from qello_knowledge.domain.source_config import SourceScope
    from qello_knowledge.security import screen
    from tests.unit.security.helpers import fake_config

    first = harness()
    run_sync(first.targets, first.deps, SyncOptions())
    actual_list = screen.list_all
    monkeypatch.setattr(screen, "list_all", lambda *args: replace(actual_list(*args), complete=False))
    second = harness(
        {k: v for k, v in DEFAULT_DOCS.items() if k not in {"D", "E"}},
        store=first.store,
        config=fake_config(scope=SourceScope(("elsewhere/**",), ("DOCS/d.md",))),
    )
    result = run_sync(second.targets, second.deps, SyncOptions())
    assert result.status == "stopped"
    assert second.store.load_documents("fake")["D"].takedown_reason == "config_excluded"
    assert second.store.load_documents("fake")["E"].status == "active"


@pytest.mark.parametrize(
    "mode, expected",
    [("path", "security_path"), ("not_markdown", "not_target"), ("fetch", None), ("screen", None), ("stopped", None)],
)
def test_takedown_classification_keeps_fetch_and_judgment_failures_active(mode, expected, monkeypatch):
    from qello_knowledge.domain.source import (
        ContentFormat,
        FailureType,
        RunStopped,
        SourceFailure,
        StopInfo,
        StopReason,
    )

    first = harness()
    run_sync(first.targets, first.deps, SyncOptions())
    second = harness(store=first.store, locations={"D": "secrets/D.md"} if mode == "path" else None)
    adapter = second.targets[0].adapter
    original = adapter.fetch_content

    def fetched(session, config, item):
        if item.source_id == "D":
            if mode == "fetch":
                raise SourceFailure(FailureType.NOT_FOUND)
            if mode == "stopped":
                raise RunStopped(StopInfo(StopReason.REQUEST_BUDGET))
            content = original(session, config, item)
            if mode == "not_markdown":
                return replace(content, content_format=ContentFormat.TEXT)
            return content
        return original(session, config, item)

    monkeypatch.setattr(adapter, "fetch_content", fetched)
    if mode == "not_markdown":
        # Changed input forces a fresh chunk-format decision.
        second.store.documents["fake", "D"] = replace(second.store.documents["fake", "D"], chunk_input_hash="changed")
    if mode == "screen":
        from qello_knowledge.security import screen

        actual = screen._screen_content

        def judge(content, item, *args):
            if item.source_id == "D":
                raise ValueError("synthetic failure")
            return actual(content, item, *args)

        monkeypatch.setattr(screen, "_screen_content", judge)
    result = run_sync(second.targets, second.deps, SyncOptions())
    row = second.store.load_documents("fake")["D"]
    assert row.takedown_reason == expected
    if expected is None:
        assert row.status == "active"
    if mode == "stopped":
        assert result.status == "stopped"


@pytest.mark.parametrize("mode", ["secret", "excluded", "path", "unknown"])
def test_confirmed_security_takedown_is_settled_on_repeated_runs(mode):
    from qello_knowledge.domain.source_config import SourceScope
    from tests.unit.security.helpers import fake_config
    from tests.unit.synthetic_secrets import SYNTHETIC

    first = harness()
    run_sync(first.targets, first.deps, SyncOptions())
    kwargs = {}
    docs = DEFAULT_DOCS
    if mode == "secret":
        docs = {**docs, **{key: SYNTHETIC["github-classic"] for key in "DE"}}
    elif mode == "excluded":
        kwargs["config"] = fake_config(scope=SourceScope(("**/*.md",), ("docs/[DE].md",)))
    elif mode == "path":
        kwargs["locations"] = {key: f"secrets/{key}.md" for key in "DE"}
    else:
        kwargs["access"] = {key: None for key in "DE"}
    for confirm, expected in [(False, "stopped"), (True, "succeeded"), (False, "succeeded"), (False, "succeeded")]:
        h = harness(docs, store=first.store, **kwargs)
        before = len(h.store.results)
        result = run_sync(h.targets, h.deps, SyncOptions(confirm_takedown=confirm))
        assert result.status == expected
        if not confirm and expected == "succeeded":
            assert result.sources[0]["takedown_ratio"]["purge"] == 0
            assert result.sources[0]["counts"] == {"UNCHANGED": 3}
            assert len(h.store.results) == before + 3


def test_settled_security_takedown_still_applies_changed_reason_and_access_scope():
    from tests.unit.synthetic_secrets import SYNTHETIC

    first = harness()
    run_sync(first.targets, first.deps, SyncOptions())
    held = harness(store=first.store, access={"D": None})
    run_sync(held.targets, held.deps, SyncOptions())
    secret = harness({**DEFAULT_DOCS, "D": SYNTHETIC["github-classic"]}, store=first.store)
    result = run_sync(secret.targets, secret.deps, SyncOptions())
    assert result.sources[0]["takedowns"] == {"security_secret": 1}
    assert first.store.load_documents("fake")["D"].access_scope == "team"
    changed_scope = harness(
        {**DEFAULT_DOCS, "D": SYNTHETIC["github-classic"]},
        store=first.store,
        access={"D": {"visibility": "restricted"}},
    )
    result = run_sync(changed_scope.targets, changed_scope.deps, SyncOptions())
    assert result.sources[0]["takedowns"] == {"security_access": 1}
    assert first.store.load_documents("fake")["D"].access_scope == "restricted"
    unknown_scope = harness(store=first.store, access={"D": None})
    result = run_sync(unknown_scope.targets, unknown_scope.deps, SyncOptions())
    assert result.sources[0]["takedowns"] == {"security_access": 1}
    assert first.store.load_documents("fake")["D"].access_scope is None
