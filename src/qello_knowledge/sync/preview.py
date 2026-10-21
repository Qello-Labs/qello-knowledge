"""실행과 같은 계획에 임베딩 예상량만 붙인다. 저장소 쓰기 없음."""

from dataclasses import replace

from qello_knowledge.domain.embedding import EmbedInput, EmbedPurpose, EmbedRequest
from qello_knowledge.domain.sync import Action, DocumentOutcome, HoldReason, SyncPreview
from qello_knowledge.sync.decide import constrain
from qello_knowledge.sync.execute import ExecutionResult
from qello_knowledge.sync.report import source_summary


def embedding_request(plans, model_version, run_id="preview", allow_partial=False):
    return EmbedRequest(
        tuple(
            EmbedInput(d.embedding_text, (p.source_name, doc.chunked.screened.content.location))
            for p in plans
            for doc in p.decisions
            if Action.PROCESS in doc.actions
            for d in doc.chunked.drafts
        ),
        EmbedPurpose.INDEX,
        model_version,
        run_id,
        allow_partial,
    )


def preview(plans, embedder, model_version, index_state, options):
    embedding = embedder.preview(embedding_request(plans, model_version, allow_partial=options.allow_partial_budget))
    if not embedding.runnable and not options.allow_partial_budget:
        plans = tuple(
            replace(
                p,
                holds=p.holds | {HoldReason.BUDGET_EXCEEDED},
                decisions=tuple(constrain(d, p.holds | {HoldReason.BUDGET_EXCEEDED}) for d in p.decisions),
            )
            for p in plans
        )
    outcomes = {
        Action.PROCESS: DocumentOutcome.PROCESSED,
        Action.UNCHANGED: DocumentOutcome.UNCHANGED,
        Action.TAKE_DOWN: DocumentOutcome.TAKEN_DOWN,
        Action.PURGE: DocumentOutcome.PURGED,
        Action.FAIL: DocumentOutcome.FAILED,
        Action.HOLD: DocumentOutcome.HELD,
        Action.SKIP: DocumentOutcome.SKIPPED,
    }
    sources = tuple(
        source_summary(
            p,
            ExecutionResult(
                outcomes=[(doc, action, outcomes[action]) for doc in p.decisions for action in doc.actions],
                holds=set(p.holds),
                failures=sum(Action.FAIL in doc.actions for doc in p.decisions),
            ),
        )
        for p in plans
    )
    state = dict(index_active=index_state.active is not None, active=index_state.active, ready=list(index_state.ready))
    return SyncPreview(
        sources,
        embedding,
        state,
        (embedding.runnable or options.allow_partial_budget) and not any(p.holds for p in plans),
        options.confirm_takedown,
        options.allow_partial_budget,
    )
