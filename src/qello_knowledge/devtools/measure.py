"""사전 검증된 자료원의 수집을 측정한다. 저장·임베딩은 하지 않는다."""

import json
import platform
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urlsplit

from qello_knowledge.adapters.github import GitHubRepoFilesAdapter
from qello_knowledge.domain.redact import FieldKind, safe_text
from qello_knowledge.domain.security import Verdict
from qello_knowledge.domain.source_config import SourceConfig
from qello_knowledge.security.policy import SecurityPolicy, load_policy
from qello_knowledge.security.screen import screen_source
from qello_knowledge.sources.config import ConfigIssue
from qello_knowledge.sources.scope_review import load_checked_sources
from qello_knowledge.sources.session import DefaultSourceSession


@dataclass(frozen=True, init=False)
class PreparedSource:
    config: SourceConfig
    policy: SecurityPolicy = field(repr=False)

    def __init__(self, *args, **kwargs):
        raise TypeError("prepare_source를 통해 생성해야 한다")


def prepare_source(name: str, sources_path: Path, reviews_dir: Path, exceptions_path: Path):
    configs, issues = load_checked_sources(sources_path, reviews_dir)
    if issues:
        return issues
    policy, issues = load_policy(exceptions_path, configs)
    if issues:
        return issues
    config = next((c for c in configs if c.name == name), None)
    if config is None:
        return (ConfigIssue("source", "name", "NOT_FOUND"),)
    if not config.enabled:
        return (ConfigIssue(config.name, "enabled", "DISABLED"),)
    if config.kind != "github_repo_files":
        return (ConfigIssue(config.name, "kind", "UNSUPPORTED_KIND"),)
    prepared = object.__new__(PreparedSource)
    object.__setattr__(prepared, "config", config)
    object.__setattr__(prepared, "policy", policy)
    return prepared


class CountingTransport:
    def __init__(self, inner):
        self._inner = inner
        self.bodies_fetched = 0
        self.total_bytes = 0
        self.max_file_bytes = 0

    def send(self, request):
        response = self._inner.send(request)
        if "/git/blobs/" in urlsplit(request.url).path and 200 <= response.status < 300:
            size = len(response.body)
            self.bodies_fetched += 1
            self.total_bytes += size
            self.max_file_bytes = max(self.max_file_bytes, size)
        return response


@dataclass(frozen=True)
class SourceMeasurement:
    source_name: str
    repo: str
    ref: str
    commit: str | None
    visibility: str | None
    tree_truncated: bool | None
    include: tuple[str, ...]
    exclude: tuple[str, ...]
    measured_at: str
    environment: str
    requests: int
    elapsed_seconds: float
    listing_complete: bool
    stop: dict | None
    files: int
    bodies_fetched: int
    total_bytes: int
    max_file_bytes: int
    by_verdict: dict
    by_rule: dict
    blocked: tuple[dict, ...]
    limits: dict

    @property
    def ok(self):
        return self.listing_complete and self.stop is None and self.by_verdict.get("ERROR", 0) == 0

    def to_dict(self):
        data = asdict(self)
        for key in ("include", "exclude", "blocked"):
            data[key] = list(data[key])
        return data


def measure_source(prepared: PreparedSource, transport, clock) -> SourceMeasurement:
    if not isinstance(prepared, PreparedSource):
        raise TypeError("사전 검증된 자료원이 필요하다")
    config, policy = prepared.config, prepared.policy
    adapter = GitHubRepoFilesAdapter()
    counting = transport if isinstance(transport, CountingTransport) else CountingTransport(transport)
    session = DefaultSourceSession(counting, adapter, config, clock)
    result = screen_source(adapter, config, session, policy)
    snapshot = adapter.last_snapshot
    summary = result.summary.to_dict()
    context = policy.output_context(config.kind)

    def text(value):
        return None if value is None else safe_text(value, FieldKind.TEXT, context)

    scope = dict(config.scope.extra)
    return SourceMeasurement(
        config.name,
        text(scope["repo"]),
        text(scope["ref"]),
        snapshot.commit_sha if snapshot else None,
        text(snapshot.visibility) if snapshot else None,
        snapshot.truncated if snapshot else None,
        tuple(safe_text(p, FieldKind.PATH, context) for p in config.scope.include),
        tuple(safe_text(p, FieldKind.PATH, context) for p in config.scope.exclude),
        result.fetch.started_at.isoformat(),
        f"{platform.platform()} / Python {platform.python_version()}",
        result.fetch.requests_made,
        (result.fetch.finished_at - result.fetch.started_at).total_seconds(),
        result.fetch.listing_complete,
        result.fetch.to_dict()["stop"],
        len(result.verdicts),
        counting.bodies_fetched,
        counting.total_bytes,
        counting.max_file_bytes,
        summary["by_verdict"],
        summary["by_rule"],
        tuple(
            v.to_dict(context)
            for v in result.verdicts
            if v.verdict in {Verdict.SECRET_BLOCKED, Verdict.ERROR} or v.rule == "identifier-address"
        ),
        {**asdict(config.limits), "max_content_bytes": config.max_content_bytes},
    )


def render_measurement(measurement: SourceMeasurement, json_output=False) -> str:
    data = measurement.to_dict()
    if json_output:
        return json.dumps(data, ensure_ascii=False)
    lines = [
        f"수집 측정: {data['source_name']} ({data['repo']}@{data['ref']}, 커밋 {data['commit']}, "
        f"visibility={data['visibility']}, tree_truncated={data['tree_truncated']})",
        f"  범위      include={json.dumps(data['include'], ensure_ascii=False)} "
        f"exclude={json.dumps(data['exclude'], ensure_ascii=False)}",
        f"  환경      {data['environment']}, {data['measured_at']}",
        f"  요청      {data['requests']}회, 소요 {data['elapsed_seconds']:.3f}초, "
        f"listing_complete={data['listing_complete']}, stop={data['stop']}",
        f"  파일      범위 안 {data['files']}개, 본문 받음 {data['bodies_fetched']}건, "
        f"{data['total_bytes']}바이트, 최대 {data['max_file_bytes']}바이트",
        f"  판정      {json.dumps(data['by_verdict'], ensure_ascii=False)}",
        f"  규칙      {json.dumps(data['by_rule'], ensure_ascii=False)}",
        f"  한도      {json.dumps(data['limits'], ensure_ascii=False)}",
    ]
    lines += [f"  막힌 자료  {item['source_id']}  {item['verdict']}  {item['rule']}" for item in data["blocked"]]
    return "\n".join(lines)
