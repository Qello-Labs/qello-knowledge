from qello_knowledge.domain.chunking import ChunkingSettings
from qello_knowledge.sync.run import SyncOptions, run_sync
from tests.unit.sync.helpers import DEFAULT_DOCS, harness


def run(h):
    return run_sync(h.targets, h.deps, SyncOptions())


def test_first_sync_then_unchanged_has_zero_embedding_chunking_and_replacement(monkeypatch):
    first = harness()
    result = run(first)
    assert result.status == "succeeded"
    assert [r["outcome"] for r in first.store.results] == ["PROCESSED"] * 5
    second = harness(store=first.store)
    from qello_knowledge.sync import plan

    monkeypatch.setattr(
        plan, "chunk_screened", lambda *args: (_ for _ in ()).throw(AssertionError("unchanged chunking"))
    )
    before = len(first.store.calls)
    result = run(second)
    assert result.status == "succeeded"
    assert second.provider.calls == []
    assert not any(op == "apply_document" for op, key in second.store.calls[before:])
    assert [r["outcome"] for r in second.store.results[-5:]] == ["UNCHANGED"] * 5
    assert len([r for r in second.transport.requests if "/items/" in r.url]) == 5


def test_one_document_changed_and_new_document_only():
    first = harness()
    run(first)
    docs = {**DEFAULT_DOCS, "B": "# Changed B\n\nUpdated.", "F": "# New F\n\nAdded."}
    second = harness(docs, store=first.store)
    run(second)
    results = second.store.results[-6:]
    processed = {r["doc_display"]: r["change_reason"] for r in results if r["action"] == "PROCESS"}
    assert processed == {"B": "INPUT_CHANGED", "F": "NEW"}
    assert len(second.provider.calls) == 2


def test_commit_only_updates_seen_not_processed_provenance():
    first = harness()
    run(first)
    previous = first.store.load_documents("fake")["C"]
    second = harness(store=first.store, version="v2")
    run(second)
    current = first.store.load_documents("fake")["C"]
    assert current.source_version == previous.source_version == "v1"
    assert current.source_url == previous.source_url
    assert current.last_seen_version == "v2"
    assert second.provider.calls == []


def test_title_location_chunking_and_empty_are_changes():
    first = harness()
    run(first)
    second = harness(
        {**DEFAULT_DOCS, "E": ""}, store=first.store, titles={"A": "New title"}, locations={"B": "moved/B.md"}
    )
    run(second)
    reasons = {r["doc_display"]: r["change_reason"] for r in second.store.results[-5:] if r["action"] == "PROCESS"}
    assert reasons == {"A": "INPUT_CHANGED", "B": "INPUT_CHANGED", "E": "INPUT_CHANGED"}
    assert second.store.load_documents("fake")["E"].processed_outcome == "empty"
    third = harness(store=first.store, chunking=ChunkingSettings(target_tokens=500))
    run(third)
    assert any(r["change_reason"] == "CHUNKING_CHANGED" for r in third.store.results[-5:])
