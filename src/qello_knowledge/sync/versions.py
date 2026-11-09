"""인덱스 버전 수명 판단(QK-STO-002 data-model 2.2~2.4). 저장소가 돌려준 스냅샷만 읽는 순수 함수다.

게이트 확인 결과는 조건 이름과 값(문자열·정수)으로 받는다. 이 모듈은 `gate`·`evaluation`을 가져오지 않는다
(tasks 공통 규칙 "경계", 기존 `sync/**` 경계 검사).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

RESOLUTIONS = ("reindex_gate_activate", "redeploy_active_settings")
RESOLUTION_TEXT = {
    "reindex_gate_activate": (
        "재색인(qk-index run --reindex) → 평가 게이트(qk-dev eval gate) → 활성화(qk-index index activate)"
    ),
    "redeploy_active_settings": "설정을 지금 활성 버전의 설정으로 되돌려 배포한다",
}
VECTOR_NOTE = (
    "vector_ann_shared: 벡터 근사 색인을 모든 버전이 함께 써서, 임베딩 입력이 바뀐 재색인은 활성 버전 벡터 검색 결과를 "
    "근사 오차 범위에서 바꿀 수 있다(research R-01)"
)
MAX_REASON = 200


def coverage_dict(coverage) -> dict | None:
    if coverage is None:
        return None
    return {
        "version": coverage.version,
        "visible": coverage.visible,
        "covered": coverage.covered,
        "remaining": coverage.remaining,
        "failed": [{"display": f.display, "stage": f.stage, "run_id": f.run_id} for f in coverage.failed],
    }


def estimated_days(estimated: float, remaining_today: float, daily_budget: float) -> int | None:
    """예산 안에서 끝내는 데 필요한 실행 일수(research R-05). 일일 색인 예산이 0이면 끝낼 수 없어 `None`."""
    if estimated <= 0 or estimated <= remaining_today:
        return 1
    if daily_budget <= 0:
        return None
    rest = estimated - max(remaining_today, 0)
    return 1 + int(-(-rest // daily_budget))


@dataclass(frozen=True)
class GateFacts:
    """활성화가 게이트 기록에서 확인한 값. `failed`는 게이트 쪽 조건 이름(`gate_*`)."""

    failed: tuple[str, ...] = ()
    baseline: str | None = None  # 게이트 기록의 기준 인덱스 버전. 잠금 안에서 지금 활성 버전과 다시 비교한다
    candidate_tokenizer: str | None = None
    search: Mapping[str, Any] = field(default_factory=dict)  # 정책의 요청 단위 검색 설정
    summary: Mapping[str, Any] = field(default_factory=dict)


def activation_conditions(
    state,
    *,
    version: str,
    gate: GateFacts,
    keyword_rule: str,
    code_defaults: Mapping[str, Any],
) -> tuple[str, ...]:
    """FR-021 조건 (1)~(11)을 계산한다. 채우지 못한 조건 이름을 모두 돌려준다."""
    if state.active is None:
        return ("no_active_version",)
    failed: list[str] = []
    target = state.target
    if version != state.current:
        failed.append("current_version")  # (1)
    if target is None or target.status != "ready":
        failed.append("ready_version")  # (1)
    last = target.last_reindex if target else None
    if last is None or last.status != "succeeded":
        failed.append("last_reindex")  # (2)
    coverage = state.coverage
    if coverage is None or coverage.covered < coverage.visible:
        failed.append("coverage")  # (3)
    if coverage is not None and coverage.failed:
        failed.append("failed_documents")  # (3)
    if target is not None and target.chunks_without_vector:
        failed.append("missing_vectors")  # (4)
    if target is None or target.documents < 1:
        failed.append("visible_documents")  # (5)
    gate_failed = list(gate.failed)
    if gate.baseline is not None and gate.baseline != state.active.id and "gate_baseline" not in gate_failed:
        gate_failed.append("gate_baseline")  # (6) 잠금 안에서 다시 확인한다(FR-003)
    failed.extend(name for name in gate_failed if name not in failed)  # (6)
    if keyword_rule == "unknown":
        failed.append("keyword_rule")  # (7)
    readable = gate.candidate_tokenizer is not None or bool(gate.search)  # 기록을 읽지 못하면 (8)(9)는 판단하지 않는다
    if readable and state.tokenizer != gate.candidate_tokenizer:
        failed.append("tokenizer")  # (8)
    if readable and any(
        gate.search.get(key) != code_defaults.get(key) for key in ("query_rule", "candidates", "rrf_k")
    ):
        failed.append("retrieval_settings")  # (9)
    if not readable and not gate_failed:
        failed.append("gate_integrity")
    if state.purge_pending:
        failed.append("purge_pending")  # (10)
    if state.sync_running:
        failed.append("sync_running")  # (11)
    return tuple(failed)


def reason_issue(reason: str | None, find_secrets) -> str | None:
    if reason is None or not reason.strip() or len(reason) > MAX_REASON:
        return "reason_required"
    if find_secrets(reason):
        return "reason_secret"
    return None


def rollback_conditions(state, *, version: str, confirm_stale: bool, reason_problem: str | None) -> tuple[str, ...]:
    """FR-023·FR-024 되돌리기 조건."""
    failed: list[str] = []
    if reason_problem:
        failed.append(reason_problem)
    if state.active is None:
        return (*failed, "no_active_version")
    target = state.target
    if target is None or target.status != "archived":
        failed.append("not_archived")
    if target is not None and target.pruned_at is not None:
        failed.append("pruned")
    if target is None or not target.ever_active:
        failed.append("never_active")
    if state.purge_pending:
        failed.append("purge_pending")
    if state.sync_running:
        failed.append("sync_running")
    if state.provenance_mismatch and not confirm_stale:
        failed.append("provenance_unconfirmed")
    return tuple(failed)


def prune_conditions(state, *, version: str, confirm_rollback_target: bool) -> tuple[str, ...]:
    """FR-027 정리 조건. 이미 정리됐고 남은 청크가 없으면 조건을 보지 않는다(저장소가 바뀌는 것 없이 성공)."""
    target = state.target
    if target is None:
        return ("unknown_version",)  # 그런 인덱스 버전이 없다(data-model 2.4)
    if target.pruned_at is not None and state.remaining_chunks == 0:
        return ()
    failed: list[str] = []
    if version == state.active or target.status == "active":
        failed.append("active_version")
    if version == state.current:
        failed.append("current_version")
    if version == state.rollback_target and not confirm_rollback_target:
        failed.append("rollback_target_unconfirmed")
    if state.sync_running:
        failed.append("sync_running")
    return tuple(failed)


def version_dict(row, *, current: str | None, rollback_target: str | None, coverage=None) -> dict:
    prune_candidate = (
        (row.status == "ready" and row.id != current)
        or (row.status == "archived" and row.pruned_at is None)
        or (row.pruned_at is not None and row.chunks > 0)  # 정리가 중단돼 청크가 남았다
    )
    value = {
        "id": row.id,
        "status": row.status,
        "embedding_model": row.embedding_model,
        "dimension": row.dimension,
        "chunking_version": row.chunking_version,
        "metadata_schema_version": row.metadata_schema_version,
        "created_at": row.created_at,
        "activated_at": row.activated_at,
        "pruned_at": row.pruned_at,
        "documents": row.documents,
        "chunks": row.chunks,
        "last_reindex": None
        if row.last_reindex is None
        else {
            "run_id": row.last_reindex.run_id,
            "status": row.last_reindex.status,
            "finished_at": row.last_reindex.finished_at,
        },
        "ever_active": row.ever_active,
        "prune_candidate": prune_candidate,
        "rollback_target": row.id == rollback_target,
        "coverage": coverage_dict(coverage) if row.id == current and row.status == "ready" else None,
    }
    if value["coverage"] is None:
        value["coverage_note"] = "not_current_version"
    return value


def status_view(
    *,
    active: str | None,
    ready: Sequence[str],
    current: str,
    versions: Sequence = (),
    coverage=None,
    mismatch_since=None,
    rollback_target: str | None = None,
) -> dict:
    """`qk-index index status`(contracts/cli.md 2절). 지금 키를 먼저 두고 새 키를 더한다."""
    mismatch = active is not None and active != current
    return {
        "active": active,
        "ready": list(ready),
        "current": current,
        "matches": active in (None, current),
        "mismatch_since": mismatch_since if mismatch else None,
        "versions": [
            version_dict(r, current=current, rollback_target=rollback_target, coverage=coverage) for r in versions
        ],
        "coverage": coverage_dict(coverage) if mismatch else None,
        "resolutions": list(RESOLUTIONS) if mismatch else [],
    }
