"""종류 추가는 결정 기록이 필요하다(AGENTS.md 3.1)."""

import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class ScopeCheck:
    """종류별 범위 값 검증 결과. 오류에는 값을 넣지 않고 (필드, 코드)만 담는다."""

    include: tuple[str, ...]
    exclude: tuple[str, ...]
    extra: tuple[tuple[str, str], ...]
    issues: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class SourceKindSpec:
    name: str
    requires_auth: bool
    scope_keys: tuple[str, ...]
    default_allowed_hosts: tuple[str, ...]
    extra_auth: tuple[str, ...] = ()  # `auth` 말고도 켜진 자료원에 필요한 설정 항목 이름
    scope_validator: Callable[[Mapping[str, object]], ScopeCheck] | None = None  # 없으면 공통 규칙


CONFLUENCE_DOC_TYPES = (
    "회의록",
    "용어집",
    "기능 명세",
    "설계 문서",
    "API 문서",
    "디자인 문서",
    "개발 규칙",
    "색인 안 함",
)
CONFLUENCE_JUDGE_MODES = ("team_group", "site_users")
_DIGITS = re.compile(r"[0-9]+")


def canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _confluence_scope(scope: Mapping[str, object]) -> ScopeCheck:
    """QK-ING-003 data-model 1절. 표·목록 값은 정렬된 JSON 문자열로 `extra`에 담는다."""
    issues: list[tuple[str, str]] = []
    allowed = {"include", "space_key", "space_id", "judge_mode", "team_group_id", "doc_types", "exclude_trees"}
    for key in sorted(scope.keys() - allowed):
        issues.append(("scope." + key, "INVALID" if key == "exclude" else "UNKNOWN_KEY"))
    if "include" not in scope:
        issues.append(("scope.include", "MISSING"))
    elif scope["include"] != ["**"]:
        issues.append(("scope.include", "INVALID"))

    def text(key: str) -> str | None:
        value = scope.get(key)
        if key not in scope or value == "":
            issues.append(("scope." + key, "MISSING"))
            return None
        if not isinstance(value, str) or not value.strip():
            issues.append(("scope." + key, "INVALID"))
            return None
        return value

    space_key = text("space_key")
    if space_key is not None and space_key.startswith("~"):
        issues.append(("scope.space_key", "INVALID"))
        space_key = None
    space_id = text("space_id")
    if space_id is not None and not _DIGITS.fullmatch(space_id):
        issues.append(("scope.space_id", "INVALID"))
        space_id = None
    mode = text("judge_mode")
    if mode is not None and mode not in CONFLUENCE_JUDGE_MODES:
        issues.append(("scope.judge_mode", "INVALID"))
        mode = None
    group = None
    if mode == "team_group":
        group = text("team_group_id")
    elif mode == "site_users" and "team_group_id" in scope:
        issues.append(("scope.team_group_id", "INVALID"))
    doc_types = scope.get("doc_types", {})
    if not isinstance(doc_types, dict) or any(
        not isinstance(k, str) or not _DIGITS.fullmatch(k) or v not in CONFLUENCE_DOC_TYPES
        for k, v in doc_types.items()
    ):
        issues.append(("scope.doc_types", "INVALID"))
        doc_types = {}
    trees = scope.get("exclude_trees", [])
    if (
        not isinstance(trees, list)
        or any(not isinstance(t, str) or not _DIGITS.fullmatch(t) for t in trees)
        or len(set(trees)) != len(trees)
    ):
        issues.append(("scope.exclude_trees", "INVALID"))
        trees = []
    extra = [("space_key", space_key), ("space_id", space_id), ("judge_mode", mode)]
    if group is not None:
        extra.append(("team_group_id", group))
    extra += [("doc_types", canonical_json(doc_types)), ("exclude_trees", canonical_json(sorted(trees)))]
    return ScopeCheck(("**",), (), tuple((k, v) for k, v in extra if v is not None), tuple(issues))


KINDS = MappingProxyType(
    {
        "github_repo_files": SourceKindSpec("github_repo_files", True, ("repo", "ref"), ("api.github.com",)),
        "fake": SourceKindSpec("fake", False, (), ("fake.invalid",)),
        # Confluence 페이지(ADR-026 Proposed, QK-ING-003). 비활성으로 등록하고 켜기는 사람이 한다.
        "confluence_pages": SourceKindSpec(
            "confluence_pages",
            True,
            ("space_key", "space_id", "judge_mode", "team_group_id", "doc_types", "exclude_trees"),
            ("api.atlassian.com",),
            extra_auth=("ATLASSIAN_EMAIL", "ATLASSIAN_CLOUD_ID"),
            scope_validator=_confluence_scope,
        ),
    }
)
