"""인덱스 버전 수명 저장소(QK-STO-002 research R-04·R-08·R-12·R-16·R-17, data-model 2.3).

활성화·되돌리기·정리는 동기화가 공유로 잡는 세션 advisory lock `qk-sync-index`를 배타로 잡고,
잠금 안에서 상태를 다시 읽어 넘겨받은 판정 함수로 확인한 뒤 바꾼다. 출력에 본문과 접속 정보를 담지 않는다.
"""

from __future__ import annotations

from contextlib import contextmanager

import psycopg
from psycopg.types.json import Jsonb

from qello_knowledge.adapters.postgres.connection import connect
from qello_knowledge.adapters.postgres.eval_target import _TOKENIZER, KEYWORD_INDEX, _tokenizer
from qello_knowledge.adapters.postgres.sync_store import require_schema
from qello_knowledge.domain.store import InvalidRecord, StoreError, StoreUnavailable
from qello_knowledge.ports.index_versions import (
    ActivationState,
    Coverage,
    FailedDoc,
    PruneResult,
    PruneState,
    RollbackState,
    RunRef,
    SourceRef,
    SwitchResult,
    TransitionRow,
    VersionRow,
)

LOCK_KEY = "qk-sync-index"
ACTIVE_KINDS = ("first_activation", "activation", "rollback")

_VERSIONS = """
SELECT v.id, v.embedding_model, v.dimension, v.chunking_version, v.metadata_schema_version, v.status,
       v.created_at, v.activated_at, v.pruned_at,
       (SELECT count(DISTINCT c.artifact_id) FROM qk.chunk c JOIN qk.artifact a ON a.id = c.artifact_id
        WHERE c.index_version = v.id AND a.status = 'active' AND a.access_scope = 'team'),
       (SELECT count(*) FROM qk.chunk c WHERE c.index_version = v.id),
       (SELECT count(*) FROM qk.chunk c WHERE c.index_version = v.id AND c.embedding_id IS NULL),
       EXISTS (SELECT 1 FROM qk.index_transition t WHERE t.after_active = v.id AND t.kind = ANY(%(kinds)s)),
       r.run_id, r.status, r.finished_at
FROM qk.index_version v
LEFT JOIN LATERAL (
    SELECT s.run_id, s.status, s.finished_at FROM qk.sync_run s
    WHERE s.index_version = v.id AND s.kind = 'reindex' ORDER BY s.started_at DESC, s.run_id DESC LIMIT 1
) r ON true
WHERE %(ids)s::text[] IS NULL OR v.id = ANY(%(ids)s::text[])
ORDER BY v.created_at, v.id
"""

_VISIBLE_IDS = """
SELECT DISTINCT a.id, a.processed_index_version FROM qk.artifact a JOIN qk.chunk c ON c.artifact_id = a.id
WHERE c.index_version = %s AND a.status = 'active' AND a.access_scope = 'team'
"""

_LATEST_REINDEX_RESULTS = """
SELECT DISTINCT ON (d.artifact_id) d.artifact_id, d.outcome, d.doc_display, d.stage, d.run_id
FROM qk.sync_document_result d JOIN qk.sync_run r ON r.run_id = d.run_id
WHERE r.kind = 'reindex' AND r.index_version = %s AND d.action <> 'PURGE' AND d.artifact_id = ANY(%s)
ORDER BY d.artifact_id, r.started_at DESC, r.run_id DESC
"""


def _row(values) -> VersionRow:
    (vid, model, dim, chunking, meta, status, created, activated, pruned, docs, chunks, missing, ever, *run) = values
    run_id, run_status, finished = run
    return VersionRow(
        id=vid,
        embedding_model=model,
        dimension=dim,
        chunking_version=chunking,
        metadata_schema_version=meta,
        status=status,
        created_at=created,
        activated_at=activated,
        pruned_at=pruned,
        documents=int(docs),
        chunks=int(chunks),
        chunks_without_vector=int(missing),
        ever_active=bool(ever),
        last_reindex=RunRef(run_id, run_status, finished) if run_id else None,
    )


class PostgresIndexVersionStore:
    def __init__(self, url, *, current_version=None, target="local"):
        self._url = url
        self._conn = None
        self.current_version = current_version
        self.target = target

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    @contextmanager
    def _db(self):
        try:
            if self._conn is None:
                conn = connect(self._url)
                try:
                    require_schema(conn)
                except BaseException:
                    conn.close()
                    raise
                self._conn = conn
            if self._conn.closed:
                raise StoreUnavailable("index version connection closed")
            yield self._conn
        except (psycopg.IntegrityError, psycopg.DataError):
            raise InvalidRecord("index version record rejected") from None
        except psycopg.OperationalError:
            raise StoreUnavailable("index version store unavailable") from None
        except psycopg.Error:
            raise StoreError("index version store error") from None

    # 읽기 -----------------------------------------------------------------

    @staticmethod
    def _rows(conn, ids=None) -> tuple[VersionRow, ...]:
        rows = conn.execute(_VERSIONS, {"kinds": list(ACTIVE_KINDS), "ids": list(ids) if ids else None}).fetchall()
        return tuple(_row(r) for r in rows)

    def _one(self, conn, version) -> VersionRow | None:
        rows = self._rows(conn, [version]) if version else ()
        return rows[0] if rows else None

    @staticmethod
    def _active_id(conn) -> str | None:
        row = conn.execute("SELECT id FROM qk.index_version WHERE status = 'active'").fetchone()
        return row[0] if row else None

    @staticmethod
    def _sync_running(conn) -> bool:
        return bool(conn.execute("SELECT EXISTS (SELECT 1 FROM qk.sync_run WHERE status = 'running')").fetchone()[0])

    @staticmethod
    def _purge_pending(conn, version) -> int:
        return int(
            conn.execute("SELECT count(*) FROM qk.artifact WHERE %s = ANY(purge_pending)", (version,)).fetchone()[0]
        )

    def _coverage(self, conn, version, active) -> Coverage | None:
        if active is None or version is None:
            return None
        visible = conn.execute(_VISIBLE_IDS, (active,)).fetchall()
        ids = [r[0] for r in visible]
        covered = sum(1 for _, processed in visible if processed == version)
        latest = conn.execute(_LATEST_REINDEX_RESULTS, (version, ids)).fetchall() if ids else []
        failed = tuple(
            FailedDoc(display, stage, run_id)
            for _, outcome, display, stage, run_id in sorted(latest, key=lambda r: r[2])
            if outcome == "FAILED"
        )
        return Coverage(version, len(ids), covered, len(ids) - covered, failed)

    def versions(self):
        with self._db() as conn:
            return self._rows(conn)

    def coverage(self, version):
        with self._db() as conn:
            return self._coverage(conn, version, self._active_id(conn))

    def mismatch_since(self, active, current):
        if active is None or current is None or active == current:
            return None
        with self._db() as conn:
            row = conn.execute(
                "SELECT min(r.started_at) FROM qk.sync_run r WHERE r.index_version = %(current)s AND r.started_at > "
                "coalesce((SELECT max(t.at) FROM qk.index_transition t WHERE t.after_active = %(active)s "
                "AND t.kind = ANY(%(kinds)s)), (SELECT activated_at FROM qk.index_version WHERE id = %(active)s), "
                "'-infinity'::timestamptz)",
                {"current": current, "active": active, "kinds": list(ACTIVE_KINDS)},
            ).fetchone()
        return row[0] if row else None

    def _activation_state(self, conn, version) -> ActivationState:
        active = self._active_id(conn)
        options = conn.execute(_TOKENIZER, (KEYWORD_INDEX,)).fetchone()
        sources = conn.execute("SELECT source_name, source_kind FROM qk.sync_source ORDER BY source_name").fetchall()
        return ActivationState(
            active=self._one(conn, active),
            target=self._one(conn, version),
            current=self.current_version,
            sync_running=self._sync_running(conn),
            coverage=self._coverage(conn, version, active),
            purge_pending=self._purge_pending(conn, version),
            tokenizer=_tokenizer(options[0]) if options is not None else None,
            sources=tuple(SourceRef(str(n), str(k)) for n, k in sources),
        )

    def activation_state(self, version):
        with self._db() as conn:
            return self._activation_state(conn, version)

    def _rollback_state(self, conn, version) -> RollbackState:
        active = self._active_id(conn)
        missing = mismatch = 0
        if active is not None:
            missing = conn.execute(
                "SELECT count(DISTINCT a.id) FROM qk.artifact a JOIN qk.chunk c ON c.artifact_id = a.id "
                "AND c.index_version = %s WHERE a.status = 'active' AND a.access_scope = 'team' AND NOT EXISTS "
                "(SELECT 1 FROM qk.chunk t WHERE t.artifact_id = a.id AND t.index_version = %s)",
                (active, version),
            ).fetchone()[0]
        mismatch = conn.execute(
            "SELECT count(DISTINCT a.id) FROM qk.artifact a JOIN qk.chunk c ON c.artifact_id = a.id "
            "AND c.index_version = %s WHERE a.status = 'active' AND a.access_scope = 'team'"
            " AND c.source_version <> a.source_version",
            (version,),
        ).fetchone()[0]
        return RollbackState(
            active=self._one(conn, active),
            target=self._one(conn, version),
            current=self.current_version,
            sync_running=self._sync_running(conn),
            purge_pending=self._purge_pending(conn, version),
            missing_documents=int(missing),
            provenance_mismatch=int(mismatch),
        )

    def rollback_state(self, version):
        with self._db() as conn:
            return self._rollback_state(conn, version)

    @staticmethod
    def _rollback_target(conn) -> str | None:
        row = conn.execute(
            "SELECT v.id FROM qk.index_version v JOIN qk.index_transition t ON t.before_active = v.id "
            "AND t.kind IN ('activation', 'rollback') WHERE v.status = 'archived' AND v.pruned_at IS NULL "
            "GROUP BY v.id ORDER BY max(t.at) DESC, v.id LIMIT 1"
        ).fetchone()
        return row[0] if row else None

    def rollback_target(self):
        """정리 전 보관 버전 가운데 가장 최근에 보관된 것(research R-16 D5)."""
        with self._db() as conn:
            return self._rollback_target(conn)

    def _prune_state(self, conn, version) -> PruneState:
        remaining = conn.execute("SELECT count(*) FROM qk.chunk WHERE index_version = %s", (version,)).fetchone()[0]
        return PruneState(
            target=self._one(conn, version),
            active=self._active_id(conn),
            current=self.current_version,
            rollback_target=self._rollback_target(conn),
            remaining_chunks=int(remaining),
            sync_running=self._sync_running(conn),
        )

    def prune_state(self, version):
        with self._db() as conn:
            return self._prune_state(conn, version)

    def transitions(self, version=None):
        with self._db() as conn:
            rows = conn.execute(
                "SELECT id, kind, at, version, before_active, after_active, documents, chunks, target, gate_record_id,"
                " gate_record_sha256, reason, provenance_mismatch, deleted_chunks, details FROM qk.index_transition"
                " WHERE %(v)s::text IS NULL OR version = %(v)s ORDER BY at, id",
                {"v": version},
            ).fetchall()
        return tuple(TransitionRow(*r) for r in rows)

    # 쓰기 -----------------------------------------------------------------

    @contextmanager
    def _locked(self, conn):
        acquired = conn.execute("SELECT pg_try_advisory_lock(hashtext(%s)::bigint)", (LOCK_KEY,)).fetchone()[0]
        try:
            yield bool(acquired)
        finally:
            if acquired and not conn.closed:
                conn.execute("SELECT pg_advisory_unlock(hashtext(%s)::bigint)", (LOCK_KEY,))

    def switch_active(
        self,
        version,
        *,
        check,
        kind,
        gate_record_id=None,
        gate_record_sha256=None,
        reason=None,
        provenance_mismatch=None,
        details=None,
    ):
        if kind not in ("activation", "rollback"):
            raise ValueError("switch kind must be activation or rollback")
        with self._db() as conn, self._locked(conn) as acquired:
            if not acquired:
                return SwitchResult(False, ("sync_running",))
            with conn.transaction():
                state = (
                    self._activation_state(conn, version)
                    if kind == "activation"
                    else self._rollback_state(conn, version)
                )
                failed = tuple(check(state))
                if failed:
                    return SwitchResult(False, failed)
                before = state.active.id if state.active else None
                # 활성은 하나 이하라(유일 색인) 보관을 먼저 한다(research R-08).
                conn.execute("UPDATE qk.index_version SET status = 'archived' WHERE status = 'active'")
                conn.execute(
                    "UPDATE qk.index_version SET status = 'active', activated_at = now(), pruned_at = NULL"
                    " WHERE id = %s",
                    (version,),
                )
                row = conn.execute(
                    "INSERT INTO qk.index_transition(kind, version, before_active, after_active, documents, chunks,"
                    " target, gate_record_id, gate_record_sha256, reason, provenance_mismatch, details)"
                    " VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
                    (
                        kind,
                        version,
                        before,
                        version,
                        state.target.documents,
                        state.target.chunks,
                        self.target,
                        gate_record_id,
                        gate_record_sha256,
                        reason,
                        provenance_mismatch,
                        Jsonb(dict(details or {})),
                    ),
                ).fetchone()
                return SwitchResult(True, (), int(row[0]))

    def prune(self, version, *, check, batch_size=1000, after_batch=None):
        if type(batch_size) is not int or batch_size < 1:
            raise ValueError("positive batch size required")
        with self._db() as conn, self._locked(conn) as acquired:
            if not acquired:
                return PruneResult(False, ("sync_running",))
            state = self._prune_state(conn, version)
            failed = tuple(check(state))
            if failed:
                return PruneResult(False, failed)
            if state.target.pruned_at is not None and state.remaining_chunks == 0:
                return PruneResult(True, (), 0, True)
            # 청크를 지우기 전에 이 버전으로 처리했다는 문서 상태를 비운다. 그래야 이 버전을 다시 쓸 때(재사용 전환)
            # 재색인이 모든 문서를 다시 처리하고, 중단돼도 덮음이 청크 없는 문서를 세지 않는다(구현 검토 1번, R-06).
            with conn.transaction():
                conn.execute(
                    "UPDATE qk.artifact SET processed_index_version = NULL WHERE processed_index_version = %s",
                    (version,),
                )
                # 정리 시작을 표시한다. 중단돼도 되돌리기(`pruned`)가 청크 일부가 지워진 버전을 쓰지 않는다
                # (구현 검토 2차 1번). 마지막 트랜잭션이 완료 시각으로 다시 쓴다.
                conn.execute(
                    "UPDATE qk.index_version SET status = 'archived', pruned_at = coalesce(pruned_at, now())"
                    " WHERE id = %s",
                    (version,),
                )
            deleted = 0
            while True:
                with conn.transaction():
                    count = conn.execute(
                        "DELETE FROM qk.chunk WHERE id IN (SELECT id FROM qk.chunk WHERE index_version = %s"
                        " ORDER BY id LIMIT %s)",
                        (version, batch_size),
                    ).rowcount
                deleted += count
                if count == 0:
                    break
                if after_batch is not None:
                    after_batch(deleted)
            with conn.transaction():
                # 본문이 사라졌으므로 모든 자료의 대기 목록에서 이 버전을 뺀다(research R-16, 제약 0004).
                conn.execute(
                    "UPDATE qk.artifact SET purge_pending = array_remove(purge_pending, %(v)s), purge_reason = CASE"
                    " WHEN array_remove(purge_pending, %(v)s) = '{}' THEN NULL ELSE purge_reason END"
                    " WHERE %(v)s = ANY(purge_pending)",
                    {"v": version},
                )
                conn.execute(
                    "UPDATE qk.index_version SET status = 'archived', pruned_at = now() WHERE id = %s", (version,)
                )
                conn.execute(
                    "INSERT INTO qk.index_transition(kind, version, before_active, after_active, documents, chunks,"
                    " target, deleted_chunks) VALUES ('prune', %s, %s, %s, %s, %s, %s, %s)",
                    (
                        version,
                        state.active,
                        state.active,
                        state.target.documents,
                        state.target.chunks,
                        self.target,
                        deleted,
                    ),
                )
            return PruneResult(True, (), deleted, True)
