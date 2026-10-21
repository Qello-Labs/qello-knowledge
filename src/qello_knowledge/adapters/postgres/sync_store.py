"""동기화 상태·청크·결과를 같은 트랜잭션으로 반영한다."""

from __future__ import annotations

from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from qello_knowledge.adapters.postgres.connection import connect
from qello_knowledge.adapters.postgres.store import _replace_chunk_rows
from qello_knowledge.domain.store import (
    InvalidRecord,
    StoreError,
    StoreUnavailable,
    chunk_set_hash,
    validate_artifact,
    validate_chunks,
)
from qello_knowledge.domain.sync import Action, DocumentOutcome
from qello_knowledge.ports.sync import IndexState, StoredDocument, StoredSource


class PostgresSyncStore:
    def __init__(self, url, *, current_version=None):
        self._url = url
        self._conn = None
        self.current_version = current_version

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
        if self._conn is None:
            self._conn = connect(self._url)
        # 잠금을 들고 있는 연결을 조용히 다시 연결하면 안 된다.
        if self._conn.closed:
            raise StoreUnavailable("sync connection closed")
        try:
            yield self._conn
        except (psycopg.IntegrityError, psycopg.DataError):
            raise InvalidRecord("sync record rejected") from None
        except psycopg.OperationalError:
            raise StoreUnavailable("sync store unavailable") from None
        except psycopg.Error:
            raise StoreError("sync store error") from None

    def index_state(self):
        with self._db() as conn:
            rows = conn.execute("SELECT id,status FROM qk.index_version ORDER BY id").fetchall()
        return IndexState(next((i for i, s in rows if s == "active"), None), tuple(i for i, s in rows if s == "ready"))

    def ensure_index_version(self, spec):
        with self._db() as conn, conn.transaction():
            conn.execute(
                "INSERT INTO qk.index_version(id,embedding_model,dimension,chunking_version,"
                "metadata_schema_version,status) "
                "VALUES (%s,%s,%s,%s,%s,'ready') ON CONFLICT(id) DO NOTHING",
                (spec.id, spec.embedding_model, spec.dimension, spec.chunking_version, spec.metadata_schema_version),
            )
        return spec.id

    def load_documents(self, source_kind):
        with self._db() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT id AS artifact_id,source_id,source_name,source_kind,location,chunk_input_hash,"
                "processed_chunking_version,processed_index_version,processed_outcome,last_seen_version,last_seen_at,"
                "takedown_reason,takedown_at,purge_pending,purge_reason,source_url,source_version,content_hash,"
                "collected_at,access_scope,status FROM qk.artifact WHERE source_kind=%s",
                (source_kind,),
            )
            rows = cur.fetchall()
        return {r["source_id"]: StoredDocument(**{**r, "purge_pending": tuple(r["purge_pending"])}) for r in rows}

    def load_sources(self):
        with self._db() as conn:
            rows = conn.execute(
                "SELECT source_name,source_kind,scope_key,origin_id,origin_name FROM qk.sync_source"
            ).fetchall()
        return {r[0]: StoredSource(*r) for r in rows}

    def begin_run(self, run, source_names):
        with self._db() as conn, conn.transaction():
            conn.execute(
                "UPDATE qk.sync_run_source rs SET status='unfinished' WHERE status='running' AND "
                "(source_name=ANY(%s) OR summary->>'source_kind'=ANY(%s) OR source_name IN "
                "(SELECT source_name FROM qk.sync_source WHERE source_kind=ANY(%s)))",
                (list(source_names), list(run.source_kinds), list(run.source_kinds)),
            )
            conn.execute(
                "UPDATE qk.sync_run r SET status='unfinished',finished_at=now() WHERE status='running' "
                "AND EXISTS(SELECT 1 FROM qk.sync_run_source s WHERE s.run_id=r.run_id AND s.status='unfinished') "
                "AND NOT EXISTS(SELECT 1 FROM qk.sync_run_source s WHERE s.run_id=r.run_id AND s.status='running')"
            )
            conn.execute(
                "INSERT INTO qk.sync_run(run_id,trigger,target,rules_version,chunking_version,index_version,status) "
                "VALUES (%s,%s,%s,%s,%s,%s,'running')",
                (run.run_id, run.trigger, run.target, run.rules_version, run.chunking_version, run.index_version),
            )
            for name, kind in zip(source_names, run.source_kinds, strict=True):
                conn.execute(
                    "INSERT INTO qk.sync_run_source(run_id,source_name,status,summary) VALUES (%s,%s,'running',%s)",
                    (run.run_id, name, Jsonb({"source_kind": kind})),
                )

    @staticmethod
    def _record(conn, run_id, doc, action, outcome, artifact_id=None):
        conn.execute(
            "INSERT INTO qk.sync_document_result(run_id,doc_key,action,source_name,doc_display,artifact_id,"
            "outcome,change_reason,stage,failure,takedown_reason,rule,lines) VALUES "
            "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                run_id,
                doc.doc_key,
                action,
                doc.source_name,
                doc.display,
                artifact_id if artifact_id is not None else doc.artifact_id,
                outcome,
                doc.change_reason,
                doc.stage,
                doc.failure,
                doc.takedown_reason,
                doc.rule,
                list(doc.lines),
            ),
        )

    def apply_document(self, run_id, doc, artifact, index_version, chunks):
        r = artifact.record
        validate_artifact(r)
        validate_chunks(r.source_version, chunks)
        if not artifact.location:
            raise InvalidRecord("sync location required")
        with self._db() as conn, conn.transaction():
            conn.execute(
                "SELECT id FROM qk.artifact WHERE source_kind=%s AND source_id=%s FOR UPDATE",
                (r.source_kind, r.source_id),
            )
            row = conn.execute(
                "INSERT INTO qk.artifact(source_kind,source_id,source_url,source_version,source_modified_at,"
                "collected_at,content_hash,artifact_kind,title,access_scope,source_name,location,chunk_input_hash,"
                "processed_chunking_version,processed_index_version,processed_outcome,last_seen_version,last_seen_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,'team',%s,%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT(source_kind,source_id) DO UPDATE SET source_url=EXCLUDED.source_url,"
                "source_version=EXCLUDED.source_version,source_modified_at=EXCLUDED.source_modified_at,"
                "collected_at=EXCLUDED.collected_at,content_hash=EXCLUDED.content_hash,artifact_kind=EXCLUDED.artifact_kind,"
                "title=EXCLUDED.title,access_scope='team',status='active',takedown_reason=NULL,takedown_at=NULL,"
                "source_name=EXCLUDED.source_name,location=EXCLUDED.location,chunk_input_hash=EXCLUDED.chunk_input_hash,"
                "processed_chunking_version=EXCLUDED.processed_chunking_version,processed_index_version=EXCLUDED.processed_index_version,"
                "processed_outcome=EXCLUDED.processed_outcome,last_seen_version=EXCLUDED.last_seen_version,"
                "last_seen_at=EXCLUDED.last_seen_at,updated_at=now() RETURNING id",
                (
                    r.source_kind,
                    r.source_id,
                    r.source_url,
                    r.source_version,
                    r.source_modified_at,
                    r.collected_at,
                    r.content_hash,
                    r.artifact_kind,
                    r.title,
                    artifact.source_name,
                    artifact.location,
                    artifact.chunk_input_hash,
                    artifact.chunking_version,
                    index_version,
                    artifact.processed_outcome,
                    r.source_version,
                    r.collected_at,
                ),
            ).fetchone()
            identity = row[0]
            _replace_chunk_rows(conn, identity, index_version, r.source_version, chunks)
            conn.execute(
                "UPDATE qk.artifact SET chunk_set_hash=%s WHERE id=%s",
                (chunk_set_hash(index_version, r.source_version, chunks), identity),
            )
            conn.execute(
                "UPDATE qk.artifact SET purge_pending=array_remove(purge_pending,%s),"
                "purge_reason=CASE WHEN array_remove(purge_pending,%s)='{}' THEN NULL ELSE purge_reason END "
                "WHERE id=%s",
                (index_version, index_version, identity),
            )
            outcome = DocumentOutcome.PROCESSED if chunks else DocumentOutcome.PROCESSED_EMPTY
            self._record(conn, run_id, doc, Action.PROCESS, outcome, identity)
        return identity

    def mark_seen(self, run_id, docs, version, at):
        with self._db() as conn, conn.transaction():
            for doc in docs:
                conn.execute("SELECT id FROM qk.artifact WHERE id=%s FOR UPDATE", (doc.artifact_id,))
                conn.execute(
                    "UPDATE qk.artifact SET last_seen_version=%s,last_seen_at=%s WHERE id=%s",
                    (version, at, doc.artifact_id),
                )
                self._record(conn, run_id, doc, Action.UNCHANGED, DocumentOutcome.UNCHANGED)

    def record_outcome(self, run_id, doc, action, outcome):
        with self._db() as conn, conn.transaction():
            self._record(conn, run_id, doc, action, outcome)

    def finish_source(self, run_id, source_name, status, summary):
        with self._db() as conn, conn.transaction():
            conn.execute(
                "UPDATE qk.sync_run_source SET status=%s,summary=%s,origin_version=%s,listing_complete=%s,"
                "stop_reason=%s,holds=%s,retry_at=%s WHERE run_id=%s AND source_name=%s",
                (
                    status,
                    Jsonb(summary),
                    summary.get("origin_version"),
                    summary.get("listing_complete"),
                    summary.get("stop_reason"),
                    summary.get("holds", []),
                    summary.get("retry_at"),
                    run_id,
                    source_name,
                ),
            )

    def finish_run(self, run_id, status, summary):
        with self._db() as conn, conn.transaction():
            conn.execute(
                "UPDATE qk.sync_run SET status=%s,summary=%s,finished_at=now() WHERE run_id=%s",
                (status, Jsonb(summary), run_id),
            )

    def take_down(self, run_id, doc, reason, access_scope, delete_bodies):
        with self._db() as conn, conn.transaction():
            conn.execute("SELECT id FROM qk.artifact WHERE id=%s FOR UPDATE", (doc.artifact_id,))
            scope = {"TEAM": "team", "RESTRICTED": "restricted", "UNKNOWN": None}.get(access_scope)
            conn.execute(
                "UPDATE qk.artifact SET status='deleted',takedown_reason=%s,"
                "takedown_at=now(),updated_at=now() WHERE id=%s",
                (reason, doc.artifact_id),
            )
            if reason.is_security:
                conn.execute("UPDATE qk.artifact SET access_scope=%s WHERE id=%s", (scope, doc.artifact_id))
                if delete_bodies:
                    conn.execute("DELETE FROM qk.chunk WHERE artifact_id=%s", (doc.artifact_id,))
                versions = [
                    r[0]
                    for r in conn.execute(
                        "SELECT DISTINCT index_version FROM qk.chunk WHERE artifact_id=%s ORDER BY 1",
                        (doc.artifact_id,),
                    ).fetchall()
                ]
                conn.execute(
                    "UPDATE qk.artifact SET purge_pending=%s,purge_reason=%s WHERE id=%s",
                    (versions, reason if versions else None, doc.artifact_id),
                )
            self._record(conn, run_id, doc, Action.TAKE_DOWN, DocumentOutcome.TAKEN_DOWN)

    def purge_pending_bodies(self, run_id, doc):
        with self._db() as conn, conn.transaction():
            row = conn.execute(
                "SELECT purge_pending FROM qk.artifact WHERE id=%s FOR UPDATE", (doc.artifact_id,)
            ).fetchone()
            conn.execute(
                "DELETE FROM qk.chunk WHERE artifact_id=%s AND index_version=ANY(%s)", (doc.artifact_id, row[0])
            )
            conn.execute("UPDATE qk.artifact SET purge_pending='{}',purge_reason=NULL WHERE id=%s", (doc.artifact_id,))
            self._record(conn, run_id, doc, Action.PURGE, DocumentOutcome.PURGED)

    def register_origin(self, source_name, kind, scope_key, origin):
        with self._db() as conn, conn.transaction():
            conn.execute(
                "INSERT INTO qk.sync_source(source_name,source_kind,scope_key,origin_id,origin_name) "
                "VALUES (%s,%s,%s,%s,%s) ON CONFLICT(source_name) DO NOTHING",
                (source_name, kind, scope_key, origin.origin_id, origin.origin_name),
            )

    def try_lock(self, source_kinds):
        with self._db() as conn:
            keys = []
            for key, shared in [
                ("qk-sync-index", True),
                *[(f"qk-sync-kind:{kind}", False) for kind in sorted(set(source_kinds))],
            ]:
                function = "pg_try_advisory_lock_shared" if shared else "pg_try_advisory_lock"
                acquired = conn.execute("SELECT " + function + "(hashtext(%s)::bigint)", (key,)).fetchone()[0]
                if not acquired:
                    _SyncLock(conn, keys).close()
                    return None
                keys.append((key, shared))
            return _SyncLock(conn, keys)

    def activation_check(self, version):
        with self._db() as conn:
            return self._activation_check(conn, version)

    def _activation_check(self, conn, version):
        from qello_knowledge.domain.sync import ActivationCheck

        active = conn.execute("SELECT id FROM qk.index_version WHERE status='active'").fetchone()
        ready = conn.execute("SELECT 1 FROM qk.index_version WHERE id=%s AND status='ready'", (version,)).fetchone()
        last = conn.execute(
            "SELECT status FROM qk.sync_run WHERE index_version=%s ORDER BY started_at DESC,run_id DESC LIMIT 1",
            (version,),
        ).fetchone()
        running = conn.execute("SELECT 1 FROM qk.sync_run WHERE status='running' LIMIT 1").fetchone()
        documents = conn.execute(
            "SELECT count(DISTINCT a.id) FROM qk.artifact a JOIN qk.chunk c ON c.artifact_id=a.id "
            "WHERE c.index_version=%s AND a.status='active' AND a.access_scope='team'",
            (version,),
        ).fetchone()[0]
        chunks, missing = conn.execute(
            "SELECT count(*),count(*) FILTER (WHERE embedding_id IS NULL) FROM qk.chunk WHERE index_version=%s",
            (version,),
        ).fetchone()
        failed = []
        if active:
            failed.append("active_exists")
        if version != self.current_version:
            failed.append("current_version")
        if not ready:
            failed.append("ready_version")
        if not last or last[0] != "succeeded" or running:
            failed.append("last_run")
        if not documents:
            failed.append("visible_documents")
        if missing:
            failed.append("missing_vectors")
        return ActivationCheck(version, documents, chunks, missing, last[0] if last else None, tuple(failed))

    def activate(self, version):
        from dataclasses import replace

        with self._db() as conn:
            if not conn.execute("SELECT pg_try_advisory_lock(hashtext('qk-sync-index')::bigint)").fetchone()[0]:
                return replace(self._activation_check(conn, version), failed_conditions=("sync_running",))
            try:
                with conn.transaction():
                    check = self._activation_check(conn, version)
                    if not check.failed_conditions:
                        conn.execute(
                            "UPDATE qk.index_version SET status='active',activated_at=now() WHERE id=%s", (version,)
                        )
                    return check
            finally:
                conn.execute("SELECT pg_advisory_unlock(hashtext('qk-sync-index')::bigint)")

    def list_runs(self, limit=20):
        if type(limit) is not int or limit < 1:
            raise InvalidRecord("positive limit required")
        with self._db() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT run_id,status,started_at,finished_at,summary FROM qk.sync_run "
                "ORDER BY started_at DESC LIMIT %s",
                (limit,),
            )
            return cur.fetchall()

    def run_detail(self, run_id):
        with self._db() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SELECT * FROM qk.sync_run WHERE run_id=%s", (run_id,))
            return cur.fetchone()

    def run_failures(self, run_id):
        with self._db() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute(
                "SELECT doc_key,source_name,doc_display,stage,failure FROM qk.sync_document_result "
                "WHERE run_id=%s AND outcome='FAILED' ORDER BY doc_key",
                (run_id,),
            )
            return cur.fetchall()

    def prune_runs(self, retention_days=90):
        if type(retention_days) is not int or retention_days < 1:
            raise InvalidRecord("positive retention required")
        with self._db() as conn, conn.transaction():
            return len(
                conn.execute(
                    "DELETE FROM qk.sync_run WHERE status<>'running' "
                    "AND coalesce(finished_at,started_at)<now()-make_interval(days=>%s) RETURNING run_id",
                    (retention_days,),
                ).fetchall()
            )


class _SyncLock:
    def __init__(self, conn, keys):
        self.conn = conn
        self.keys = list(keys)

    def close(self):
        keys, self.keys = self.keys, []
        if self.conn.closed:
            return
        try:
            for key, shared in reversed(keys):
                function = "pg_advisory_unlock_shared" if shared else "pg_advisory_unlock"
                self.conn.execute("SELECT " + function + "(hashtext(%s)::bigint)", (key,))
        except psycopg.OperationalError:
            return  # 서버가 끊긴 세션의 잠금은 이미 해제했다.
