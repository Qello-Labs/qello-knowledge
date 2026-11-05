"""`qk-index index status|activate|rollback|prune`(QK-STO-002 contracts/cli.md 2~5절, research R-15).

사전 처리(설정 점검, 현재 설정 버전, 원격 확인, 자료원 검토)는 `sync_cli.query_command`가 하고 이 모듈은 명령만 맡는다.
버전 저장소는 동기화 저장소가 내준다(`index_versions()`). 없는 대역이면 지금 키와 지금 첫 활성화만 낸다.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any

from qello_knowledge.domain.keyword_rules import index_rule_for
from qello_knowledge.domain.retrieval import RetrievalSettings
from qello_knowledge.domain.secret_rules import find_secrets
from qello_knowledge.sync.activate import activate_first_index
from qello_knowledge.sync.report import summary_values
from qello_knowledge.sync.versions import (
    RESOLUTIONS,
    VECTOR_NOTE,
    GateFacts,
    activation_conditions,
    coverage_dict,
    prune_conditions,
    reason_issue,
    rollback_conditions,
    status_view,
)

PREVIEW, APPLIED, FAILED, LOCKED, UNAVAILABLE = 4, 0, 1, 6, 2


def _error(code: int, reason: str) -> tuple[int, dict]:
    return code, {"exit_code": code, "error": reason}


def _code_defaults() -> dict[str, Any]:
    defaults = RetrievalSettings()
    return {"query_rule": defaults.query_rule, "candidates": defaults.candidates, "rrf_k": defaults.rrf_k}


def _switch_code(failed) -> int:
    """동기화 실행 중(잠금 경합이나 실행 중 기록)만 남았으면 종료 6, 그 밖은 1(contracts/cli.md 공통 종료 코드)."""
    return LOCKED if tuple(failed) == ("sync_running",) else FAILED


def _status(store, version: str, versions) -> dict:
    state = store.index_state()
    if versions is None:
        return {
            "active": state.active,
            "ready": list(state.ready),
            "current": version,
            "matches": state.active in (None, version),
        }
    mismatch = state.active is not None and state.active != version
    return status_view(
        active=state.active,
        ready=state.ready,
        current=version,
        versions=versions.versions(),
        coverage=versions.coverage(version) if mismatch else None,
        mismatch_since=versions.mismatch_since(state.active, version) if mismatch else None,
        rollback_target=versions.rollback_target(),
    )


def _activate(args, store, version, versions, *, history, gate_verifier, repo_root) -> tuple[int, dict]:
    state = store.index_state()
    if state.active is None:
        result = activate_first_index(store, args.version)  # QK-SYN-001 FR-021 그대로
        return (0 if not result.failed_conditions else 1), summary_values(result)
    if args.gate is None:
        return _error(FAILED, "gate_record_required")
    if versions is None:
        return _error(UNAVAILABLE, "store_unavailable")
    verified, gate_failed = gate_verifier(
        Path(args.gate), active=state.active, target=args.version, history=history, repo_root=repo_root
    )
    facts = GateFacts(
        failed=tuple(gate_failed),
        baseline=verified.baseline if verified else None,
        candidate_tokenizer=verified.candidate_tokenizer if verified else None,
        search=dict(verified.search) if verified else {},
        summary=dict(verified.summary) if verified else {},
    )
    defaults = _code_defaults()

    def check(snapshot):
        return activation_conditions(
            snapshot,
            version=args.version,
            gate=facts,
            keyword_rule=index_rule_for(args.version),
            code_defaults=defaults,
        )

    snapshot = versions.activation_state(args.version)
    failed = check(snapshot)
    covered = set(verified.covered_sources) if verified else set()
    value = {
        "baseline": None
        if snapshot.active is None
        else {"version": snapshot.active.id, "documents": snapshot.active.documents, "chunks": snapshot.active.chunks},
        "candidate": None
        if snapshot.target is None
        else {
            "version": snapshot.target.id,
            "documents": snapshot.target.documents,
            "chunks": snapshot.target.chunks,
            "chunks_without_vector": snapshot.target.chunks_without_vector,
        },
        "coverage": coverage_dict(snapshot.coverage),
        "failed_documents": len(snapshot.coverage.failed) if snapshot.coverage else 0,
        "purge_pending_documents": snapshot.purge_pending,
        "gate": None
        if verified is None
        else {"gate_id": verified.gate_id, "verdict": verified.verdict, **dict(verified.summary)},
        "retrieval_settings": {"policy": dict(facts.search), "code_defaults": defaults},
        "uncovered_sources": [{"name": s.name, "kind": s.kind} for s in snapshot.sources if s.name not in covered],
        "notes": [VECTOR_NOTE],
        "failed_conditions": list(failed),
        "applied": False,
    }
    if failed:
        return _switch_code(failed), value
    if not args.confirm:
        return PREVIEW, value
    result = versions.switch_active(
        args.version,
        check=check,
        kind="activation",
        gate_record_id=verified.gate_id,
        gate_record_sha256=verified.sha256,
        details={**dict(verified.summary), "gate_record_id": verified.gate_id},
    )
    if not result.applied:
        return _switch_code(result.failed_conditions), {**value, "failed_conditions": list(result.failed_conditions)}
    return APPLIED, {**value, "applied": True, "transition_id": result.transition_id}


def _rollback(args, store, version, versions) -> tuple[int, dict]:
    if versions is None:
        return _error(UNAVAILABLE, "store_unavailable")
    problem = reason_issue(args.reason, find_secrets)

    def check(snapshot):
        return rollback_conditions(
            snapshot, version=args.version, confirm_stale=args.confirm_stale, reason_problem=problem
        )

    snapshot = versions.rollback_state(args.version)
    failed = check(snapshot)
    value = {
        "target": None
        if snapshot.target is None
        else {"version": snapshot.target.id, "documents": snapshot.target.documents, "chunks": snapshot.target.chunks},
        "active": {"version": snapshot.active.id if snapshot.active else None},
        "missing_documents": snapshot.missing_documents,
        "provenance_mismatch": snapshot.provenance_mismatch,
        "purge_pending_documents": snapshot.purge_pending,
        "failed_conditions": list(failed),
        "applied": False,
    }
    if failed:
        return _switch_code(failed), value
    if not args.confirm:
        return PREVIEW, value
    result = versions.switch_active(
        args.version,
        check=check,
        kind="rollback",
        reason=args.reason,
        provenance_mismatch=snapshot.provenance_mismatch,
    )
    if not result.applied:
        return _switch_code(result.failed_conditions), {**value, "failed_conditions": list(result.failed_conditions)}
    value = {**value, "applied": True, "transition_id": result.transition_id}
    if version != args.version:
        value.update(mismatch_after=True, resolutions=list(RESOLUTIONS))
    return APPLIED, value


def _prune(args, store, version, versions) -> tuple[int, dict]:
    if versions is None:
        return _error(UNAVAILABLE, "store_unavailable")

    def check(snapshot):
        return prune_conditions(snapshot, version=args.version, confirm_rollback_target=args.confirm_rollback_target)

    snapshot = versions.prune_state(args.version)
    failed = check(snapshot)
    value = {
        "version": args.version,
        "status": snapshot.target.status if snapshot.target else None,
        "chunks_to_delete": snapshot.remaining_chunks,
        "deleted_chunks": 0,
        "pruned": bool(snapshot.target and snapshot.target.pruned_at),
        "failed_conditions": list(failed),
        "applied": False,
    }
    if failed:
        return _switch_code(failed), value
    if snapshot.target.pruned_at is not None and snapshot.remaining_chunks == 0:
        return APPLIED, value  # 이미 정리됐다. 바뀌는 것 없이 종료 0(contracts/cli.md 5절)
    if not args.confirm:
        return PREVIEW, value
    result = versions.prune(args.version, check=check)
    if not result.applied:
        return _switch_code(result.failed_conditions), {**value, "failed_conditions": list(result.failed_conditions)}
    return APPLIED, {**value, "deleted_chunks": result.deleted_chunks, "pruned": result.pruned, "applied": True}


def make_handler(*, history_factory: Callable[[Path], object], gate_verifier, repo_root: Path | None = None):
    """`query_command(index_handler=…)`에 넘길 처리기를 만든다. 게이트 확인은 `gate_verifier`로만 부른다."""

    def handle(args, store, version, label):
        opener = getattr(store, "index_versions", None)
        versions = opener() if opener is not None else None
        try:
            if args.index_command == "status":
                return 0, _status(store, version, versions)
            if args.index_command == "activate":
                root = Path(repo_root or Path.cwd())
                return _activate(
                    args,
                    store,
                    version,
                    versions,
                    history=history_factory(root),
                    gate_verifier=gate_verifier,
                    repo_root=root,
                )
            if args.index_command == "rollback":
                return _rollback(args, store, version, versions)
            return _prune(args, store, version, versions)
        finally:
            if versions is not None:
                versions.close()

    return handle
