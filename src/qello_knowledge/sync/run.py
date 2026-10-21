"""동기화 실행의 순서와 의존성 조립 경계."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from secrets import token_hex

from qello_knowledge.chunking.version import chunking_version
from qello_knowledge.domain.embedding import MODELS, EmbedError
from qello_knowledge.domain.store import StoreError, StoreUnavailable
from qello_knowledge.domain.sync import HoldReason, SyncRunResult
from qello_knowledge.ports.sync import IndexSpec, RunInfo
from qello_knowledge.sync.decide import constrain
from qello_knowledge.sync.execute import execute_source
from qello_knowledge.sync.identity import select_targets
from qello_knowledge.sync.keys import index_version_id, scope_key
from qello_knowledge.sync.plan import plan_source
from qello_knowledge.sync.preview import embedding_request
from qello_knowledge.sync.report import source_summary


@dataclass(frozen=True)
class SyncOptions:
    trigger: str = "manual"
    target: str = "local"
    confirm_takedown: bool = False
    allow_partial_budget: bool = False
    source: str | None = None


@dataclass(frozen=True)
class SyncDependencies:
    store: object
    cache_store: object
    embedder: object
    policy: object
    chunking_settings: object
    clock: object
    preflight: object = None


def current_spec(deps):
    model = MODELS[deps.chunking_settings.model_version]
    version = chunking_version(deps.chunking_settings)
    return IndexSpec(
        index_version_id(model.model_version, model.dimension, version), model.model_version, model.dimension, version
    )


def run_sync(targets, deps, options):
    if deps.preflight is not None:
        deps.preflight()
    selected = select_targets(targets, deps.store.load_sources(), options.source)
    deps.store.index_state()  # 쓰기 전 연결 검사
    lock = deps.store.try_lock(tuple(t.source_kind for t in selected))
    if lock is None:
        return SyncRunResult("", "stopped", (), 6, {"reason": "already_running"})
    try:
        selected = select_targets(targets, deps.store.load_sources(), options.source)
        return _run_locked(selected, deps, options)
    finally:
        lock.close()


def _run_locked(targets, deps, options):
    spec = current_spec(deps)
    run_id = "sync-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S") + "-" + token_hex(4)
    deps.store.begin_run(
        RunInfo(
            run_id,
            options.trigger,
            options.target,
            deps.policy.version,
            spec.chunking_version,
            spec.id,
            tuple(t.source_kind for t in targets),
        ),
        [t.source_name for t in targets],
    )
    state = deps.store.index_state()
    if state.active is None:
        deps.store.ensure_index_version(spec)
    sources = []
    exhausted = [False]
    plans = []
    for target in targets:
        if state.active and state.active != spec.id:
            target = replace(target, holds=target.holds | {HoldReason.INDEX_MISMATCH})
        plans.append(plan_source(target, deps, deps.store.load_documents(target.source_kind), spec.id, options))
    try:
        estimate = deps.embedder.preview(
            embedding_request(plans, spec.embedding_model, run_id, options.allow_partial_budget)
        )
    except EmbedError:
        exhausted[0] = True
        plans = [replace(p, holds=p.holds | {HoldReason.BUDGET_EXHAUSTED}) for p in plans]
    else:
        if not estimate.runnable and not options.allow_partial_budget:
            plans = [
                replace(
                    p,
                    holds=p.holds | {HoldReason.BUDGET_EXCEEDED},
                    decisions=tuple(constrain(d, p.holds | {HoldReason.BUDGET_EXCEEDED}) for d in p.decisions),
                )
                for p in plans
            ]
    for target, plan in zip(targets, plans, strict=True):
        if plan.origin_check == "REGISTER" and plan.decisions:
            try:
                deps.store.register_origin(
                    target.source_name,
                    target.source_kind,
                    scope_key(target.source_kind, target.config.scope),
                    plan.origin,
                )
            except StoreUnavailable:
                raise
            except StoreError:
                holds = plan.holds | {HoldReason.ORIGIN_MISMATCH}
                plan = replace(
                    plan,
                    origin_check="MISMATCH",
                    holds=holds,
                    decisions=tuple(constrain(d, holds) for d in plan.decisions),
                )
        execution = execute_source(plan, target, deps, options, run_id, spec.id, exhausted)
        summary = source_summary(plan, execution)
        sources.append(summary)
        deps.store.finish_source(run_id, target.source_name, summary["status"], summary)
    status = (
        "stopped"
        if any(s["status"] == "stopped" for s in sources)
        else "partial"
        if any(s["status"] == "partial" for s in sources)
        else "succeeded"
    )
    summary = {
        "trigger": options.trigger,
        "target": options.target,
        "rules_version": deps.policy.version,
        "chunking_version": spec.chunking_version,
        "index_version": spec.id,
        "index_active": state.active is not None,
        "sources": sources,
    }
    deps.store.finish_run(run_id, status, summary)
    return SyncRunResult(run_id, status, tuple(sources), {"succeeded": 0, "partial": 4, "stopped": 5}[status], summary)
