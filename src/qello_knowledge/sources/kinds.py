"""종류 추가는 결정 기록이 필요하다(AGENTS.md 3.1)."""

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class SourceKindSpec:
    name: str
    requires_auth: bool
    scope_keys: tuple[str, ...]
    default_allowed_hosts: tuple[str, ...]


KINDS = MappingProxyType(
    {
        "github_repo_files": SourceKindSpec("github_repo_files", True, ("repo", "ref"), ("api.github.com",)),
        "fake": SourceKindSpec("fake", False, (), ("fake.invalid",)),
    }
)
