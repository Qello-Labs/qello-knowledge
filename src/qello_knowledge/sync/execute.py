"""문서별 캐시·임베딩·원자 반영. 실행 전체 소진 상태를 유지한다."""

from dataclasses import dataclass, field, replace

from qello_knowledge.domain.embedding import (
    EmbedError,
    EmbedFailureKind,
    EmbedInput,
    EmbedPurpose,
    EmbedRequest,
    RunSummary,
)
from qello_knowledge.domain.store import ArtifactRecord, EmbeddingRef, StoreError, StoreUnavailable
from qello_knowledge.domain.sync import Action, DocumentOutcome, HoldReason, Operation, allowed
from qello_knowledge.embedding.hashing import input_hash
from qello_knowledge.ports.sync import ArtifactWrite


@dataclass
class ExecutionResult:
    embedding: list = field(default_factory=list)
    outcomes: list = field(default_factory=list)
    holds: set = field(default_factory=set)
    failures: int = 0


def execute_source(plan, target, deps, options, run_id, index_version, exhausted=None):
    exhausted = exhausted if exhausted is not None else [False]
    execution = ExecutionResult(holds=set(plan.holds))
    pending = []
    failed_documents = set()

    def store_failure(doc, error):
        if doc.doc_key not in failed_documents:
            pending.append(
                (replace(doc, stage="store", failure=type(error).__name__), Action.FAIL, DocumentOutcome.FAILED)
            )
            failed_documents.add(doc.doc_key)

    def write(doc, action, outcome, call):
        try:
            call()
            execution.outcomes.append((doc, action, outcome))
        except StoreUnavailable:
            raise
        except StoreError as error:
            store_failure(doc, error)

    for security in (True, False):
        for doc in plan.decisions:
            if Action.TAKE_DOWN in doc.actions and doc.takedown_reason.is_security == security:
                write(
                    doc,
                    Action.TAKE_DOWN,
                    DocumentOutcome.TAKEN_DOWN,
                    lambda doc=doc: deps.store.take_down(
                        run_id, doc, doc.takedown_reason, doc.access_scope, doc.delete_bodies
                    ),
                )
    for doc in plan.decisions:
        if (
            doc.doc_key not in failed_documents
            and Action.PURGE in doc.actions
            and options.confirm_takedown
            and allowed(plan.holds, Operation.PURGE)
        ):
            write(
                doc, Action.PURGE, DocumentOutcome.PURGED, lambda doc=doc: deps.store.purge_pending_bodies(run_id, doc)
            )
    for doc in plan.decisions:
        if doc.doc_key in failed_documents:
            continue
        if Action.HOLD in doc.actions:
            pending.append((doc, Action.HOLD, DocumentOutcome.HELD))
        elif Action.SKIP in doc.actions:
            pending.append((doc, Action.SKIP, DocumentOutcome.SKIPPED))
        if Action.FAIL in doc.actions:
            pending.append((doc, Action.FAIL, DocumentOutcome.FAILED))
            continue
        if Action.PROCESS not in doc.actions:
            continue
        chunked = doc.chunked
        refs = [
            EmbeddingRef(input_hash(d.embedding_text), deps.chunking_settings.model_version) for d in chunked.drafts
        ]
        try:
            found = deps.cache_store.find_embeddings(refs)
            if all(r in found for r in refs):
                execution.embedding.append(RunSummary(requested=len(refs), cache_hits=len(refs)))
            elif exhausted[0]:
                execution.holds.add(HoldReason.BUDGET_EXHAUSTED)
                pending.append(
                    (
                        replace(doc, actions=(Action.HOLD,), failure=HoldReason.BUDGET_EXHAUSTED),
                        Action.HOLD,
                        DocumentOutcome.HELD,
                    )
                )
                continue
            else:
                request = EmbedRequest(
                    tuple(
                        EmbedInput(d.embedding_text, (plan.source_name, chunked.screened.content.location))
                        for d in chunked.drafts
                    ),
                    EmbedPurpose.INDEX,
                    deps.chunking_settings.model_version,
                    run_id,
                    options.allow_partial_budget,
                )
                try:
                    result = deps.embedder.embed(request)
                except EmbedError as error:
                    exhausted[0] = True
                    execution.holds.add(HoldReason.BUDGET_EXHAUSTED)
                    pending.append(
                        (replace(doc, stage="embed", failure=error.kind.value), Action.FAIL, DocumentOutcome.FAILED)
                    )
                    continue
                execution.embedding.append(result.summary)
                failures = [item.failure for item in result.items if item.failure is not None]
                if (
                    any(
                        f
                        in {
                            EmbedFailureKind.PROVIDER_QUOTA,
                            EmbedFailureKind.INDEX_BUDGET,
                            EmbedFailureKind.USAGE_UNAVAILABLE,
                        }
                        for f in failures
                    )
                    or "usage_unavailable" in result.summary.warnings
                ):
                    exhausted[0] = True
                    execution.holds.add(HoldReason.BUDGET_EXHAUSTED)
                if failures:
                    pending.append(
                        (replace(doc, stage="embed", failure=failures[0].value), Action.FAIL, DocumentOutcome.FAILED)
                    )
                    continue
            chunks = [replace(d.chunk, embedding=ref) for d, ref in zip(chunked.drafts, refs, strict=True)]
            item, content = chunked.screened.item, chunked.screened.content
            artifact = ArtifactWrite(
                ArtifactRecord(
                    item.source_kind,
                    item.source_id,
                    item.url,
                    content.version or item.version or item.change_key,
                    content.fetched_at,
                    content.content_hash,
                    item.item_type,
                    chunked.document_title,
                    item.modified_at,
                    "team",
                ),
                plan.source_name,
                content.location,
                doc.fingerprint,
                chunked.chunking_version,
                "chunked" if chunks else "empty",
            )
            deps.store.apply_document(run_id, doc, artifact, index_version, chunks)
            execution.outcomes.append(
                (doc, Action.PROCESS, DocumentOutcome.PROCESSED if chunks else DocumentOutcome.PROCESSED_EMPTY)
            )
        except StoreUnavailable:
            raise
        except StoreError as error:
            pending.append(
                (replace(doc, stage="store", failure=type(error).__name__), Action.FAIL, DocumentOutcome.FAILED)
            )
    unchanged = [
        doc for doc in plan.decisions if Action.UNCHANGED in doc.actions and doc.doc_key not in failed_documents
    ]
    if unchanged:
        try:
            deps.store.mark_seen(run_id, unchanged, plan.origin_version, deps.clock.now())
            execution.outcomes.extend((doc, Action.UNCHANGED, DocumentOutcome.UNCHANGED) for doc in unchanged)
        except StoreUnavailable:
            raise
        except StoreError:
            # 묶음 트랜잭션은 취소됐다. 문서별로 다시 시도해 실패를 격리한다.
            for doc in unchanged:
                write(
                    doc,
                    Action.UNCHANGED,
                    DocumentOutcome.UNCHANGED,
                    lambda doc=doc: deps.store.mark_seen(run_id, [doc], plan.origin_version, deps.clock.now()),
                )
    for doc, action, outcome in pending:
        deps.store.record_outcome(run_id, doc, action, outcome)
        execution.outcomes.append((doc, action, outcome))
        execution.failures += outcome == DocumentOutcome.FAILED
    return execution
