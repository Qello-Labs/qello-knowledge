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


KINDS = MappingProxyType(
    {
        "github_repo_files": KindSecurityPolicy(
            "github_repo_files", "github-visibility-v1", judge_github_visibility, ("github.com",), True
        ),
        "fake": KindSecurityPolicy("fake", "fake-visibility-v1", judge_fake_visibility, ("fake.invalid",), False),
    }
)
