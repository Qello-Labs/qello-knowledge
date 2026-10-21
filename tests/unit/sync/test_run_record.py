import json
import logging

from qello_knowledge.domain.store import StoreError
from qello_knowledge.sync.keys import doc_key
from qello_knowledge.sync.report import run_dict
from qello_knowledge.sync.run import SyncOptions, run_sync
from tests.unit.sync.helpers import DEFAULT_DOCS, harness
from tests.unit.synthetic_secrets import SYNTHETIC


def test_run_summary_matches_result_rows_and_includes_all_stages():
    h = harness()
    result = run_sync(h.targets, h.deps, SyncOptions())
    summary = result.sources[0]
    assert summary["counts"] == {"PROCESS": 5}
    assert summary["embedding"]["requested"] == 5
    assert summary["collection"]["processed"] == 5
    assert "items" not in summary["collection"]
    assert summary["filter"]["by_verdict"] == {"PASSED": 5}
    assert summary["chunking"]["chunk_count"] == 5
    assert len(h.store.results) == 5


def test_body_and_error_messages_never_enter_records_json_or_logs(caplog):
    caplog.set_level(logging.INFO)
    marker = "QK-SYN-001-LEAK-MARKER"
    first = harness()
    run_sync(first.targets, first.deps, SyncOptions())
    first.store.failures["apply_document", doc_key("docs", "fake", "B")] = StoreError(marker)
    h = harness({**DEFAULT_DOCS, "B": "# Synthetic\n" + marker, "D": SYNTHETIC["github-classic"]}, store=first.store)
    result = run_sync(h.targets, h.deps, SyncOptions())
    output = json.dumps(run_dict(result)) + json.dumps(h.store.results) + caplog.text
    assert marker not in output and SYNTHETIC["github-classic"] not in output
    assert result.sources[0]["security_takedowns"][0]["lines"] == [1]
    assert result.sources[0]["security_takedowns"][0]["rule"] == "github-token"


def test_cache_only_reinstatement_is_counted_in_embedding_summary():
    from dataclasses import replace

    h = harness()
    run_sync(h.targets, h.deps, SyncOptions())
    h.store.documents["fake", "B"] = replace(h.store.documents["fake", "B"], status="deleted")
    second = harness(store=h.store)
    result = run_sync(second.targets, second.deps, SyncOptions())
    assert result.sources[0]["embedding"]["requested"] == 1
    assert result.sources[0]["embedding"]["cache_hits"] == 1
    assert result.sources[0]["embedding"]["provider_calls"] == 0
    assert second.provider.calls == []


def test_redacted_new_failed_document_can_be_found_by_internal_key():
    identity = SYNTHETIC["github-classic"]
    h = harness({identity: "# Synthetic blocked", "new": "# Synthetic fresh"})
    h.store.failures["apply_document", doc_key("docs", "fake", "new")] = StoreError("private failure")
    result = run_sync(h.targets, h.deps, SyncOptions())
    output = json.dumps(run_dict(result))
    assert identity not in output
    redacted = next(row for row in h.store.results if row["doc_key"] == doc_key("docs", "fake", identity))
    assert identity not in redacted["doc_display"]
    failed = next(row for row in h.store.results if row["outcome"] == "FAILED")
    assert failed["doc_key"] == doc_key("docs", "fake", "new")
    assert failed["doc_key"] != doc_key("docs", "fake", identity)
