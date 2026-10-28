"""자료원 종류별 보안 정책. 등록되지 않은 종류는 미확인이다(FR-015). ING-001 `sources/kinds.py`와 별개다."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from types import MappingProxyType

from qello_knowledge.domain.security import AccessScope
from qello_knowledge.domain.source import AccessInfo, AccessStatus


@dataclass(frozen=True)
class KindSecurityPolicy:
    kind: str
    rule_name: str
    judge: Callable[[AccessInfo], AccessScope]
    public_link_hosts: tuple[str, ...]
    source_id_is_path: bool
    opaque_item_fields: bool = False  # 판정 기록·측정 출력에서 제목·위치·링크를 비운다(QK-ING-003 R-15)
    lookup_failure_threshold: float | None = None  # 권한 조회 실패 비율 기준(QK-ING-003 FR-031, R-05)


def _visibility(access: AccessInfo) -> str | None:
    """원본 권한 원값이 정확히 `visibility` 하나일 때만 그 값을 돌려준다. 그 밖은 모두 판정 불가다."""
    if access.status != AccessStatus.PROVIDED or len(access.raw) != 1 or access.raw[0][0] != "visibility":
        return None
    return access.raw[0][1]


def judge_github_visibility(access: AccessInfo) -> AccessScope:
    # 비공개·내부 저장소를 팀 공용으로 보려면 결정 기록과 이 규칙 변경이 필요하다(FR-017).
    return AccessScope.TEAM if _visibility(access) == "public" else AccessScope.UNKNOWN


def judge_fake_visibility(access: AccessInfo) -> AccessScope:
    value = _visibility(access)
    if value == "public":
        return AccessScope.TEAM
    return AccessScope.RESTRICTED if value == "restricted" else AccessScope.UNKNOWN


_CONFLUENCE_TEAM_SPACE_TYPES = frozenset({"global", "collaboration", "knowledge_base"})
_CONFLUENCE_KEYS = {
    "team_group": ("judge_mode", "space_type", "space_status", "team_group_read", "read_restricted", "ancestor_count"),
    "site_users": (
        "judge_mode",
        "space_type",
        "space_status",
        "site_review_valid",
        "read_restricted",
        "ancestor_count",
    ),
}


def judge_confluence_access(access: AccessInfo) -> AccessScope:
    """원값만 읽는다(QK-ING-003 data-model 4절). 모양이 다르거나 모르는 값이면 미확인이다."""
    if access.status != AccessStatus.PROVIDED:
        return AccessScope.UNKNOWN
    raw = dict(access.raw)
    keys = _CONFLUENCE_KEYS.get(raw.get("judge_mode", ""))
    if keys is None or tuple(key for key, _ in access.raw) != keys:
        return AccessScope.UNKNOWN
    flag = raw.get("team_group_read", raw.get("site_review_valid"))
    if flag not in {"true", "false"} or not raw["ancestor_count"].isdigit():
        return AccessScope.UNKNOWN
    if raw["read_restricted"] in {"self", "ancestor"}:
        return AccessScope.RESTRICTED
    if (
        raw["space_type"] in _CONFLUENCE_TEAM_SPACE_TYPES
        and raw["space_status"] == "current"
        and flag == "true"
        and raw["read_restricted"] == "none"
    ):
        return AccessScope.TEAM
    return AccessScope.UNKNOWN


KINDS = MappingProxyType(
    {
        "github_repo_files": KindSecurityPolicy(
            "github_repo_files", "github-visibility-v1", judge_github_visibility, ("github.com",), True
        ),
        "fake": KindSecurityPolicy("fake", "fake-visibility-v1", judge_fake_visibility, ("fake.invalid",), False),
        # 원본 링크는 출력에서 비운다. 판정 기록은 페이지 ID만 남긴다(QK-ING-003 R-15).
        "confluence_pages": KindSecurityPolicy(
            "confluence_pages", "confluence-access-v1", judge_confluence_access, (), False, True, 0.10
        ),
    }
)
