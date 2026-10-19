"""보안 정책 묶음과 규칙 버전. 판정을 바꿀 수 있는 입력은 모두 버전 해시에 들어간다(research R-08)."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path

from qello_knowledge.domain.exclusions import DEFAULT_EXCLUSIONS, EXAMPLE_SUFFIXES, DefaultExclusion
from qello_knowledge.domain.redact import AddressPolicy, OutputContext
from qello_knowledge.domain.secret_rules import RULES, SecretRule
from qello_knowledge.domain.source_config import SourceConfig
from qello_knowledge.security.exceptions import PolicyIssue, SecretException, load_exceptions
from qello_knowledge.security.kinds import KINDS, KindSecurityPolicy


@dataclass(frozen=True)
class SecurityPolicy:
    rules: tuple[SecretRule, ...] = RULES
    exclusions: tuple[DefaultExclusion, ...] = DEFAULT_EXCLUSIONS
    exceptions: frozenset[SecretException] = frozenset()
    kinds: Mapping[str, KindSecurityPolicy] = field(default_factory=lambda: KINDS)
    address_policy: AddressPolicy = field(default_factory=AddressPolicy)
    version: str = field(init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "version", _version(self))

    def output_context(self, kind: str) -> OutputContext:
        spec = self.kinds.get(kind)
        if spec is None:
            return OutputContext((), False, self.address_policy)
        return OutputContext(spec.public_link_hosts, spec.source_id_is_path, self.address_policy)

    def exempt_rules(self, source: str, path: str) -> frozenset[str]:
        return frozenset(e.rule for e in self.exceptions if e.source == source and e.path == path)


def _version(policy: SecurityPolicy) -> str:
    material = {
        "rules": [[r.name, r.pattern.pattern, r.pattern.flags] for r in policy.rules],
        "exclusions": [[e.category, e.pattern, e.allow_examples] for e in policy.exclusions],
        "example_suffixes": list(EXAMPLE_SUFFIXES),
        "exceptions": [[e.source, e.path, e.rule] for e in sorted(policy.exceptions)],
        "address": {
            "patterns": [p.pattern for p in policy.address_policy.patterns],
            "file_extensions": sorted(policy.address_policy.file_extensions),
            "version": policy.address_policy.version,
        },
        "kinds": [
            [k.kind, k.rule_name, list(k.public_link_hosts), k.source_id_is_path]
            for k in sorted(policy.kinds.values(), key=lambda k: k.kind)
        ],
    }
    digest = sha256(json.dumps(material, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
    return "sec-" + digest[:12]


def load_policy(
    exceptions_path: Path, configs: Sequence[SourceConfig]
) -> tuple[SecurityPolicy | None, tuple[PolicyIssue, ...]]:
    """예외 파일 오류가 하나라도 있으면 정책을 만들지 않는다. 호출자는 원본을 부르기 전에 멈춘다."""
    exceptions, issues = load_exceptions(exceptions_path, configs)
    if issues:
        return None, issues
    return SecurityPolicy(exceptions=exceptions), ()
