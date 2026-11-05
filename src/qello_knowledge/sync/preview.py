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


def reindex_preview(plans, embedder, spec, state, *, candidate_status, coverage, options):
    """재색인 미리 보기 값(contracts/cli.md 1절 `reindex`, research R-05). 임베딩 호출·저장소 쓰기 없음."""
    from qello_knowledge.sync.versions import estimated_days

    estimate = embedder.preview(
        embedding_request(plans, spec.embedding_model, allow_partial=options.allow_partial_budget)
    )
    decisions = [d for p in plans for d in p.decisions]
    hidden = sum(1 for d in decisions if Action.HOLD in d.actions and d.failure == "reindex_hidden")
    security = sum(1 for d in decisions if Action.TAKE_DOWN in d.actions and d.takedown_reason.is_security)
    value = {
        "candidate": spec.id,
        "candidate_status": candidate_status,
        "documents": len(decisions),
        "to_process": sum(1 for d in decisions if Action.PROCESS in d.actions),
        "embedding": {
            "requested": estimate.requested,
            "cache_hits": estimate.cache_hits,
            "to_embed": estimate.to_embed,
            "estimated_neurons": estimate.estimated_neurons,
            "basis": {
                "bytes_total": estimate.basis.bytes_total,
                "bytes_per_token": estimate.basis.bytes_per_token,
                "neurons_per_million_tokens": estimate.basis.neurons_per_million_tokens,
            },
        },
        "budget": {
            "index_budget": estimate.index_budget,
            "used_today": estimate.index_used_today,
            "remaining_today": estimate.index_remaining,
        },
        "estimated_days": estimated_days(estimate.estimated_neurons, estimate.index_remaining, estimate.index_budget),
        "coverage": coverage,
        "hidden_held": hidden,
        "security_takedowns": security,
    }
    return value, estimate.runnable or options.allow_partial_budget
