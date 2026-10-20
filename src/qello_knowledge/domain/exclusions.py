"""자료원 설정과 상관없이 항상 적용하는 색인 제외 경로(research R-04). 설정으로 해제할 수 없다(FR-007)."""

from __future__ import annotations

import posixpath
from dataclasses import dataclass
from pathlib import PurePosixPath

EXAMPLE_SUFFIXES = (".example", ".sample", ".template")
PATH_INVALID = "path-invalid"


@dataclass(frozen=True)
class DefaultExclusion:
    category: str
    pattern: str
    # 참이면 예시 파일(`.env.example` 등)은 빼지 않고 비밀값 검사로 넘긴다.
    allow_examples: bool = False


def _group(category: str, *patterns: str, allow_examples: tuple[str, ...] = ()) -> tuple[DefaultExclusion, ...]:
    return tuple(DefaultExclusion(category, p, p in allow_examples) for p in patterns)


DEFAULT_EXCLUSIONS = (
    *_group("env-file", "**/.env", "**/.env.*", allow_examples=("**/.env.*",)),
    *_group(
        "private-key-file",
        "**/*.pem",
        "**/*.key",
        "**/*.p12",
        "**/*.pfx",
        "**/*.jks",
        "**/*.keystore",
        "**/id_rsa*",
        "**/id_ecdsa*",
        "**/id_ed25519*",
    ),
    *_group("secret-dir", "**/secrets/**", "**/.secrets/**"),
    *_group(
        "infra-state",
        "**/*.tfstate",
        "**/*.tfstate.*",
        "**/*.tfvars",
        "**/.terraform/**",
        allow_examples=("**/*.tfvars",),
    ),
    *_group(
        "build-output",
        "**/node_modules/**",
        "**/build/**",
        "**/dist/**",
        "**/target/**",
        "**/.gradle/**",
        "**/.venv/**",
        "**/__pycache__/**",
    ),
    *_group("vcs-internal", "**/.git/**"),
)
CATEGORIES = (*dict.fromkeys(e.category for e in DEFAULT_EXCLUSIONS), PATH_INVALID)


def normalize_location(location: str) -> str:
    return posixpath.normpath(location)


def excluded_by(location: str, exclusions: tuple[DefaultExclusion, ...] = DEFAULT_EXCLUSIONS) -> str | None:
    """정규화한 경로가 걸린 범주 이름. 저장소 밖을 가리키는 경로는 `path-invalid`다."""
    normalized = normalize_location(location)
    if normalized in {".", ".."} or normalized.startswith(("/", "../")):
        return PATH_INVALID
    path = PurePosixPath(normalized)
    is_example = path.name.lower().endswith(EXAMPLE_SUFFIXES)
    for exclusion in exclusions:
        if path.full_match(exclusion.pattern, case_sensitive=False) and not (exclusion.allow_examples and is_example):
            return exclusion.category
    return None
