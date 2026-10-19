"""자료원 TOML을 읽고 모든 오류를 모은다. 오류에 설정 값을 넣지 않는다."""

from __future__ import annotations

import math
import re
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

from qello_knowledge.config.registry import Entrypoint, specs_for
from qello_knowledge.domain.source_config import RateLimits, RetryPolicy, SourceConfig, SourceScope
from qello_knowledge.sources.kinds import KINDS

UNKNOWN_KIND_MESSAGE = "등록되지 않은 자료원 종류다. 종류를 추가하려면 결정 기록이 필요하다(AGENTS.md 3.1)"
TOKEN_PREFIXES = ("ghp_", "gho_", "ghu_", "ghs_", "ghr_", "github_pat_", "xox", "sk-", "ATATT", "figd_")
SECRETS = tuple(spec for spec in specs_for(Entrypoint.INDEX) if spec.secret)


@dataclass(frozen=True)
class ConfigIssue:
    source: str
    field: str
    code: str

    def __str__(self) -> str:
        message = " " + UNKNOWN_KIND_MESSAGE if self.code == "UNKNOWN_KIND" else ""
        return f"{self.source}: {self.code} {self.field}{message}"


def _token(value: str) -> bool:
    return value.startswith(TOKEN_PREFIXES) or any(spec.rule(value) for spec in SECRETS)


def _scrub(value, field: str, add):
    if isinstance(value, str) and _token(value):
        add(field, "TOKEN_VALUE")
        return None
    if isinstance(value, list):
        return [_scrub(v, f"{field}[{i}]", add) for i, v in enumerate(value)]
    if isinstance(value, dict):
        return {k: _scrub(v, f"{field}.{k}" if field else k, add) for k, v in value.items()}
    return value


def _number(value, minimum: float, integer: bool = False, strict: bool = False) -> bool:
    if type(value) not in ({int} if integer else {int, float}):
        return False
    return math.isfinite(value) and (value > minimum if strict else value >= minimum)


def _source(raw: dict, ordinal: int, seen: set[str]) -> tuple[SourceConfig, list[ConfigIssue]]:
    name = raw.get("name")
    label = name if isinstance(name, str) and not _token(name) else f"[[source]] {ordinal}"
    issues = []

    def add(field, code):
        issues.append(ConfigIssue(label, field, code))

    # 비활성은 name·kind·enabled만 검사한다.
    selected = (
        {k: v for k, v in raw.items() if k in {"name", "kind", "enabled"}} if raw.get("enabled") is False else raw
    )
    data = _scrub(selected, "", add)
    for key in ("name", "kind", "enabled"):
        if key not in data:
            add(key, "MISSING")
    name = data.get("name")
    if "name" in data and (not isinstance(name, str) or not re.fullmatch(r"[a-z0-9-]{1,64}", name)):
        add("name", "INVALID")
    if isinstance(name, str):
        if name in seen:
            add("name", "DUPLICATE_NAME")
        seen.add(name)
    kind = data.get("kind")
    spec = KINDS.get(kind) if isinstance(kind, str) else None
    if "kind" in data and spec is None:
        add("kind", "UNKNOWN_KIND" if isinstance(kind, str) else "INVALID")
    if "enabled" in data and type(data["enabled"]) is not bool:
        add("enabled", "INVALID")
    name = name if isinstance(name, str) else label
    kind = kind if isinstance(kind, str) else ""
    enabled = data.get("enabled") is True
    if data.get("enabled") is False:
        return SourceConfig(name, kind, False), issues

    def keys(table, allowed, prefix=""):
        for key in table.keys() - set(allowed):
            add(prefix + key, "UNKNOWN_KEY")

    keys(data, {"name", "kind", "enabled", "auth", "scope", "limits", "retry", "max_content_bytes", "allowed_hosts"})
    auth = data.get("auth")
    if spec and spec.requires_auth and "auth" not in data:
        add("auth", "MISSING")
    if "auth" in data and (not isinstance(auth, str) or auth not in {s.name for s in SECRETS}):
        add("auth", "UNKNOWN_AUTH_SETTING")
    auth = auth if isinstance(auth, str) else None
    scope = data.get("scope")
    if not isinstance(scope, dict):
        add("scope", "MISSING" if "scope" not in data else "INVALID")
        scope = {}
    scope_keys = spec.scope_keys if spec else ()
    keys(scope, {"include", "exclude", *scope_keys}, "scope.")
    patterns = {}
    for key in ("include", "exclude"):
        value = scope.get(key, [] if key == "exclude" else None)
        if key == "include" and key not in scope:
            add("scope.include", "MISSING")
        elif (
            not isinstance(value, list)
            or (key == "include" and not value)
            or any(not isinstance(v, str) or not v for v in value)
        ):
            add("scope." + key, "INVALID")
            value = []
        patterns[key] = tuple(value or ())
    extra = []
    for key in scope_keys:
        value = scope.get(key)
        if key not in scope:
            add("scope." + key, "MISSING")
        elif (
            not isinstance(value, str)
            or not value.strip()
            or (key == "repo" and not re.fullmatch(r"[^/\s]+/[^/\s]+", value))
        ):
            add("scope." + key, "INVALID")
        else:
            extra.append((key, value))

    limits, retry = asdict(RateLimits()), asdict(RetryPolicy())
    for table_name, values in (("limits", limits), ("retry", retry)):
        given = data.get(table_name, {})
        if not isinstance(given, dict):
            add(table_name, "INVALID")
            continue
        keys(given, values, table_name + ".")
        for key in given.keys() & values.keys():
            value = given[key]
            integer = key.startswith("max_requests") or key == "max_retries"
            minimum = (
                0 if key in {"max_wait_seconds", "max_retries", "initial_backoff_seconds", "max_backoff_seconds"} else 1
            )
            if not _number(value, minimum, integer, key in {"initial_backoff_seconds", "max_backoff_seconds"}):
                add(f"{table_name}.{key}", "INVALID")
            else:
                values[key] = value
    if retry["max_backoff_seconds"] < retry["initial_backoff_seconds"]:
        add("retry.max_backoff_seconds", "INVALID")
    size = data.get("max_content_bytes", 1_000_000)
    if not _number(size, 1, integer=True):
        add("max_content_bytes", "INVALID")
        size = 1_000_000
    hosts = data.get("allowed_hosts", list(spec.default_allowed_hosts) if spec else [])
    if not isinstance(hosts, list) or any(
        not isinstance(host, str) or not re.fullmatch(r"[a-zA-Z0-9.-]+", host) for host in hosts
    ):
        add("allowed_hosts", "INVALID")
        hosts = []
    config = SourceConfig(
        name,
        kind,
        enabled,
        auth,
        SourceScope(patterns["include"], patterns["exclude"], tuple(extra)),
        RateLimits(**limits),
        RetryPolicy(**retry),
        size,
        tuple(hosts),
    )
    return config, issues


def load_sources(path: Path) -> tuple[tuple[SourceConfig, ...], tuple[ConfigIssue, ...]]:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeError):
        return (), (ConfigIssue("file", "file", "INVALID"),)
    issues = [ConfigIssue("file", key, "UNKNOWN_KEY") for key in data.keys() - {"source"}]
    rows = data.get("source", [])
    if not isinstance(rows, list):
        return (), (*issues, ConfigIssue("file", "source", "INVALID"))
    configs, seen = [], set()
    for index, row in enumerate(rows, 1):
        if not isinstance(row, dict):
            issues.append(ConfigIssue(f"[[source]] {index}", "source", "INVALID"))
            continue
        config, found = _source(row, index, seen)
        configs.append(config)
        issues.extend(found)
    return tuple(configs), tuple(issues)
