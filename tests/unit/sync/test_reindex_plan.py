"""재색인 계획과 실행(QK-STO-002 research R-02·R-03, FR-004·FR-010·FR-029, US1-5·US1-6)."""

from dataclasses import replace

import pytest

from qello_knowledge.domain.source import ContentFormat
from qello_knowledge.domain.sync import Action, ChangeReason, HoldReason, TakedownReason
from qello_knowledge.sync.run import SyncOptions, current_spec, plan_all, run_sync
from tests.unit.sync.helpers import harness
from tests.unit.sync.reindex_fakes import DOCS, NEW_CHUNKING, ReindexMemoryStore, mismatched

REINDEX = SyncOptions(reindex=True)


@pytest.mark.parametrize("kwargs", [{"trigger": "schedule"}, {"source": "fake-docs"}])
def test_reindex_rejects_schedule_and_single_source(kwargs):
    with pytest.raises(ValueError):
        SyncOptions(reindex=True, **kwargs)


def test_reindex_refuses_without_active_or_without_mismatch():
    store = ReindexMemoryStore()
    h = harness(DOCS, store=store)
    result = run_sync(h.targets, h.deps, REINDEX)
    assert (result.exit_code, result.summary["reason"]) == (1, "no_active_version")
    assert store.writes == 0
    run_sync(h.targets, h.deps, SyncOptions())
    store.indexes[current_spec(h.deps).id] = "active"
    before = store.writes
    again = harness(DOCS, store=store)
    result = run_sync(again.targets, again.deps, REINDEX)
    assert (result.exit_code, result.summary["reason"]) == (1, "not_mismatched")
    assert store.writes == before


def test_reindex_processes_into_candidate_without_mismatch_hold():
    m = mismatched()
    result = run_sync(m.h.targets, m.h.deps, REINDEX)
    assert result.status == "succeeded" and result.exit_code == 0
    assert result.sources[0]["counts"] == {"PROCESS": 10} and result.sources[0]["holds"] == []
    assert m.store.indexes[m.v2] == "ready" and m.store.indexes[m.v1] == "active"
    assert list(m.store.run_kinds.values())[-1] == "reindex"
    assert result.summary["kind"] == "reindex"
    assert result.summary["reindex"]["candidate"] == m.v2
    assert result.summary["reindex"]["coverage"]["covered"] == 10
    # 이어 하기: 다시 돌리면 처리한 문서는 바뀜 없음이다.
    again = harness(DOCS, store=m.store, chunking=NEW_CHUNKING)
    result = run_sync(again.targets, again.deps, REINDEX)
    assert result.sources[0]["counts"] == {"UNCHANGED": 10}


def test_reindex_takes_down_source_missing_and_disabled_documents():
    m = mismatched()
    docs = {k: v for k, v in DOCS.items() if k != "J"}
    h = harness(docs, store=m.store, chunking=NEW_CHUNKING)
    plans = plan_all(h.targets, h.deps, current_spec(h.deps), m.store.index_state(), REINDEX)
    missing = {d.source_id: d for d in plans[0].decisions}["J"]
    assert missing.actions == (Action.TAKE_DOWN,) and missing.takedown_reason == TakedownReason.SOURCE_MISSING
    assert HoldReason.INDEX_MISMATCH not in plans[0].holds
    # 예약 실행은 같은 내림을 보류한다(D2).
    h = harness(docs, store=m.store, chunking=NEW_CHUNKING)
    held = plan_all(h.targets, h.deps, current_spec(h.deps), m.store.index_state(), SyncOptions())
    assert {d.source_id: d for d in held[0].decisions}["J"].actions == (Action.HOLD,)
    disabled = replace(h.targets[0], mode="TAKEDOWN_ONLY")
    options = SyncOptions(reindex=True, confirm_takedown=True)
    plans = plan_all((disabled,), h.deps, current_spec(h.deps), m.store.index_state(), options)
    assert {d.takedown_reason for d in plans[0].decisions} == {TakedownReason.SOURCE_DISABLED}
    assert all(d.actions == (Action.TAKE_DOWN,) for d in plans[0].decisions)


def _hide(store, name, **fields):
    key = ("fake", name)
    store.documents[key] = replace(store.documents[key], **fields)


def test_reindex_holds_documents_that_are_not_visible_now():
    m = mismatched()
    _hide(m.store, "A", status="deleted", takedown_reason="source_missing")
    _hide(
        m.store,
        "B",
        status="deleted",
        takedown_reason="security_secret",
        access_scope="team",
        purge_pending=(m.v1,),
        purge_reason="security_secret",
    )
    _hide(m.store, "C", status="deleted", takedown_reason="not_target")
    # 저장 문서 B는 보안 내림 뒤 본문 삭제 대기다. 재색인이 되살리면 V1 옛 본문이 다시 검색된다.
    plans = plan_all(m.h.targets, m.h.deps, current_spec(m.h.deps), m.store.index_state(), REINDEX)
    decisions = {d.source_id: d for d in plans[0].decisions}
    for name in "ABC":
        assert decisions[name].actions == (Action.HOLD,)
        assert decisions[name].failure == "reindex_hidden"
        assert decisions[name].change_reason is not None  # 다시 처리할 사유가 있어도 처리하지 않는다
    assert decisions["D"].actions == (Action.PROCESS,)


def _text_for(adapter, monkeypatch, name):
    original = adapter.fetch_content

    def fetched(session, config, item):
        content = original(session, config, item)
        return replace(content, content_format=ContentFormat.TEXT) if item.source_id == name else content

    monkeypatch.setattr(adapter, "fetch_content", fetched)


def test_reindex_counts_new_not_target_as_processed_and_keeps_active(monkeypatch):
    m = mismatched()
    _text_for(m.h.targets[0].adapter, monkeypatch, "D")
    result = run_sync(m.h.targets, m.h.deps, REINDEX)
    assert result.sources[0]["counts"] == {"PROCESS": 10}
    row = m.store.documents["fake", "D"]
    assert (row.status, row.processed_outcome, row.processed_index_version) == ("active", "not_target", m.v2)
    assert m.store.chunks[row.artifact_id, m.v2] == ()
    assert m.store.chunks[row.artifact_id, m.v1]


def test_not_target_is_taken_down_by_the_next_non_reindex_run(monkeypatch):
    m = mismatched()
    _text_for(m.h.targets[0].adapter, monkeypatch, "D")
    run_sync(m.h.targets, m.h.deps, REINDEX)
    # 재색인 안에서는 처리 완료다.
    again = harness(DOCS, store=m.store, chunking=NEW_CHUNKING)
    _text_for(again.targets[0].adapter, monkeypatch, "D")
    plans = plan_all(again.targets, again.deps, current_spec(again.deps), m.store.index_state(), REINDEX)
    assert {d.source_id: d for d in plans[0].decisions}["D"].actions == (Action.UNCHANGED,)
    # 불일치 중 예약 실행은 보류, 활성화 뒤에는 지금 규칙대로 내린다.
    again = harness(DOCS, store=m.store, chunking=NEW_CHUNKING)
    _text_for(again.targets[0].adapter, monkeypatch, "D")
    held = plan_all(again.targets, again.deps, current_spec(again.deps), m.store.index_state(), SyncOptions())
    assert {d.source_id: d for d in held[0].decisions}["D"].change_reason == ChangeReason.NOT_TARGET_PENDING
    assert {d.source_id: d for d in held[0].decisions}["D"].actions == (Action.HOLD,)
    m.store.indexes[m.v1] = "archived"
    m.store.indexes[m.v2] = "active"
    after = harness(DOCS, store=m.store, chunking=NEW_CHUNKING)
    _text_for(after.targets[0].adapter, monkeypatch, "D")
    plans = plan_all(after.targets, after.deps, current_spec(after.deps), m.store.index_state(), SyncOptions())
    decision = {d.source_id: d for d in plans[0].decisions}["D"]
    assert decision.actions == (Action.TAKE_DOWN,) and decision.takedown_reason == TakedownReason.NOT_TARGET


def test_scheduled_run_keeps_mismatch_hold_and_reports_coverage():
    m = mismatched()
    run_sync(m.h.targets, m.h.deps, REINDEX)
    scheduled = harness(DOCS, store=m.store, chunking=NEW_CHUNKING)
    result = run_sync(scheduled.targets, scheduled.deps, SyncOptions(trigger="schedule"))
    assert "INDEX_MISMATCH" in result.sources[0]["holds"]
    mismatch = result.summary["index_mismatch"]
    assert (mismatch["active"], mismatch["current"]) == (m.v1, m.v2)
    assert mismatch["coverage"]["covered"] == 10
    assert mismatch["resolutions"] == ["reindex_gate_activate", "redeploy_active_settings"]
    assert "kind" not in result.summary


def test_mismatch_report_without_version_store_has_null_coverage():
    from tests.unit.sync.fake_store import MemorySyncStore

    store = MemorySyncStore()
    first = harness(DOCS, store=store)
    run_sync(first.targets, first.deps, SyncOptions())
    store.indexes[current_spec(first.deps).id] = "active"
    second = harness(DOCS, store=store, chunking=NEW_CHUNKING)
    result = run_sync(second.targets, second.deps, SyncOptions())
    assert result.summary["index_mismatch"]["coverage"] is None


@pytest.mark.parametrize("where", ["open", "query"])
def test_coverage_failure_does_not_leave_the_run_unfinished(where):
    from qello_knowledge.domain.store import StoreUnavailable

    m = mismatched()

    class Broken:
        def coverage(self, version):
            raise StoreUnavailable("coverage unavailable")

        def close(self):
            pass

    def opener():
        if where == "open":
            raise StoreUnavailable("open unavailable")
        return Broken()

    m.store.index_versions = opener
    scheduled = harness(DOCS, store=m.store, chunking=NEW_CHUNKING)
    result = run_sync(scheduled.targets, scheduled.deps, SyncOptions(trigger="schedule"))
    assert result.summary["index_mismatch"]["coverage"] is None
    assert m.store.runs[result.run_id]["status"] != "running"
