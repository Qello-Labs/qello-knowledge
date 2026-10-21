from dataclasses import replace

import pytest

from qello_knowledge.ports.sync import StoredSource
from qello_knowledge.sync.identity import IdentityError, select_targets
from qello_knowledge.sync.run import SyncOptions, run_sync
from tests.unit.sync.helpers import DEFAULT_DOCS, harness


def test_duplicate_kind_and_replacement_rejected_before_requests_or_writes():
    h = harness()
    other = replace(h.targets[0], source_name="other", config=replace(h.targets[0].config, name="other"))
    with pytest.raises(IdentityError):
        run_sync((*h.targets, other), h.deps, SyncOptions())
    assert h.transport.requests == [] and h.store.writes == 0
    h.store.sources["old"] = StoredSource("old", "fake", "fake:@", "old", "old")
    with pytest.raises(IdentityError):
        run_sync(h.targets, h.deps, SyncOptions())
    assert h.transport.requests == [] and h.store.writes == 0


def test_scope_change_rejected_and_removed_source_becomes_takedown_only():
    h = harness()
    h.store.sources["docs"] = StoredSource("docs", "fake", "different", "repo-1", "synthetic/docs")
    with pytest.raises(IdentityError):
        select_targets(h.targets, h.store.load_sources())
    targets = select_targets((), h.store.load_sources())
    assert len(targets) == 1 and targets[0].mode == "TAKEDOWN_ONLY"


@pytest.mark.parametrize(
    "origin",
    [
        dict(origin_id="other", origin_name="synthetic/docs", version="v2"),
        dict(origin_id="repo-1", origin_name="other", version="v2"),
        {},
    ],
)
def test_origin_mismatch_or_missing_blocks_processing_missing_and_seen_but_keeps_security(origin):
    h = harness()
    run_sync(h.targets, h.deps, SyncOptions())
    docs = {k: v for k, v in DEFAULT_DOCS.items() if k != "E"}
    second = harness({**docs, "A": "# Changed A"}, store=h.store, origin=origin, access={"D": None})
    before = len(h.store.calls)
    result = run_sync(second.targets, second.deps, SyncOptions())
    assert result.status == "stopped" and second.provider.calls == []
    assert h.store.load_documents("fake")["D"].status == "deleted"
    assert h.store.load_documents("fake")["E"].status == "active"
    assert not any(op in {"apply_document", "mark_seen"} for op, key in h.store.calls[before:])


def test_first_origin_registered_before_document_write_and_not_overwritten_after_failure():
    from qello_knowledge.domain.store import StoreUnavailable
    from qello_knowledge.sync.keys import doc_key

    h = harness()
    h.store.failures["apply_document", doc_key("docs", "fake", "A")] = StoreUnavailable("connection lost")
    with pytest.raises(StoreUnavailable):
        run_sync(h.targets, h.deps, SyncOptions())
    assert h.store.sources["docs"].origin_id == "repo-1"
    ops = [op for op, key in h.store.calls]
    assert ops.index("register_origin") < len(ops)
    second = harness(store=h.store, origin=dict(origin_id="other", origin_name="synthetic/docs", version="v2"))
    assert run_sync(second.targets, second.deps, SyncOptions()).status == "stopped"
    assert h.store.sources["docs"].origin_id == "repo-1"


@pytest.mark.parametrize("complete", [True, False])
def test_empty_listing_records_origin_without_registering_baseline(complete, monkeypatch):
    from qello_knowledge.security import screen

    actual = screen.list_all
    monkeypatch.setattr(screen, "list_all", lambda *args: replace(actual(*args), complete=complete))
    h = harness({})
    result = run_sync(h.targets, h.deps, SyncOptions())
    assert result.sources[0]["origin"] == {"origin_id": "repo-1", "origin_name": "synthetic/docs"}
    assert result.sources[0]["origin_version"] == "v1"
    assert h.store.sources == {}


def test_origin_registration_store_error_stops_source_and_closes_run_but_keeps_security(monkeypatch):
    from qello_knowledge.domain.store import StoreError
    from tests.unit.synthetic_secrets import SYNTHETIC

    first = harness()
    run_sync(first.targets, first.deps, SyncOptions())
    first.store.sources.clear()  # Existing documents without an origin baseline require registration.
    before = len(first.store.calls)
    original = first.store.load_documents("fake")
    docs = {k: v for k, v in DEFAULT_DOCS.items() if k != "E"}
    second = harness({**docs, "A": "# Changed A", "D": SYNTHETIC["github-classic"]}, store=first.store)

    def reject_registration(*args):
        raise StoreError("synthetic registration conflict")

    monkeypatch.setattr(first.store, "register_origin", reject_registration)
    result = run_sync(second.targets, second.deps, SyncOptions(confirm_takedown=True))
    assert result.status == "stopped" and result.exit_code == 5
    assert second.provider.calls == []
    assert result.sources[0]["holds"] == ["ORIGIN_MISMATCH"]
    assert first.store.runs[result.run_id]["status"] == "stopped"
    assert first.store.runs[result.run_id]["sources"]["docs"]["status"] == "stopped"
    rows = first.store.load_documents("fake")
    assert rows["D"].status == "deleted" and rows["D"].purge_pending == ()
    assert not any(key[0] == rows["D"].artifact_id for key in first.store.chunks)
    for key in "ABCE":
        assert rows[key] == original[key]
    assert not any(op in {"apply_document", "mark_seen", "purge"} for op, key in first.store.calls[before:])
    assert "synthetic registration conflict" not in str(result.summary)
