"""수집 전 범위 확인. 오류에는 필드와 코드만 담는다."""

import re
import tomllib
from dataclasses import dataclass, field, replace
from datetime import date
from pathlib import Path

from qello_knowledge.domain.redact import FILE_EXTENSIONS
from qello_knowledge.domain.source_config import SourceConfig, SourceScope
from qello_knowledge.sources.config import ConfigIssue, load_sources


@dataclass(frozen=True)
class ScopeReview:
    source: str
    reviewed_on: date
    reviewer_role: str = field(repr=False)
    method: str = field(repr=False)
    result: str
    scope: SourceScope = field(repr=False)
    moved_to_exclude: tuple[tuple[str, str], ...] = field(default=(), repr=False)


def extension_issues(config: SourceConfig) -> tuple[ConfigIssue, ...]:
    issues = []
    for index, pattern in enumerate(config.scope.include):
        leaf = pattern.rsplit("/", 1)[-1]
        if "." not in leaf:
            continue
        extension = leaf.rsplit(".", 1)[-1]
        if re.fullmatch(r"[a-zA-Z0-9]+", extension) is None or extension.lower() not in FILE_EXTENSIONS:
            issues.append(ConfigIssue(config.name, f"scope.include[{index}]", "UNKNOWN_EXTENSION"))
    return tuple(issues)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def load_review(path: Path) -> ScopeReview | tuple[ConfigIssue, ...]:
    def invalid(field="review"):
        return (ConfigIssue(path.stem, field, "REVIEW_INVALID"),)

    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return (ConfigIssue(path.stem, "review", "REVIEW_MISSING"),)
    except (OSError, ValueError, UnicodeError):
        return invalid()
    required = {"source", "reviewed_on", "reviewer_role", "method", "result", "scope"}
    if data.keys() - (required | {"moved_to_exclude"}):
        return invalid()
    for name in sorted(required):
        if name not in data:
            return invalid("review." + name)
    if data["source"] != path.stem:
        return invalid("review.source")
    if type(data["reviewed_on"]) is not date:
        return invalid("review.reviewed_on")
    for name in ("reviewer_role", "method"):
        if not _text(data[name]):
            return invalid("review." + name)
    if data["result"] not in ("개인 정보 없음", "개인 정보 경로 제외함"):
        return invalid("review.result")
    scope = data["scope"]
    if not isinstance(scope, dict) or scope.keys() - {"repo", "ref", "include", "exclude"}:
        return invalid("review.scope")
    for name in ("include", "exclude"):
        if name not in scope or not isinstance(scope[name], list) or not all(_text(p) for p in scope[name]):
            return invalid("review.scope")
    for name in ("repo", "ref"):
        if name in scope and not _text(scope[name]):
            return invalid("review.scope")
    moved = data.get("moved_to_exclude", [])
    if not isinstance(moved, list) or (data["result"] == "개인 정보 경로 제외함" and not moved):
        return invalid("review.moved_to_exclude")
    for row in moved:
        if not isinstance(row, dict) or row.keys() != {"pattern", "reason"} or not all(_text(v) for v in row.values()):
            return invalid("review.moved_to_exclude")
    return ScopeReview(
        data["source"],
        data["reviewed_on"],
        data["reviewer_role"],
        data["method"],
        data["result"],
        SourceScope(
            tuple(scope["include"]),
            tuple(scope["exclude"]),
            tuple((name, scope[name]) for name in ("repo", "ref") if name in scope),
        ),
        tuple((row["pattern"], row["reason"]) for row in moved),
    )


def check_scope(configs, reviews_dir: Path) -> tuple[ConfigIssue, ...]:
    issues = [issue for config in configs for issue in extension_issues(config)]
    for config in configs:
        if not config.enabled:
            continue
        review = load_review(reviews_dir / (config.name + ".toml"))
        if not isinstance(review, ScopeReview):
            issues.extend(review)
            continue
        if (
            review.scope.include != config.scope.include
            or review.scope.exclude != config.scope.exclude
            or dict(review.scope.extra) != dict(config.scope.extra)
        ):
            issues.append(ConfigIssue(config.name, "review.scope", "REVIEW_SCOPE_MISMATCH"))
        for index, (pattern, _) in enumerate(review.moved_to_exclude):
            if pattern not in config.scope.exclude:
                issues.append(ConfigIssue(config.name, f"review.moved_to_exclude[{index}]", "REVIEW_SCOPE_MISMATCH"))
    return tuple(issues)


def load_checked_sources(path: Path, reviews_dir: Path):
    """ING-001이 생략하는 비활성 include만 복원해 확장자를 검사한다."""
    configs, issues = load_sources(path)
    invalid = {issue.source for issue in issues}
    checked = tuple(c for c in configs if c.name not in invalid)
    if any(not c.enabled for c in checked):
        try:
            rows = tomllib.loads(path.read_text(encoding="utf-8")).get("source", [])
        except (OSError, ValueError, UnicodeError):
            return configs, (*issues, ConfigIssue("file", "file", "INVALID"))
        includes = {}
        disabled_names = {c.name for c in checked if not c.enabled}
        for row in rows:
            if (
                not isinstance(row, dict)
                or row.get("enabled") is not False
                or not isinstance(row.get("scope"), dict)
                or not isinstance(row.get("name"), str)
                or row["name"] not in disabled_names
            ):
                continue
            patterns = row["scope"].get("include", [])
            if isinstance(patterns, list) and all(isinstance(p, str) for p in patterns):
                includes[row["name"]] = tuple(patterns)
        checked = tuple(
            replace(c, scope=replace(c.scope, include=includes.get(c.name, ()))) if not c.enabled else c
            for c in checked
        )
    return configs, (*issues, *check_scope(checked, reviews_dir))
