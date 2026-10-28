"""동기화 CLI 점검·조립. 원본 전송과 저장 구현은 이 경계에서만 조립한다."""

from __future__ import annotations

import argparse
import json
import os
import tomllib
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from qello_knowledge.adapters.postgres.connection import database_url, target_label
from qello_knowledge.config.check import budget_settings, build_report, code_chunking_from
from qello_knowledge.config.loader import SettingStatus, load, merge_sources, read_env_file
from qello_knowledge.config.registry import Entrypoint
from qello_knowledge.domain.chunking import ChunkingSettings
from qello_knowledge.domain.embedding import EmbedError
from qello_knowledge.domain.redact import FieldKind, safe_text
from qello_knowledge.domain.store import StoreError, StoreUnavailable
from qello_knowledge.security.policy import SecurityPolicy, load_policy
from qello_knowledge.sources.config import load_sources
from qello_knowledge.sources.report import render_report, source_report
from qello_knowledge.sources.scope_review import confluence_review_context, load_checked_sources
from qello_knowledge.sync.activate import activate_first_index
from qello_knowledge.sync.identity import IdentityError, select_targets
from qello_knowledge.sync.plan import SyncTarget, plan_source
from qello_knowledge.sync.preview import preview
from qello_knowledge.sync.report import preview_dict, render, run_dict, summary_values
from qello_knowledge.sync.run import SyncDependencies, SyncOptions, current_spec, run_sync


@dataclass
class SyncRuntime:
    targets: tuple
    deps: SyncDependencies
    resources: tuple = ()

    def close(self):
        for resource in reversed(self.resources):
            resource.close()


def _github_parts(config, settings, context):
    from qello_knowledge.adapters.github import GitHubRepoFilesAdapter
    from qello_knowledge.adapters.http import HttpsTransport

    return GitHubRepoFilesAdapter(), HttpsTransport(
        config.allowed_hosts, settings.get(config.auth or "GITHUB_API_TOKEN")
    )


def _confluence_parts(config, settings, context):
    """Confluence 범위 지정 토큰은 게이트웨이와 Basic 인증을 쓴다(ADR-026, QK-ING-003 R-14). 값은 기록하지 않는다."""
    import base64

    from qello_knowledge.adapters.confluence import ConfluencePagesAdapter
    from qello_knowledge.adapters.http import HttpsTransport
    from qello_knowledge.security.kinds import KINDS as SECURITY_KINDS

    token, email, cloud = (settings.get(name) for name in (config.auth, "ATLASSIAN_EMAIL", "ATLASSIAN_CLOUD_ID"))
    site = settings.get("ATLASSIAN_SITE_URL")

    def authorization():
        pair = email.reveal() + ":" + token.reveal()
        return "Basic " + base64.b64encode(pair.encode("utf-8")).decode("ascii")

    adapter = ConfluencePagesAdapter(
        gateway_root="https://api.atlassian.com/ex/confluence/" + cloud.reveal(),
        site_base=site.reveal() if site is not None else None,
        site_review_valid=context.get("site_review_valid", {}).get(config.name),
        public_link_hosts=sorted({host for kind in SECURITY_KINDS.values() for host in kind.public_link_hosts}),
    )
    transport = HttpsTransport(
        config.allowed_hosts, None, authorization=authorization, default_headers={"accept": "application/json"}
    )
    return adapter, transport


# 자료원 종류 → (어댑터, 전송) 조립. 표에 없는 종류가 켜져 있으면 원본을 부르기 전에 멈춘다(QK-ING-003 R-12).
TARGET_PARTS = {"github_repo_files": _github_parts, "confluence_pages": _confluence_parts}


def source_targets(configs, settings, clock, context=None):
    """켜진 자료원의 수집 대상을 종류별로 조립한다. `context`는 종류별 조립에 필요한 실행 값이다."""
    from qello_knowledge.sources.session import DefaultSourceSession

    if any(c.enabled and c.kind not in TARGET_PARTS for c in configs):
        raise IdentityError("unsupported_source_kind")
    targets = []
    for config in configs:
        if not config.enabled:
            continue
        adapter, transport = TARGET_PARTS[config.kind](config, settings, context or {})
        targets.append(
            SyncTarget(
                config.name,
                config.kind,
                config=config,
                adapter=adapter,
                session=DefaultSourceSession(transport, adapter, config, clock),
            )
        )
    return targets


github_targets = source_targets  # 이전 이름. 평가 준비(QK-RET-001)가 쓰던 기본 대상과 같다


def workers_ai_provider(source, settings):
    from qello_knowledge.adapters.workers_ai.rest import WorkersAiRestProvider

    return WorkersAiRestProvider(source["CLOUDFLARE_ACCOUNT_ID"], settings.get("CLOUDFLARE_API_TOKEN"))


_UNSET = object()


def current_index_version(chunking=None, code=None, confluence=False):
    """현재 청커 설정의 인덱스 버전(활성화의 현재 버전 계산, QK-RET-001·QK-CHK-001 research R-09·QK-ING-003 R-10)."""
    from qello_knowledge.chunking.version import index_chunking_version
    from qello_knowledge.sync.keys import index_version_id, metadata_schema_version

    version = index_chunking_version(chunking or ChunkingSettings(), code)
    return index_version_id("@cf/baai/bge-m3", 1024, version, metadata_schema_version(code, confluence))


def confluence_on(configs, stored_sources=()) -> bool:
    """활성 Confluence 자료원이 있거나 저장소에 그 종류가 등록돼 있으면 켜짐이다(QK-ING-003 research R-10)."""
    return any(c.enabled and c.kind == "confluence_pages" for c in configs or ()) or any(
        getattr(s, "source_kind", None) == "confluence_pages" for s in stored_sources
    )


def confluence_index_unregistered(version: str) -> bool:
    from qello_knowledge.domain.keyword_rules import INDEX_KEYWORD_RULES

    return version not in INDEX_KEYWORD_RULES


def confluence_source_issues(configs, code=None):
    """저장소를 읽지 않는 검사(`sources check`)의 켜짐 인덱스 버전 대응표 검사(QK-ING-003 research R-10 표)."""
    from qello_knowledge.sources.config import ConfigIssue

    if not confluence_on(configs) or not confluence_index_unregistered(
        current_index_version(code=code, confluence=True)
    ):
        return ()
    names = [c.name for c in configs if c.enabled and c.kind == "confluence_pages"]
    return tuple(ConfigIssue(name, "index_version", "CONFLUENCE_INDEX_VERSION_UNREGISTERED") for name in names)


def confluence_auth_issues(configs, settings):
    """켜진 Confluence 자료원이 쓰는 설정 항목이 비었는지 본다. 값은 보이지 않는다(QK-ING-003 source-config 계약)."""
    from qello_knowledge.sources.config import ConfigIssue
    from qello_knowledge.sources.kinds import KINDS

    issues = []
    for config in configs:
        spec = KINDS.get(config.kind)
        if not config.enabled or spec is None or not spec.extra_auth:
            continue
        for name in (config.auth, *spec.extra_auth):
            if name is None or settings.get(name) is None:
                issues.append(ConfigIssue(config.name, "auth", "AUTH_MISSING"))
                break
    return tuple(issues)


def build_runtime(
    *,
    settings,
    configs,
    policy,
    source,
    chunking=None,
    code=_UNSET,
    targets_factory=None,
    provider_factory=None,
    context=None,
):
    """인자 없이 부르면 지금까지와 같다. 평가용 색인 준비(QK-RET-001)가 청커 설정과 대상·제공자를 바꿔 넣는다.

    코드 청킹은 `code`를 넘기면 그 값이고, `chunking`을 명시하면(평가 준비) 꺼짐, 둘 다 없으면 설정에서 읽는다.
    """
    from qello_knowledge.adapters.postgres.store import PostgresStore
    from qello_knowledge.adapters.postgres.sync_store import PostgresSyncStore
    from qello_knowledge.adapters.postgres.usage import PostgresUsageLedger
    from qello_knowledge.embedding.service import EmbeddingService
    from qello_knowledge.indexer.embedding import security_outgoing_check
    from qello_knowledge.sources.clock import SystemClock

    clock = SystemClock()
    targets = (
        targets_factory(configs, settings, clock)
        if targets_factory
        else source_targets(configs, settings, clock, context)
    )
    url = database_url(source)
    cache = PostgresStore(url)
    store = PostgresSyncStore(url)
    ledger = PostgresUsageLedger(url, budget_settings(settings))
    provider = (provider_factory or workers_ai_provider)(source, settings)
    embedder = EmbeddingService(provider, cache, ledger, budget_settings(settings), security_outgoing_check(policy))
    if code is _UNSET:
        code = None if chunking is not None else code_chunking_from(settings)
    # 등록 이력은 실행 명령이 저장소를 읽은 뒤 더한다(run_command). 조립은 저장소에 연결하지 않는다.
    confluence = confluence_on(configs)
    deps = SyncDependencies(
        store, cache, embedder, policy, chunking or ChunkingSettings(), clock, code_chunking=code, confluence=confluence
    )
    store.current_version = current_spec(deps).id
    return SyncRuntime(tuple(targets), deps, (cache, store, ledger))


def postgres_sync_store(source, current_version):
    from qello_knowledge.adapters.postgres.sync_store import PostgresSyncStore

    return PostgresSyncStore(database_url(source), current_version=current_version)


def positive(value):
    try:
        number = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("positive integer required") from None
    if number < 1:
        raise argparse.ArgumentTypeError("positive integer required")
    return number


def add_sync_parsers(sub, run):
    run.add_argument("--preview", action="store_true")
    run.add_argument("--trigger", choices=("manual", "schedule"), default=None)
    run.add_argument("--allow-remote", action="store_true")
    run.add_argument("--allow-partial-budget", action="store_true")
    run.add_argument("--confirm-takedown", action="store_true")
    run.add_argument("--source")
    runs = sub.add_parser("runs")
    commands = runs.add_subparsers(dest="runs_command", required=True)
    listing = commands.add_parser("list")
    listing.add_argument("--limit", type=positive, default=20)
    show = commands.add_parser("show")
    show.add_argument("run_id")
    show.add_argument("--failures", action="store_true")
    prune = commands.add_parser("prune")
    prune.add_argument("--retention-days", type=positive, default=90)
    prune.add_argument("--allow-remote", action="store_true")
    index = sub.add_parser("index")
    indexes = index.add_subparsers(dest="index_command", required=True)
    status = indexes.add_parser("status")
    activate = indexes.add_parser("activate")
    activate.add_argument("version")
    activate.add_argument("--allow-remote", action="store_true")
    for parser in (listing, show, prune, status, activate):
        parser.add_argument("--json", action="store_true")
        parser.add_argument("--env-file", type=Path, default=Path(".env"))


def _policy_valid(path):
    try:
        data = tomllib.loads(path.read_text())
        if not all(
            isinstance(data.get(key), str) and data[key].strip()
            for key in ("provider", "checked_at", "decision_record")
        ):
            return False
        date.fromisoformat(data["checked_at"])
        return True
    except (OSError, ValueError):
        return False


def _emit(value, json_output=True):
    print(
        json.dumps(
            value, ensure_ascii=False, default=lambda v: v.isoformat() if isinstance(v, (date, datetime)) else str(v)
        )
    )


def _failure(code, reason):
    _emit({"exit_code": code, "error": reason})
    return code


def _refresh_confluence(runtime) -> None:
    """저장소에 Confluence 자료원이 등록돼 있으면 꺼진 설정이어도 켜짐으로 본다(QK-ING-003 R-10, plan 검토 P3)."""
    from dataclasses import replace

    deps = runtime.deps
    load = getattr(deps.store, "load_sources", None)
    if getattr(deps, "confluence", True) or load is None or not confluence_on((), load().values()):
        return
    runtime.deps = replace(deps, confluence=True)
    deps.store.current_version = current_spec(runtime.deps).id


def run_command(args, sync_factory, policy_path):
    source = merge_sources(os.environ, read_env_file(args.env_file))
    settings = load(Entrypoint.INDEX, environ=source, env_file=None)
    report = build_report(settings)
    if not report.ok:
        print(report.to_json() if args.json else report.to_text())
        return 1
    configs, issues = load_checked_sources(args.sources, args.reviews)
    issues = (*issues, *confluence_auth_issues(configs, settings))
    if issues:
        print(render_report(source_report(args.sources, configs, issues), args.json))
        return 1
    code = code_chunking_from(settings)
    if confluence_on(configs) and confluence_index_unregistered(current_index_version(code=code, confluence=True)):
        return _failure(1, "confluence_index_version_unregistered")
    site_valid, material = confluence_review_context(configs, args.reviews, datetime.now(UTC).date())
    policy, issues = load_policy(args.exceptions, configs, kind_material=material)
    if issues:
        from qello_knowledge.security.report import render_security_report, security_report

        print(render_security_report(security_report(args.exceptions, policy, issues), args.json))
        return 1
    label = target_label(source)
    if label == "remote":
        if not args.allow_remote:
            return _failure(3, "remote_confirmation_required")
        if not _policy_valid(policy_path):
            return _failure(1, "store_policy_required")
    options = SyncOptions(
        trigger=args.trigger or "manual",
        target=label,
        source=args.source,
        confirm_takedown=args.confirm_takedown,
        allow_partial_budget=args.allow_partial_budget,
    )
    runtime = None
    try:
        runtime = sync_factory(
            settings=settings, configs=configs, policy=policy, source=source, context={"site_review_valid": site_valid}
        )
        _refresh_confluence(runtime)
        # 저장소를 연 뒤 등록 이력까지 본 두 번째 검사(QK-ING-003 research R-10). 원본 호출 전이다.
        if getattr(runtime.deps, "confluence", False) and confluence_index_unregistered(current_spec(runtime.deps).id):
            return _failure(1, "confluence_index_version_unregistered")
        if args.preview:
            targets = select_targets(runtime.targets, runtime.deps.store.load_sources(), options.source)
            state = runtime.deps.store.index_state()
            spec = current_spec(runtime.deps)
            from dataclasses import replace

            from qello_knowledge.domain.sync import HoldReason

            plans = tuple(
                plan_source(
                    replace(t, holds=t.holds | {HoldReason.INDEX_MISMATCH})
                    if state.active and state.active != spec.id
                    else t,
                    runtime.deps,
                    runtime.deps.store.load_documents(t.source_kind),
                    spec.id,
                    options,
                )
                for t in targets
            )
            result = preview(plans, runtime.deps.embedder, spec.embedding_model, state, options)
            data = preview_dict(result)
            data.update(
                index_version=spec.id,
                rules_version=policy.version,
                chunking_version=spec.chunking_version,
                target=label,
            )
            _emit(data)
            return 0 if result.runnable else 5
        result = run_sync(runtime.targets, runtime.deps, options)
        if args.json:
            _emit(run_dict(result))
        else:
            print(report.to_text())
            print(
                render(
                    result,
                    disabled_sources=(
                        c.name
                        for c in configs
                        if not c.enabled and (options.source is None or c.name == options.source)
                    ),
                )
            )
            if not result.sources:
                print("수집할 자료원 없음")
        return result.exit_code
    except IdentityError as error:
        return _failure(1, error.code)
    except (StoreError, EmbedError):
        return _failure(2, "store_unavailable")
    finally:
        if runtime is not None:
            runtime.close()


def _rescreen(value, policy):
    if isinstance(value, str):
        return safe_text(value, FieldKind.TEXT, policy.output_context("unknown"))
    if isinstance(value, list):
        return [_rescreen(v, policy) for v in value]
    if isinstance(value, dict):
        return {k: _rescreen(v, policy) for k, v in value.items()}
    return value


def query_command(args, store_factory, policy_path):
    source = merge_sources(os.environ, read_env_file(args.env_file))
    label = target_label(source)
    writes = (args.command == "runs" and args.runs_command == "prune") or (
        args.command == "index" and args.index_command == "activate"
    )
    if writes and label == "remote":
        if not args.allow_remote:
            return _failure(3, "remote_confirmation_required")
        if not _policy_valid(policy_path):
            return _failure(1, "store_policy_required")
    configs = None
    settings = load(Entrypoint.INDEX, environ=source, env_file=None)
    report = build_report(settings)
    # 읽기 명령도 코드 청킹 설정으로 현재 버전을 계산한다. 그 값이 형식 오류면 멈춘다(QK-CHK-001 contracts 4절).
    if not report.ok and (writes or dict(report.items).get("QK_CODE_CHUNKING") is SettingStatus.INVALID):
        print(report.to_json() if args.json else report.to_text())
        return 1
    if writes:
        configs, issues = load_checked_sources(Path("config/sources.toml"), Path("config/source_reviews"))
        if issues:
            return _failure(1, "source_review_invalid")
        policy, issues = load_policy(Path("config/security_exceptions.toml"), configs)
        if issues:
            return _failure(1, "security_policy_invalid")
    code = code_chunking_from(settings)
    version_configs = configs if configs is not None else load_sources(Path("config/sources.toml"))[0]
    version = current_index_version(code=code, confluence=confluence_on(version_configs))
    store = None
    lock = None
    try:
        store = store_factory(source, version)
        # 등록 이력까지 보고 현재 버전을 다시 정한다(QK-ING-003 R-10). 읽기 대역 저장소는 이 연산이 없을 수 있다.
        stored = getattr(store, "load_sources", None)
        if stored is not None and confluence_on(version_configs, stored().values()):
            version = current_index_version(code=code, confluence=True)
            store.current_version = version
        if writes:
            targets = tuple(SyncTarget(c.name, c.kind, config=c) for c in configs)
            select_targets(targets, store.load_sources())
            if args.command == "runs":
                lock = store.try_lock(())
                if lock is None:
                    return _failure(6, "already_running")
                select_targets(targets, store.load_sources())
        code = 0
        if args.command == "index":
            if args.index_command == "status":
                state = store.index_state()
                value = {
                    "active": state.active,
                    "ready": list(state.ready),
                    "current": version,
                    "matches": state.active in (None, version),
                }
            else:
                result = activate_first_index(store, args.version)
                value = summary_values(result)
                code = 0 if not result.failed_conditions else 1
        elif args.runs_command == "list":
            value = store.list_runs(args.limit)
        elif args.runs_command == "show":
            value = store.run_detail(args.run_id)
            if value is None:
                return _failure(1, "run_not_found")
            if args.failures:
                value = {**value, "failures": store.run_failures(args.run_id)}
        else:
            value = {"target": label, "rows_deleted": store.prune_runs(args.retention_days)}
        _emit(_rescreen(value, SecurityPolicy()))
        return code
    except IdentityError as error:
        return _failure(1, error.code)
    except (StoreUnavailable, StoreError):
        return _failure(2, "store_unavailable")
    finally:
        if lock is not None:
            lock.close()
        if store is not None:
            store.close()
