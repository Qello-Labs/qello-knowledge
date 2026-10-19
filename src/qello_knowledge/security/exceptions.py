"""색인 필터 비밀값 오탐 예외를 읽고 모든 오류를 모은다. 오류에 값(경로·사유)을 넣지 않는다."""

from __future__ import annotations

import posixpath
import tomllib
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from qello_knowledge.domain.secret_rules import RULES, SecretRule
from qello_knowledge.domain.source_config import SourceConfig

FIELDS = ("source", "path", "rule", "reason")


@dataclass(frozen=True, order=True)
class SecretException:
    source: str
    path: str
    rule: str
    reason: str


@dataclass(frozen=True)
class PolicyIssue:
    entry: int | None
    field: str
    code: str

    def __str__(self) -> str:
        where = self.field if self.entry is None else f"exception[{self.entry}].{self.field}"
        return f"{where} {self.code}"


def normalize_path(path: str) -> str:
    return posixpath.normpath(path)


def load_exceptions(
    path: Path, configs: Sequence[SourceConfig], rules: Sequence[SecretRule] = RULES
) -> tuple[frozenset[SecretException], tuple[PolicyIssue, ...]]:
    if not path.is_file():
        return frozenset(), ()
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return frozenset(), (PolicyIssue(None, "file", "INVALID_FILE"),)
    issues = [PolicyIssue(None, key, "UNKNOWN_KEY") for key in sorted(data.keys() - {"exception"})]
    rows = data.get("exception", [])
    if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
        return frozenset(), (*issues, PolicyIssue(None, "exception", "INVALID"))
    sources = {config.name for config in configs}
    rule_names = {rule.name for rule in rules}
    found, seen = set(), set()
    for number, row in enumerate(rows, 1):
        before = len(issues)
        issues += [PolicyIssue(number, key, "UNKNOWN_KEY") for key in sorted(row.keys() - set(FIELDS))]
        values = {}
        for key in FIELDS:
            value = row.get(key)
            if key not in row:
                issues.append(PolicyIssue(number, key, "MISSING"))
            elif not isinstance(value, str) or not value.strip():
                issues.append(PolicyIssue(number, key, "INVALID"))
            else:
                values[key] = value
        if "source" in values and values["source"] not in sources:
            issues.append(PolicyIssue(number, "source", "UNKNOWN_SOURCE"))
        if "rule" in values and values["rule"] not in rule_names:
            issues.append(PolicyIssue(number, "rule", "UNKNOWN_RULE"))
        if "path" in values:
            if any(mark in values["path"] for mark in "*?["):
                issues.append(PolicyIssue(number, "path", "WILDCARD_PATH"))
            normalized = normalize_path(values["path"])
            if normalized.startswith(("/", "..")) or normalized == ".":
                issues.append(PolicyIssue(number, "path", "INVALID_PATH"))
            values["path"] = normalized
            key = (values.get("source"), normalized, values.get("rule"))
            if key in seen:
                issues.append(PolicyIssue(number, "path", "DUPLICATE"))
            seen.add(key)
        if len(issues) == before:
            found.add(SecretException(values["source"], values["path"], values["rule"], values["reason"]))
    return (frozenset(found) if not issues else frozenset()), tuple(issues)
