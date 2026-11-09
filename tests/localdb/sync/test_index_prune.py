"""정리(QK-STO-002 SC-005, US5-2~US5-5, research R-16)."""

import psycopg
import pytest

from qello_knowledge.adapters.postgres.index_versions import PostgresIndexVersionStore
from qello_knowledge.sync.versions import prune_conditions
from tests.localdb.sync.version_setup import activate, prepare, prune, state

pytestmark = pytest.mark.localdb


@pytest.fixture
def switched(db_url, sync_store, store, monkeypatch):
    """V2 활성, V1 보관(되돌리기 대상)."""
    ready = prepare(sync_store, store, monkeypatch)
    assert activate(sync_store, ready.v2)[0] == 0
    return ready


def _chunks(db_url):
    with psycopg.connect(db_url) as conn:
        return dict(conn.execute("SELECT index_version, count(*) FROM qk.chunk GROUP BY 1").fetchall()), conn.execute(
            "SELECT count(*) FROM qk.embedding"
        ).fetchone()[0]


def test_refusals(db_url, sync_store, switched):
    before = state(db_url)
    assert prune(sync_store, switched.v2)[1]["failed_conditions"] == ["active_version", "current_version"]
    assert prune(sync_store, switched.v1)[1]["failed_conditions"] == ["rollback_target_unconfirmed"]
    with psycopg.connect(db_url, autocommit=True) as other:
        other.execute("SELECT pg_advisory_lock_shared(hashtext('qk-sync-index')::bigint)")
        code, value = prune(sync_store, switched.v1, confirm_rollback_target=True)
    assert code == 6 and value["failed_conditions"] == ["sync_running"]
    assert state(db_url) == before


def test_preview_then_prune_keeps_other_versions_and_vectors(db_url, sync_store, switched):
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(
            "UPDATE qk.artifact SET purge_pending=ARRAY[%s], purge_reason='security_secret' WHERE source_id='A'",
            (switched.v1,),
        )
        conn.execute(
            "UPDATE qk.artifact SET purge_pending=ARRAY[%s,%s], purge_reason='security_secret' WHERE source_id='B'",
            (switched.v1, "iv-elsewhere"),
        )
    chunks, vectors = _chunks(db_url)
    code, value = prune(sync_store, switched.v1, confirm=False, confirm_rollback_target=True)
    assert code == 4 and value["chunks_to_delete"] == chunks[switched.v1] and _chunks(db_url) == (chunks, vectors)
    code, value = prune(sync_store, switched.v1, confirm_rollback_target=True)
    assert code == 0 and value["deleted_chunks"] == chunks[switched.v1] and value["pruned"] is True
    after, after_vectors = _chunks(db_url)
    assert switched.v1 not in after and after[switched.v2] == chunks[switched.v2] and after_vectors == vectors
    with psycopg.connect(db_url) as conn:
        pending = dict(conn.execute("SELECT source_id, purge_pending FROM qk.artifact WHERE source_id IN ('A','B')"))
        reasons = dict(conn.execute("SELECT source_id, purge_reason FROM qk.artifact WHERE source_id IN ('A','B')"))
        version = conn.execute(
            "SELECT status, pruned_at IS NOT NULL FROM qk.index_version WHERE id=%s", (switched.v1,)
        ).fetchone()
        transition = conn.execute("SELECT deleted_chunks FROM qk.index_transition WHERE kind='prune'").fetchone()
    assert pending == {"A": [], "B": ["iv-elsewhere"]} and reasons == {"A": None, "B": "security_secret"}
    assert version == ("archived", True) and transition == (chunks[switched.v1],)
    # 이미 정리됐고 남은 청크가 없으면 바뀌는 것 없이 성공한다.
    before = state(db_url)
    assert prune(sync_store, switched.v1)[0] == 0 and state(db_url) == before


def test_interrupted_prune_resumes(db_url, sync_store, switched):
    chunks, _ = _chunks(db_url)

    def check(snapshot):
        return prune_conditions(snapshot, version=switched.v1, confirm_rollback_target=True)

    def interrupt(deleted):
        raise RuntimeError("중단")

    with PostgresIndexVersionStore(db_url, current_version=switched.v2) as versions:
        with pytest.raises(RuntimeError):
            versions.prune(switched.v1, check=check, batch_size=2, after_batch=interrupt)
    left, _ = _chunks(db_url)
    assert left[switched.v1] == chunks[switched.v1] - 2
    with PostgresIndexVersionStore(db_url, current_version=switched.v2) as versions:
        result = versions.prune(switched.v1, check=check, batch_size=2)
    assert result.applied and result.deleted_chunks == chunks[switched.v1] - 2
    assert switched.v1 not in _chunks(db_url)[0]


def test_reused_pruned_version_is_reprocessed_before_activation(db_url, sync_store, store, monkeypatch):
    """정리한 준비 버전으로 설정이 돌아오면 재색인이 모든 문서를 다시 처리한다(구현 검토 1번, research R-06)."""
    from qello_knowledge.sync.run import SyncOptions, run_sync
    from tests.localdb.sync.version_setup import DOCS, NEW_CHUNKING
    from tests.unit.sync.helpers import harness

    ready = prepare(sync_store, store, monkeypatch)  # V1 활성, V2 재색인 완료
    sync_store.current_version = "iv-some-other-setting"  # 설정이 V3로 바뀌어 V2는 정리 대상
    assert prune(sync_store, ready.v2)[0] == 0
    with psycopg.connect(db_url) as conn:
        assert conn.execute(
            "SELECT count(*) FROM qk.artifact WHERE processed_index_version=%s", (ready.v2,)
        ).fetchone() == (0,)
    sync_store.current_version = ready.v2  # 설정이 V2 재료로 돌아온다
    h = harness(DOCS, store=sync_store, cache_store=store, chunking=NEW_CHUNKING)
    result = run_sync(h.targets, h.deps, SyncOptions(reindex=True))
    assert result.status == "succeeded" and result.sources[0]["counts"] == {"PROCESS": len(DOCS)}
    code, value = activate(sync_store, ready.v2, confirm=False)
    assert code == 4 and value["coverage"]["covered"] == value["candidate"]["documents"] == len(DOCS)


def test_interrupted_prune_of_ready_version_uncovers_documents(db_url, sync_store, store, monkeypatch):
    ready = prepare(sync_store, store, monkeypatch)
    sync_store.current_version = "iv-some-other-setting"

    def check(snapshot):
        return prune_conditions(snapshot, version=ready.v2, confirm_rollback_target=False)

    def interrupt(deleted):
        raise RuntimeError("중단")

    with PostgresIndexVersionStore(db_url, current_version="iv-some-other-setting") as versions:
        with pytest.raises(RuntimeError):
            versions.prune(ready.v2, check=check, batch_size=2, after_batch=interrupt)
    with PostgresIndexVersionStore(db_url, current_version=ready.v2) as versions:
        coverage = versions.coverage(ready.v2)
    assert coverage.covered == 0  # 청크가 일부 지워진 버전을 처리 완료로 세지 않는다


def test_interrupted_prune_blocks_rollback_until_finished(db_url, sync_store, switched):
    """정리가 중단된 보관 버전은 되돌리기 대상이 아니다(구현 검토 2차 1번). 다시 실행하면 끝난다."""
    from tests.localdb.sync.version_setup import rollback

    def check(snapshot):
        return prune_conditions(snapshot, version=switched.v1, confirm_rollback_target=True)

    def interrupt(deleted):
        raise RuntimeError("중단")

    with PostgresIndexVersionStore(db_url, current_version=switched.v2) as versions:
        with pytest.raises(RuntimeError):
            versions.prune(switched.v1, check=check, batch_size=2, after_batch=interrupt)
    before = state(db_url)
    code, value = rollback(sync_store, switched.v1)
    assert code == 1 and value["failed_conditions"] == ["pruned"] and state(db_url) == before
    code, value = prune(sync_store, switched.v1)  # 되돌리기 대상이 아니게 됐으므로 별도 확인 옵션 없이 끝낸다
    assert code == 0 and value["pruned"] is True and switched.v1 not in _chunks(db_url)[0]
