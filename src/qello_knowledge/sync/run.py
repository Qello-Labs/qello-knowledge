"""동기화 실행의 순서와 의존성 조립 경계."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from secrets import token_hex

from qello_knowledge.chunking.version import index_chunking_version
from qello_knowledge.domain.embedding import MODELS, EmbedError
from qello_knowledge.domain.store import StoreError, StoreUnavailable
from qello_knowledge.domain.sync import Action, HoldReason, SyncRunResult
from qello_knowledge.ports.sync import IndexSpec, RunInfo
from qello_knowledge.sync.decide import constrain
from qello_knowledge.sync.execute import execute_source
from qello_knowledge.sync.identity import select_targets
from qello_knowledge.sync.keys import index_version_id, metadata_schema_version, scope_key
from qello_knowledge.sync.plan import plan_source
from qello_knowledge.sync.preview import embedding_request
from qello_knowledge.sync.report import source_summary
from qello_knowledge.sync.versions import RESOLUTIONS, coverage_dict


@dataclass(frozen=True)
class SyncOptions:
    trigger: str = "manual"
    target: str = "local"
    confirm_takedown: bool = False
    allow_partial_budget: bool = False
    source: str | None = None
    reindex: bool = False  # 사람이 시작하는 재색인(QK-STO-002 FR-004, research R-02)

    def __post_init__(self):
        if self.reindex and self.trigger == "schedule":
            raise ValueError("reindex is never scheduled")
        if self.reindex and self.source is not None:
            raise ValueError("reindex covers every source")


@dataclass(frozen=True)
class SyncDependencies:
    store: object
    cache_store: object
    embedder: object
    policy: object
    chunking_settings: object
    clock: object
    preflight: object = None
    code_chunking: object = None  # 코드 청킹 설정. `None`이면 꺼짐(QK-CHK-001 research R-09)
    confluence: bool = False  # 활성 Confluence 자료원이나 그 등록 이력이 있으면 참(QK-ING-003 research R-10)


def current_spec(deps):
    model = MODELS[deps.chunking_settings.model_version]
    version = index_chunking_version(deps.chunking_settings, deps.code_chunking)
    meta = metadata_schema_version(deps.code_chunking, deps.confluence)
    return IndexSpec(
        index_version_id(model.model_version, model.dimension, version, meta),
        model.model_version,
        model.dimension,
        version,
        metadata_schema_version=meta,
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


def _refused(code, reason, **extra):
    return SyncRunResult("", "stopped", (), code, {"reason": reason, **extra})


def reindex_refusal(state, spec):
    """재색인을 쓰기 전에 거부할 사유(research R-02). 없으면 `None`."""
    if state.active is None:
        return "no_active_version"
    if state.active == spec.id:
        return "not_mismatched"
    return None


def plan_all(targets, deps, spec, state, options):
    """미리 보기와 실행이 같은 계획을 쓴다. 재색인은 불일치 보류를 붙이지 않는다."""
    plans = []
    for target in targets:
        if state.active and state.active != spec.id and not options.reindex:
            target = replace(target, holds=target.holds | {HoldReason.INDEX_MISMATCH})
        plans.append(plan_source(target, deps, deps.store.load_documents(target.source_kind), spec.id, options))
    return plans


def security_takedowns(plans):
    return sum(1 for p in plans for d in p.decisions if Action.TAKE_DOWN in d.actions and d.takedown_reason.is_security)


def mismatch_coverage(store, version):
    """버전 저장소가 있으면 `version`의 덮음(research R-04). 메모리 대역에는 없다."""
    opener = getattr(store, "index_versions", None)
    if opener is None:
        return None
    try:
        versions = opener()
    except StoreError:
        return None
    try:
        return coverage_dict(versions.coverage(version))
    except StoreError:
        # 덮음은 보고용이다. 계산이 실패해도 실행 기록을 마무리한다(구현 검토 3번).
        return None
    finally:
        versions.close()


def _run_locked(targets, deps, options):
    spec = current_spec(deps)
    run_id = "sync-" + datetime.now(UTC).strftime("%Y%m%dT%H%M%S") + "-" + token_hex(4)
    exhausted = [False]
    estimate = None
    if options.reindex:
        state = deps.store.index_state()
        refusal = reindex_refusal(state, spec)
        if refusal:
            return _refused(1, refusal)
        plans = plan_all(targets, deps, spec, state, options)
        try:
            estimate = deps.embedder.preview(
                embedding_request(plans, spec.embedding_model, run_id, options.allow_partial_budget)
            )
        except EmbedError:
            exhausted[0] = True
            plans = [replace(p, holds=p.holds | {HoldReason.BUDGET_EXHAUSTED}) for p in plans]
        else:
            if not estimate.runnable and not options.allow_partial_budget:
                # 기본은 실행하지 않는다(FR-006). 보안 내림은 다음 예약 실행이 한다(research R-02).
                return _refused(
                    5,
                    "budget_exceeded",
                    security_takedowns=security_takedowns(plans),
                    note="security takedowns are applied by the next scheduled sync",
                )
    deps.store.begin_run(
        RunInfo(
            run_id,
            options.trigger,
            options.target,
            deps.policy.version,
            spec.chunking_version,
            spec.id,
            tuple(t.source_kind for t in targets),
            kind="reindex" if options.reindex else "sync",
        ),
        [t.source_name for t in targets],
    )
    if options.reindex:
        deps.store.prepare_candidate(spec, target=options.target)
    else:
        state = deps.store.index_state()
        if state.active is None:
            deps.store.ensure_index_version(spec)
        plans = plan_all(targets, deps, spec, state, options)
        try:
            estimate = deps.embedder.preview(
                embedding_request(plans, spec.embedding_model, run_id, options.allow_partial_budget)
            )
        except EmbedError:
            exhausted[0] = True
            plans = [replace(p, holds=p.holds | {HoldReason.BUDGET_EXHAUSTED}) for p in plans]
    sources = []
    if estimate is not None:
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
    if options.reindex:
        summary["kind"] = "reindex"
        summary["reindex"] = {"candidate": spec.id, "coverage": mismatch_coverage(deps.store, spec.id)}
    elif state.active and state.active != spec.id:
        summary["index_mismatch"] = {
            "active": state.active,
            "current": spec.id,
            "coverage": mismatch_coverage(deps.store, spec.id),
            "resolutions": list(RESOLUTIONS),
        }
    deps.store.finish_run(run_id, status, summary)
    return SyncRunResult(run_id, status, tuple(sources), {"succeeded": 0, "partial": 4, "stopped": 5}[status], summary)
