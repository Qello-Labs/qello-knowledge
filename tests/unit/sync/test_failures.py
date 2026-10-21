from dataclasses import replace

import pytest

from qello_knowledge.domain.embedding import ProviderFailureKind
from qello_knowledge.domain.store import StoreError
from qello_knowledge.embedding.fake import FakeEmbeddingProvider
from qello_knowledge.ports.embedder import ProviderFailure
from qello_knowledge.sync.run import SyncOptions, run_sync
from tests.unit.sync.helpers import DEFAULT_DOCS, harness


def run(h):
    return run_sync(h.targets, h.deps, SyncOptions())


@pytest.mark.parametrize("failure", [ProviderFailureKind.INPUT_TOO_LONG, ProviderFailureKind.BAD_RESPONSE])
def test_failed_document_keeps_previous_state_and_next_run_retries_only_it(failure):
    first = harness()
    run(first)
    previous = first.store.load_documents("fake")["B"]
    docs = {**DEFAULT_DOCS, "A": "# Changed A\n\nNew.", "B": "# Changed B\n\nNew."}
    provider = FakeEmbeddingProvider(fail_calls={2: ProviderFailure(failure)})
    second = harness(docs, store=first.store, provider=provider)
    result = run(second)
    assert result.status == "partial" and result.exit_code == 4
    assert second.store.load_documents("fake")["B"] == previous
    assert second.store.results[-1]["failure"] == failure.value
    third = harness(docs, store=first.store)
    run(third)
    assert len(third.provider.calls) == 1


def test_chunk_failure_isolated_and_recorded():
    first = harness()
    run(first)
    previous = first.store.load_documents("fake")["B"]
    second = harness({**DEFAULT_DOCS, "B": "x" * 100000}, store=first.store)
    result = run(second)
    assert result.status == "partial"
    failure = next(r for r in second.store.results if r["run_id"] == result.run_id and r["action"] == "FAIL")
    assert (failure["stage"], failure["failure"]) == ("chunk", "line_too_long")
    assert second.store.load_documents("fake")["B"] == previous


@pytest.mark.parametrize("kind", [ProviderFailureKind.PROVIDER_QUOTA, ProviderFailureKind.AUTH_CONFIG])
def test_run_exhaustion_prevents_later_provider_calls_but_applies_complete_cache(kind):
    first = harness()
    run(first)
    cached = first.store.load_documents("fake")["E"]
    first.store.documents["fake", "E"] = replace(cached, status="deleted")
    provider = FakeEmbeddingProvider(fail_calls={1: ProviderFailure(kind)})
    docs = {**DEFAULT_DOCS, "A": "# Changed A\n\nNew.", "B": "# Changed B\n\nNew."}
    second = harness(docs, store=first.store, provider=provider)
    result = run(second)
    assert result.status == "stopped" and result.exit_code == 5
    assert len(provider.calls) == 1
    assert first.store.load_documents("fake")["E"].status == "active"
    held = [r for r in first.store.results if r["run_id"] == result.run_id and r["outcome"] == "HELD"]
    assert len(held) == 1 and held[0]["failure"] == "BUDGET_EXHAUSTED"


def test_store_failure_isolated_and_recorded():
    first = harness()
    run(first)
    from qello_knowledge.sync.keys import doc_key

    first.store.failures["apply_document", doc_key("docs", "fake", "B")] = StoreError("QK-SYN-001-LEAK-MARKER")
    previous = first.store.load_documents("fake")["B"]
    second = harness({**DEFAULT_DOCS, "A": "# Changed A", "B": "# Changed B"}, store=first.store)
    assert run(second).status == "partial"
    assert first.store.load_documents("fake")["B"] == previous
    assert first.store.results[-1]["failure"] == "StoreError"


@pytest.mark.parametrize(
    "mode, expected_calls, first_processed",
    [
        ("today", 0, False),
        ("reserve", 0, False),
        ("budget", 0, False),
        ("settle", 1, True),
    ],
)
def test_ledger_failures_stop_new_requests_and_keep_complete_cache(mode, expected_calls, first_processed):
    from tests.unit.fakes import InMemoryUsageLedger

    first = harness()
    run(first)
    first.store.documents["fake", "E"] = replace(first.store.documents["fake", "E"], status="deleted")

    class Ledger(InMemoryUsageLedger):
        def today(self):
            if mode == "today":
                raise RuntimeError("QK-SYN-001-LEAK-MARKER")
            return super().today()

        def reserve(self, *args):
            if mode == "reserve":
                raise RuntimeError("QK-SYN-001-LEAK-MARKER")
            if mode == "budget":
                return None
            return super().reserve(*args)

        def settle(self, *args):
            if mode == "settle":
                raise RuntimeError("QK-SYN-001-LEAK-MARKER")
            return super().settle(*args)

    second = harness({**DEFAULT_DOCS, "A": "# Changed A", "B": "# Changed B"}, store=first.store, ledger=Ledger())
    result = run(second)
    rows = [r for r in first.store.results if r["run_id"] == result.run_id]
    assert result.status == "stopped" and len(second.provider.calls) == expected_calls
    assert any(r["doc_display"] == "A" and r["outcome"] == "PROCESSED" for r in rows) == first_processed
    assert any(r["doc_display"] == "B" and r["failure"] == "BUDGET_EXHAUSTED" for r in rows)
    assert any(r["doc_display"] == "E" and r["outcome"] == "PROCESSED" for r in rows)


@pytest.mark.parametrize("operation", ["take_down", "mark_seen"])
def test_nonprocessing_store_failure_isolated_to_document(operation):
    from qello_knowledge.sync.keys import doc_key

    first = harness()
    run(first)
    first.store.failures[operation, doc_key("docs", "fake", "D")] = StoreError("QK-SYN-001-LEAK-MARKER")
    second = harness(
        {**DEFAULT_DOCS, "A": "# Changed A"},
        store=first.store,
        access={"D": None} if operation == "take_down" else None,
    )
    result = run(second)
    assert result.status == "partial"
    rows = [row for row in first.store.results if row["run_id"] == result.run_id]
    assert sum(row["outcome"] == "FAILED" for row in rows) == 1
    assert any(row["doc_display"] == "A" and row["outcome"] == "PROCESSED" for row in rows)
    assert sum(row["outcome"] == "UNCHANGED" for row in rows) == 3
