"""되돌리기(QK-STO-002 SC-002 되돌리기, US4-1~US4-6, FR-023·FR-024)."""

import psycopg
import pytest

from tests.localdb.sync.version_setup import activate, prepare, rollback, state

pytestmark = pytest.mark.localdb


@pytest.fixture
def switched(db_url, sync_store, store, monkeypatch):
    ready = prepare(sync_store, store, monkeypatch)
    assert activate(sync_store, ready.v2)[0] == 0
    return ready


def _sql(db_url, statement, params=()):
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(statement, params)


@pytest.mark.parametrize(
    ("name", "breaker"),
    [
        ("reason_required", None),
        ("not_archived", "UPDATE qk.index_version SET status='ready' WHERE id=%(v1)s"),
        ("pruned", "UPDATE qk.index_version SET pruned_at=now() WHERE id=%(v1)s"),
        ("never_active", "DELETE FROM qk.index_transition WHERE after_active=%(v1)s"),
        (
            "purge_pending",
            "UPDATE qk.artifact SET purge_pending=ARRAY[%(v1)s], purge_reason='security_secret' WHERE source_id='A'",
        ),
        (
            "sync_running",
            "INSERT INTO qk.sync_run(run_id,trigger,target,rules_version,chunking_version,index_version,status)"
            " VALUES ('sync-running','schedule','local','r','c','iv-x','running')",
        ),
        ("provenance_unconfirmed", "UPDATE qk.artifact SET source_version='v-new' WHERE source_id='A'"),
    ],
)
def test_each_condition_alone_blocks_rollback(name, breaker, db_url, sync_store, switched):
    if breaker:
        _sql(db_url, breaker, {"v1": switched.v1})
    before = state(db_url)
    code, value = rollback(sync_store, switched.v1, reason=None if name == "reason_required" else "합성 사유")
    assert code == (6 if name == "sync_running" else 1) and value["failed_conditions"] == [name]
    assert state(db_url) == before


def test_rollback_switches_and_hides_documents_taken_down_meanwhile(db_url, sync_store, store, switched):
    _sql(db_url, "UPDATE qk.artifact SET status='deleted', takedown_reason='source_missing' WHERE source_id='J'")
    code, value = rollback(sync_store, switched.v1, confirm=False)
    assert code == 4 and value["missing_documents"] == 0 and value["provenance_mismatch"] == 0
    code, value = rollback(sync_store, switched.v1)
    assert code == 0 and value["applied"] is True
    statuses, _ = state(db_url)
    assert statuses == {switched.v1: "active", switched.v2: "archived"}
    with psycopg.connect(db_url) as conn:
        row = conn.execute(
            "SELECT before_active, after_active, reason, provenance_mismatch, gate_record_id FROM qk.index_transition"
            " WHERE kind='rollback'"
        ).fetchone()
    assert row == (switched.v2, switched.v1, "합성 되돌리기 사유", 0, None)
    hits = store.search_keyword("Synthetic", 50).hits
    assert hits and all("view/J" not in h.provenance.source_url for h in hits)
    # 현재 설정 버전은 여전히 V2라 불일치를 알린다(US4-2).
    assert value["mismatch_after"] is True and value["resolutions"]


def test_stale_provenance_needs_confirmation(db_url, sync_store, switched):
    _sql(db_url, "UPDATE qk.artifact SET source_version='v-new' WHERE source_id='A'")
    code, value = rollback(sync_store, switched.v1, confirm_stale=True)
    assert code == 0
    with psycopg.connect(db_url) as conn:
        assert conn.execute("SELECT provenance_mismatch FROM qk.index_transition WHERE kind='rollback'").fetchone() == (
            1,
        )


def test_missing_documents_counted(db_url, sync_store, switched):
    _sql(
        db_url,
        "DELETE FROM qk.chunk WHERE index_version=%s AND artifact_id=(SELECT id FROM qk.artifact WHERE source_id='B')",
        (switched.v1,),
    )
    code, value = rollback(sync_store, switched.v1, confirm=False)
    assert code == 4 and value["missing_documents"] == 1
