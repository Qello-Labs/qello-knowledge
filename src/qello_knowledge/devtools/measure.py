"""사전 검증된 자료원의 수집을 측정한다. 저장·임베딩은 하지 않는다."""

import json
import platform
import re
import time
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from qello_knowledge.adapters.github import GitHubRepoFilesAdapter
from qello_knowledge.domain.redact import FieldKind, safe_text
from qello_knowledge.domain.security import Verdict
from qello_knowledge.domain.source import ItemStatus
from qello_knowledge.domain.source_config import SourceConfig
from qello_knowledge.security.policy import SecurityPolicy, load_policy
from qello_knowledge.security.screen import screen_source
from qello_knowledge.sources.config import ConfigIssue, load_source_as_enabled
from qello_knowledge.sources.scope_review import check_scope, confluence_review_context, load_checked_sources
from qello_knowledge.sources.session import DefaultSourceSession


@dataclass(frozen=True, init=False)
class PreparedSource:
    config: SourceConfig
    policy: SecurityPolicy = field(repr=False)
    context: dict = field(default_factory=dict, repr=False)  # 종류별 조립 값(예: 사이트 사용자 확인 유효 여부)

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
    context = {}
    if config.kind == "confluence_pages":
        # 켜기 전 측정(FR-027)이라 비활성도 잰다. 그 자료원 하나만 활성처럼 검증하고 확인 기록을 대조한다.
        config, issues = load_source_as_enabled(sources_path, name)
        issues = (*issues, *check_scope((config,), reviews_dir)) if config is not None else issues
        if issues:
            return issues
        site_valid, material = confluence_review_context((config,), reviews_dir, datetime.now(UTC).date())
        policy, issues = load_policy(exceptions_path, configs, kind_material=material)
        if issues:
            return issues
        context = {"site_review_valid": site_valid}
    elif not config.enabled:
        return (ConfigIssue(config.name, "enabled", "DISABLED"),)
    elif config.kind != "github_repo_files":
        return (ConfigIssue(config.name, "kind", "UNSUPPORTED_KIND"),)
    prepared = object.__new__(PreparedSource)
    object.__setattr__(prepared, "config", config)
    object.__setattr__(prepared, "policy", policy)
    object.__setattr__(prepared, "context", context)
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
    chunking: dict | None = None

    @property
    def ok(self):
        return self.listing_complete and self.stop is None and self.by_verdict.get("ERROR", 0) == 0

    def to_dict(self):
        data = asdict(self)
        for key in ("include", "exclude", "blocked"):
            data[key] = list(data[key])
        if self.chunking is None:
            data.pop("chunking")
        return data


def measure_source(prepared: PreparedSource, transport, clock, *, chunk: bool = False) -> SourceMeasurement:
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

    chunking = None
    if chunk:
        # 색인 전용 선택 의존성: 일반 수집 측정에서는 해석기를 가져오지 않는다.
        from qello_knowledge.chunking import chunk_screened, chunking_version
        from qello_knowledge.domain.chunking import ChunkingSettings

        settings = ChunkingSettings()
        start = time.perf_counter()
        chunked = chunk_screened(result.passed, settings)
        elapsed = time.perf_counter() - start
        chunk_summary = chunked.summary
        chunking = {
            "chunking_version": chunking_version(settings),
            "settings": asdict(settings),
            "elapsed_seconds": elapsed,
            "summary": {
                "by_outcome": dict(chunk_summary.by_outcome),
                "chunk_count": chunk_summary.chunk_count,
                "by_failure": dict(chunk_summary.by_failure),
                "by_warning": dict(chunk_summary.by_warning),
                "tokens_min": chunk_summary.tokens_min,
                "tokens_median": chunk_summary.tokens_median,
                "tokens_max": chunk_summary.tokens_max,
                "split_blocks": chunk_summary.split_blocks,
            },
            "failures": [
                {"path": safe_text(r.screened.content.location, FieldKind.PATH, context), "failure": r.failure.value}
                for r in chunked.results
                if r.failure is not None
            ],
            "warnings": [
                {
                    "path": safe_text(r.screened.content.location, FieldKind.PATH, context),
                    "line": w.line,
                    "kind": w.kind.value,
                }
                for r in chunked.results
                for w in r.warnings
            ],
        }
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
        chunking,
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
    if measurement.chunking is not None:
        chunking = measurement.chunking
        settings, summary = chunking["settings"], chunking["summary"]
        lines += [
            f"  청킹      {chunking['chunking_version']} target={settings['target_tokens']} "
            f"limit={settings['limit_tokens']}, 소요 {chunking['elapsed_seconds']:.3f}초",
            f"  청킹 결과 {json.dumps(summary['by_outcome'], ensure_ascii=False)} 청크 {summary['chunk_count']}개, "
            f"예상 토큰 min={summary['tokens_min']} median={summary['tokens_median']} max={summary['tokens_max']}, "
            f"줄 단위로 나뉜 블록 {summary['split_blocks']}개",
        ]
        lines += [f"  청킹 실패 {item['path']}  {item['failure']}" for item in chunking["failures"]]
        lines += [f"  구조 경고 {item['path']}:{item['line']}  {item['kind']}" for item in chunking["warnings"]]
    return "\n".join(lines)


# ---- Confluence(QK-ING-003 FR-027, research R-17) ------------------------------------------------------

_ID_AFTER = re.compile(r"/(spaces|pages|folders)/[^/?]+")


def endpoint_name(url: str) -> str:
    """요청 주소를 ID 없는 이름으로 바꾼다. Cloud ID·페이지 ID는 남기지 않는다."""
    parts = urlsplit(url)
    path = parts.path.split("/wiki/api/v2", 1)[-1]
    name = _ID_AFTER.sub(lambda m: f"/{m.group(1)}/{{id}}", path)
    if name == "/pages/{id}":
        name += "?body" if "body-format" in parts.query else "?status"
    return "GET " + name


class ConfluenceCountingTransport:
    def __init__(self, inner):
        self._inner = inner
        self.by_endpoint: Counter = Counter()
        self.bodies_fetched = 0
        self.total_bytes = 0
        self.max_page_bytes = 0

    def send(self, request):
        response = self._inner.send(request)
        name = endpoint_name(request.url)
        self.by_endpoint[f"{name} {response.status}"] += 1
        if name == "GET /pages/{id}?body" and 200 <= response.status < 300:
            size = len(response.body)
            self.bodies_fetched += 1
            self.total_bytes += size
            self.max_page_bytes = max(self.max_page_bytes, size)
        return response


@dataclass(frozen=True)
class ConfluenceMeasurement:
    """페이지는 ID로만 가리킨다. 제목·제목 경로·링크·본문·이름은 담지 않는다(FR-027, SC-004)."""

    source_name: str
    measured_at: str
    environment: str
    requests: int
    requests_by_endpoint: dict
    elapsed_seconds: float
    listing_complete: bool
    incomplete_reason: str | None
    stop: dict | None
    pages: int
    bodies_fetched: int
    total_bytes: int
    max_page_bytes: int
    by_verdict: dict
    by_rule: dict
    unclassified: int
    access_lookup_failed: int
    conversion_warnings: dict
    blocked: tuple[dict, ...]
    limits: dict
    chunking: dict | None = None

    @property
    def ok(self):
        return self.listing_complete and self.stop is None and self.by_verdict.get("ERROR", 0) == 0

    def to_dict(self):
        data = asdict(self)
        data["blocked"] = list(data["blocked"])
        if self.chunking is None:
            data.pop("chunking")
        return data


def measure_confluence(prepared: PreparedSource, adapter, transport, clock, *, chunk: bool = False):
    if not isinstance(prepared, PreparedSource):
        raise TypeError("사전 검증된 자료원이 필요하다")
    config, policy = prepared.config, prepared.policy
    counting = (
        transport if isinstance(transport, ConfluenceCountingTransport) else ConfluenceCountingTransport(transport)
    )
    session = DefaultSourceSession(counting, adapter, config, clock)
    result = screen_source(adapter, config, session, policy)
    summary = result.summary.to_dict()
    context = policy.output_context(config.kind)
    warnings = Counter(w.kind.value for s in result.passed for w in s.content.conversion_warnings)
    chunking = None
    if chunk:
        from qello_knowledge.chunking import chunk_screened, chunking_version
        from qello_knowledge.domain.chunking import ChunkingSettings
        from qello_knowledge.domain.embedding import MODELS
        from qello_knowledge.embedding.estimate import estimated_neurons

        settings = ChunkingSettings()
        chunked = chunk_screened(result.passed, settings)
        texts = [d.embedding_text for r in chunked.results for d in r.drafts]
        chunking = {
            "chunking_version": chunking_version(settings),
            "by_outcome": dict(chunked.summary.by_outcome),
            "chunk_count": chunked.summary.chunk_count,
            "empty_bodies": sum(r.outcome.value == "EMPTY" for r in chunked.results),
            "failures": [
                {"source_id": r.screened.item.source_id, "failure": r.failure.value}
                for r in chunked.results
                if r.failure is not None
            ],
            # 캐시·중복 제거 전 상한(research R-17)
            "estimated_neurons": estimated_neurons(texts, MODELS[settings.model_version]),
        }
    failed_fetch = sum(o.status == ItemStatus.PERMANENT_FAILED for o in result.fetch.items)
    return ConfluenceMeasurement(
        config.name,
        result.fetch.started_at.isoformat(),
        f"{platform.platform()} / Python {platform.python_version()}",
        result.fetch.requests_made,
        dict(sorted(counting.by_endpoint.items())),
        (result.fetch.finished_at - result.fetch.started_at).total_seconds(),
        result.listing.complete,
        result.listing.incomplete_reason,
        result.fetch.to_dict()["stop"],
        len(result.listing.items),
        counting.bodies_fetched,
        counting.total_bytes,
        counting.max_page_bytes,
        summary["by_verdict"] | ({"FETCH_FAILED": failed_fetch} if failed_fetch else {}),
        summary["by_rule"],
        sum(v.rule == "source-exclude:unclassified" for v in result.verdicts),
        sum(v.verdict == Verdict.ACCESS_HELD and not v.access_raw for v in result.verdicts),
        dict(sorted(warnings.items())),
        tuple(v.to_dict(context) for v in result.verdicts if v.verdict in {Verdict.SECRET_BLOCKED, Verdict.ERROR}),
        {**asdict(config.limits), "max_content_bytes": config.max_content_bytes},
        chunking,
    )


def render_confluence_measurement(measurement: ConfluenceMeasurement, json_output=False) -> str:
    data = measurement.to_dict()
    if json_output:
        return json.dumps(data, ensure_ascii=False)
    lines = [
        f"수집 측정: {data['source_name']} (Confluence)",
        f"  환경      {data['environment']}, {data['measured_at']}",
        f"  요청      {data['requests']}회, 소요 {data['elapsed_seconds']:.3f}초, "
        f"listing_complete={data['listing_complete']}({data['incomplete_reason']}), stop={data['stop']}",
        f"  엔드포인트 {json.dumps(data['requests_by_endpoint'], ensure_ascii=False)}",
        f"  페이지    {data['pages']}개, 본문 받음 {data['bodies_fetched']}건, "
        f"{data['total_bytes']}바이트, 최대 {data['max_page_bytes']}바이트",
        f"  판정      {json.dumps(data['by_verdict'], ensure_ascii=False)}",
        f"  규칙      {json.dumps(data['by_rule'], ensure_ascii=False)}",
        f"  미분류    {data['unclassified']}개, 권한 조회 실패 {data['access_lookup_failed']}개",
        f"  변환 경고 {json.dumps(data['conversion_warnings'], ensure_ascii=False)}",
        f"  한도      {json.dumps(data['limits'], ensure_ascii=False)}",
    ]
    lines += [f"  막힌 자료  {item['source_id']}  {item['verdict']}  {item['rule']}" for item in data["blocked"]]
    if measurement.chunking is not None:
        chunking = measurement.chunking
        lines.append(
            f"  청킹      {chunking['chunking_version']} {json.dumps(chunking['by_outcome'], ensure_ascii=False)} "
            f"청크 {chunking['chunk_count']}개, 본문 없음 {chunking['empty_bodies']}개, "
            f"예상 Neurons {chunking['estimated_neurons']:.2f}(캐시 전 상한)"
        )
        lines += [f"  청킹 실패 {item['source_id']}  {item['failure']}" for item in chunking["failures"]]
    return "\n".join(lines)
