"""동기화 경계의 메모리 구현. 장애는 문서 상태를 바꾸기 전에 주입한다."""

from dataclasses import replace

from qello_knowledge.domain.store import StoreError, validate_vector
from qello_knowledge.domain.sync import Action, DocumentOutcome
from qello_knowledge.ports.sync import IndexState, StoredDocument


class MemorySyncStore:
    def __init__(self):
        self.documents = {}
        self.chunks = {}
        self.embeddings = {}
        self.sources = {}
        self.runs = {}
        self.results = []
        self.calls = []
        self.failures = {}
        self.indexes = {}

    @property
    def writes(self):
        return len(self.calls)

    def _write(self, operation, doc=None):
        if doc is not None and (operation, doc.doc_key) in self.failures:
            raise self.failures[operation, doc.doc_key]
        self.calls.append((operation, doc.doc_key if doc else None))

    def index_state(self):
        return IndexState(
            next((i for i, s in self.indexes.items() if s == "active"), None),
            tuple(sorted(i for i, s in self.indexes.items() if s == "ready")),
        )

    def ensure_index_version(self, spec):
        self._write("ensure_index_version")
        self.indexes.setdefault(spec.id, "ready")
        return spec.id

    def load_documents(self, kind):
        return {sid: row for (k, sid), row in self.documents.items() if k == kind}

    def load_sources(self):
        return dict(self.sources)

    def begin_run(self, run, source_names):
        self._write("begin_run")
        self.runs[run.run_id] = {"status": "running", "sources": {}, "info": run}

    def _record(self, run, doc, action, outcome, artifact_id=None):
        if any(r["run_id"] == run and r["doc_key"] == doc.doc_key and r["action"] == action for r in self.results):
            raise StoreError("duplicate result")
        self.results.append(
            dict(
                run_id=run,
                doc_key=doc.doc_key,
                action=action,
                outcome=outcome,
                source_name=doc.source_name,
                doc_display=doc.display,
                artifact_id=artifact_id or doc.artifact_id,
                change_reason=doc.change_reason,
                stage=doc.stage,
                failure=doc.failure,
                takedown_reason=doc.takedown_reason,
                rule=doc.rule,
                lines=list(doc.lines),
            )
        )

    def apply_document(self, run, doc, artifact, version, chunks):
        self._write("apply_document", doc)
        r = artifact.record
        key = r.source_kind, r.source_id
        previous = self.documents.get(key)
        identity = previous.artifact_id if previous else len(self.documents) + 1
        pending = tuple(v for v in previous.purge_pending if v != version) if previous else ()
        row = StoredDocument(
            artifact_id=identity,
            source_id=r.source_id,
            source_name=artifact.source_name,
            source_kind=r.source_kind,
            location=artifact.location,
            chunk_input_hash=artifact.chunk_input_hash,
            processed_chunking_version=artifact.chunking_version,
            processed_index_version=version,
            processed_outcome=artifact.processed_outcome,
            last_seen_version=r.source_version,
            last_seen_at=r.collected_at,
            source_url=r.source_url,
            source_version=r.source_version,
            content_hash=r.content_hash,
            collected_at=r.collected_at,
            access_scope="team",
            purge_pending=pending,
            purge_reason=previous.purge_reason if pending else None,
        )
        # 결과 충돌도 실제 반영 전 검사한다.
        self._record(
            run, doc, Action.PROCESS, DocumentOutcome.PROCESSED if chunks else DocumentOutcome.PROCESSED_EMPTY, identity
        )
        self.documents[key] = row
        self.chunks[identity, version] = tuple(chunks)
        return identity

    def mark_seen(self, run, docs, version, at):
        documents, results = dict(self.documents), list(self.results)
        try:
            for doc in docs:
                self._write("mark_seen", doc)
                key = next(k for k, r in self.documents.items() if r.artifact_id == doc.artifact_id)
                self._record(run, doc, Action.UNCHANGED, DocumentOutcome.UNCHANGED)
                self.documents[key] = replace(self.documents[key], last_seen_version=version, last_seen_at=at)
        except StoreError:
            self.documents, self.results = documents, results
            raise

    def record_outcome(self, run, doc, action, outcome):
        self._write("record_outcome", doc)
        self._record(run, doc, action, outcome)

    def finish_source(self, run, name, status, summary):
        self._write("finish_source")
        self.runs[run]["sources"][name] = summary

    def finish_run(self, run, status, summary):
        self._write("finish_run")
        self.runs[run].update(status=status, summary=summary)

    def find_embeddings(self, refs):
        return {r: self.embeddings[r] for r in refs if r in self.embeddings}

    def put_embedding(self, ref, vector):
        validate_vector(vector)
        self._write("put_embedding")
        self.embeddings.setdefault(ref, tuple(vector))

    def take_down(self, run, doc, reason, access_scope, delete_bodies):
        self._write("take_down", doc)
        key = next(k for k, r in self.documents.items() if r.artifact_id == doc.artifact_id)
        previous = self.documents[key]
        pending = previous.purge_pending
        purge_reason = previous.purge_reason
        if reason.is_security:
            if delete_bodies:
                self.chunks = {k: v for k, v in self.chunks.items() if k[0] != doc.artifact_id}
            pending = tuple(v for (i, v), chunks in self.chunks.items() if i == doc.artifact_id and chunks)
            purge_reason = reason if pending else None
        self._record(run, doc, Action.TAKE_DOWN, DocumentOutcome.TAKEN_DOWN)
        self.documents[key] = replace(
            previous,
            status="deleted",
            takedown_reason=reason,
            purge_pending=pending,
            purge_reason=purge_reason,
            access_scope={"TEAM": "team", "RESTRICTED": "restricted", "UNKNOWN": None}.get(access_scope)
            if reason.is_security
            else previous.access_scope,
        )

    def purge_pending_bodies(self, run, doc):
        self._write("purge_pending_bodies", doc)
        key = next(k for k, r in self.documents.items() if r.artifact_id == doc.artifact_id)
        previous = self.documents[key]
        self._record(run, doc, Action.PURGE, DocumentOutcome.PURGED)
        self.chunks = {
            k: v for k, v in self.chunks.items() if k[0] != doc.artifact_id or k[1] not in previous.purge_pending
        }
        self.documents[key] = replace(previous, purge_pending=(), purge_reason=None)

    def try_lock(self, kinds):
        from types import SimpleNamespace

        return SimpleNamespace(close=lambda: None)

    def register_origin(self, name, kind, scope, origin):
        from qello_knowledge.ports.sync import StoredSource

        if name in self.sources:
            return
        if any(s.source_kind == kind for s in self.sources.values()):
            raise StoreError("source kind exists")
        self._write("register_origin")
        self.sources[name] = StoredSource(name, kind, scope, origin.origin_id, origin.origin_name)
