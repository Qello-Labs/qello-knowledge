"""수집 전 범위 확인. 오류에는 필드와 코드만 담는다."""

import json
import re
import tomllib
from dataclasses import dataclass, field, replace
from datetime import date, timedelta
from hashlib import sha256
from pathlib import Path

from qello_knowledge.domain.redact import FILE_EXTENSIONS
from qello_knowledge.domain.source_config import SourceConfig, SourceScope
from qello_knowledge.sources.config import ConfigIssue, load_sources
from qello_knowledge.sources.kinds import KINDS

CONFLUENCE_RESULTS = ("팀원 이름 외 개인 정보 없음", "개인 정보 트리 제외함")
SITE_REVIEW_DAYS = 90  # 사이트 사용자 확인 기록의 유효 기간(QK-ING-003 FR-012)


@dataclass(frozen=True)
class ScopeReview:
    source: str
    reviewed_on: date
    reviewer_role: str = field(repr=False)
    method: str = field(repr=False)
    result: str
    scope: SourceScope = field(repr=False)
    moved_to_exclude: tuple[tuple[str, str], ...] = field(default=(), repr=False)
    # Confluence 기록만 쓴다(QK-ING-003 data-model 3절). 이름·메일은 담지 않는다.
    team_member_names: str | None = field(default=None, repr=False)
    site_reviewed_on: date | None = field(default=None, repr=False)
    site_user_count: int | None = field(default=None, repr=False)
    digest: str = field(default="", repr=False)


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


def load_review(path: Path, kind: str | None = None) -> ScopeReview | tuple[ConfigIssue, ...]:
    def invalid(field="review"):
        return (ConfigIssue(path.stem, field, "REVIEW_INVALID"),)

    try:
        raw = path.read_bytes()
        data = tomllib.loads(raw.decode("utf-8"))
    except FileNotFoundError:
        return (ConfigIssue(path.stem, "review", "REVIEW_MISSING"),)
    except (OSError, ValueError, UnicodeError):
        return invalid()
    if kind == "confluence_pages":
        return _confluence_review(path, data, raw, invalid)
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


def _confluence_review(path: Path, data: dict, raw: bytes, invalid) -> ScopeReview | tuple[ConfigIssue, ...]:
    """Confluence 기록(QK-ING-003 FR-025a). 범위 값은 자료원 설정과 같은 검증기로 정규화해 비교한다."""
    required = {"source", "reviewed_on", "reviewer_role", "method", "result", "scope"}
    if data.keys() - (required | {"moved_to_exclude", "team_member_names", "site_users"}):
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
    if data["result"] not in CONFLUENCE_RESULTS:
        return invalid("review.result")
    scope = data["scope"]
    checked = KINDS["confluence_pages"].scope_validator(scope) if isinstance(scope, dict) else None
    if checked is None or checked.issues:
        return invalid("review.scope")
    moved = data.get("moved_to_exclude", [])
    if not isinstance(moved, list) or (data["result"] == CONFLUENCE_RESULTS[1] and not moved):
        return invalid("review.moved_to_exclude")
    for row in moved:
        if (
            not isinstance(row, dict)
            or row.keys() != {"id", "reason"}
            or not all(_text(v) for v in row.values())
            or not row["id"].isdigit()
        ):
            return invalid("review.moved_to_exclude")
    names = data.get("team_member_names")
    if names is not None and names != "허용":
        return invalid("review.team_member_names")
    site = data.get("site_users")
    if site is not None and (
        not isinstance(site, dict)
        or site.keys() != {"reviewed_on", "user_count"}
        or type(site["reviewed_on"]) is not date
        or type(site["user_count"]) is not int
        or site["user_count"] < 0
    ):
        return invalid("review.site_users")
    return ScopeReview(
        data["source"],
        data["reviewed_on"],
        data["reviewer_role"],
        data["method"],
        data["result"],
        SourceScope(checked.include, checked.exclude, checked.extra),
        tuple((row["id"], row["reason"]) for row in moved),
        team_member_names=names,
        site_reviewed_on=site["reviewed_on"] if site else None,
        site_user_count=site["user_count"] if site else None,
        digest=sha256(raw).hexdigest(),
    )


def _confluence_issues(config: SourceConfig, review: ScopeReview) -> list[ConfigIssue]:
    issues = []
    extra = dict(config.scope.extra)
    if review.scope.include != config.scope.include or dict(review.scope.extra) != extra:
        issues.append(ConfigIssue(config.name, "review.scope", "REVIEW_SCOPE_MISMATCH"))
    if review.team_member_names != "허용":
        issues.append(ConfigIssue(config.name, "review.team_member_names", "REVIEW_INVALID"))
    if extra.get("judge_mode") == "site_users" and review.site_reviewed_on is None:
        issues.append(ConfigIssue(config.name, "review.site_users", "REVIEW_INVALID"))
    trees = set(json.loads(extra.get("exclude_trees") or "[]"))
    for index, (tree_id, _) in enumerate(review.moved_to_exclude):
        if tree_id not in trees:
            issues.append(ConfigIssue(config.name, f"review.moved_to_exclude[{index}]", "REVIEW_SCOPE_MISMATCH"))
    return issues


def check_scope(configs, reviews_dir: Path) -> tuple[ConfigIssue, ...]:
    issues = [issue for config in configs for issue in extension_issues(config)]
    for config in configs:
        if not config.enabled:
            continue
        review = load_review(reviews_dir / (config.name + ".toml"), config.kind)
        if not isinstance(review, ScopeReview):
            issues.extend(review)
            continue
        if config.kind == "confluence_pages":
            issues.extend(_confluence_issues(config, review))
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


def confluence_review_context(configs, reviews_dir: Path, today: date) -> tuple[dict[str, bool], dict[str, str]]:
    """켜진 Confluence 자료원의 사이트 사용자 확인 유효 여부와 보안 규칙 버전 재료(QK-ING-003 FR-012, R-13).

    기록 검사를 통과한 뒤에 부른다. 날짜는 UTC 날짜로 센다.
    """
    valid, material = {}, {}
    for config in configs:
        if not config.enabled or config.kind != "confluence_pages":
            continue
        review = load_review(reviews_dir / (config.name + ".toml"), config.kind)
        if not isinstance(review, ScopeReview):
            continue
        mode = dict(config.scope.extra).get("judge_mode", "")
        material[config.name] = f"{mode}:{review.digest}"
        if mode == "site_users":
            reviewed = review.site_reviewed_on
            # 미래 날짜는 확인한 날로 볼 수 없다(구현 검토 C10).
            valid[config.name] = reviewed is not None and reviewed <= today <= reviewed + timedelta(
                days=SITE_REVIEW_DAYS
            )
    return valid, material


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
