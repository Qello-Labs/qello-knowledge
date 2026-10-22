"""`qk-index search`(QK-RET-001 contracts/cli.md 1절, research R-07·R-10).

질문은 표준 입력에서만 읽는다. 출력·기록에 질문 원문, 검색어 낱말, 청크 본문을 넣지 않는다(spec FR-008·FR-025).
종료 코드: 0 `ok`·`no_results`, 1 실패 종류, 2 인자·설정 범위 오류, 3 원격 대상인데 `--allow-remote` 없음.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Mapping, Sequence
from dataclasses import asdict, dataclass, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, TextIO

from qello_knowledge.config.loader import load, merge_sources, read_env_file
from qello_knowledge.config.registry import Entrypoint
from qello_knowledge.domain.retrieval import RetrievalMode, RetrievalRequest, RetrievalResult, RetrievalSettings
from qello_knowledge.domain.source_config import RetryPolicy
from qello_knowledge.domain.store import SearchFilter, StoreError

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_ARGS = 2
EXIT_REMOTE = 3


@dataclass(frozen=True)
class SearchParts:
    store: Any  # RetrievalStore + source_revisions()
    embedder: Any
    closers: tuple = ()


SearchFactory = Callable[..., SearchParts]


def query_retry_delay(attempt: int, retry_after_seconds: float | None) -> float:
    """질의 경로 재시도 대기. 제공자가 알려 준 값을 따르되 2초를 넘기지 않는다(research R-07)."""
    return min(0.5 if retry_after_seconds is None else max(0.0, retry_after_seconds), 2.0)


def postgres_search(settings, source: Mapping[str, str], policy, *, provider=None) -> SearchParts:
    """기본 조립: 운영·로컬 저장소와 Workers AI REST 제공자. `provider`는 시험용 주입 자리다."""
    from qello_knowledge.adapters.postgres.connection import database_url
    from qello_knowledge.adapters.postgres.store import PostgresStore
    from qello_knowledge.adapters.postgres.usage import PostgresUsageLedger
    from qello_knowledge.config.check import budget_settings
    from qello_knowledge.embedding.service import EmbeddingService
    from qello_knowledge.indexer.embedding import security_outgoing_check
    from qello_knowledge.indexer.sync_cli import workers_ai_provider

    url = database_url(source)
    budget = budget_settings(settings)
    store = PostgresStore(url)
    ledger = PostgresUsageLedger(url, budget)
    embedder = EmbeddingService(
        provider or workers_ai_provider(source, settings),
        store,
        ledger,
        budget,
        security_outgoing_check(policy),
        retry_policy=RetryPolicy(max_retries=1),
        retry_delay=query_retry_delay,
    )
    return SearchParts(store=store, embedder=embedder, closers=(store, ledger))


def add_search_parser(sub: argparse._SubParsersAction) -> None:
    search = sub.add_parser("search", help="표준 입력의 질문 하나로 검색한다. 생성은 하지 않는다")
    search.add_argument("--mode", choices=[m.value for m in RetrievalMode], default=RetrievalMode.HYBRID.value)
    search.add_argument("--query-rule", choices=("kw-query-v1", "kw-query-raw"), default=None)
    search.add_argument("--candidates", type=int, default=None)
    search.add_argument("--budget", type=int, default=None)
    search.add_argument("--expand-top", type=int, default=None)
    search.add_argument("--ranks-only", action="store_true")
    search.add_argument("--source-kind", action="append", default=[])
    search.add_argument("--allow-remote", action="store_true")
    search.add_argument("--sources", type=Path, default=Path("config/sources.toml"))
    search.add_argument("--exceptions", type=Path, default=Path("config/security_exceptions.toml"))
    search.add_argument("--json", action="store_true")
    search.add_argument("--env-file", type=Path, default=Path(".env"))


def _plain(value: object) -> object:
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        return {k: _plain(v) for k, v in asdict(value).items()}
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


def _summary(result: RetrievalResult) -> dict:
    s = result.summary
    return {
        "mode": s.mode.value,
        "candidates": s.candidates,
        "rrf_k": s.rrf_k,
        "query_rule": s.query_rule,
        "index_rule": s.index_rule,
        "index_version": s.index_version,
        "omitted": [{"search": o.search, "reason": o.reason.value, "detail": o.detail} for o in s.omitted],
        "vector_count": s.vector_count,
        "keyword_count": s.keyword_count,
        "keyword_terms": s.keyword_terms,
        "block_count": s.block_count,
        "used_tokens": s.used_tokens,
        "budget": s.budget,
        "skipped": [{"chunk_id": k.chunk_id, "role": k.role.value, "reason": k.reason.value} for k in s.skipped],
        "embedding_calls": s.embedding.provider_calls if s.embedding else 0,
        "embedding_neurons": s.embedding.neurons if s.embedding else 0.0,
        "external_calls": s.external_calls,
        "source_revisions": dict(s.source_revisions),
    }


def _hits(result: RetrievalResult) -> list[dict]:
    return [
        {
            "rank": h.rank,
            "chunk_id": h.chunk_id,
            "score": h.score,
            "vector_rank": h.vector_rank,
            "keyword_rank": h.keyword_rank,
            "keyword_matched": h.keyword_matched,
            "source_url": h.provenance.source_url,
            "heading_path": list(h.provenance.heading_path),
        }
        for h in result.hits
    ]


def _render(result: RetrievalResult, target: str, json_output: bool) -> str:
    summary = _summary(result)
    if json_output:
        blocks = [
            {
                "source_id": b.source_id,
                "rank": b.rank,
                "source_url": b.source_url,
                "chunks": [c.chunk_id for c in b.chunks],
            }
            for b in result.context
        ]
        data = {"status": result.status, "target": target, "hits": _hits(result), "context": blocks, "summary": summary}
        return json.dumps(_plain(data), ensure_ascii=False, default=str)
    lines = [
        f"target={target} mode={summary['mode']} index_version={summary['index_version']}"
        f" index_rule={summary['index_rule']} query_rule={summary['query_rule']}",
        f"status={result.status}",
    ]
    for h in _hits(result):
        path = " > ".join(h["heading_path"])
        lines.append(
            f"{h['rank']:>3} score={h['score']:.5f} vector={h['vector_rank']} keyword={h['keyword_rank']}"
            f" {h['source_url']} {path}".rstrip()
        )
    lines.append(
        f"context: blocks={summary['block_count']} tokens={summary['used_tokens']}/{summary['budget']}"
        f" skipped={len(summary['skipped'])}"
    )
    for omitted in summary["omitted"]:
        lines.append(f"omitted: {omitted['search']} {omitted['reason']}")
    lines.append(
        f"calls: external={summary['external_calls']} embedding={summary['embedding_calls']}"
        f" neurons={summary['embedding_neurons']:.4f}"
    )
    for name, revision in sorted(summary["source_revisions"].items()):
        lines.append(f"source_revision: {name} {revision}")
    return "\n".join(lines)


def _overrides(args: argparse.Namespace) -> dict[str, object]:
    values: dict[str, object] = {}
    for name, key in (("candidates", "candidates"), ("budget", "context_budget"), ("expand_top", "expand_top")):
        value = getattr(args, name)
        if value is not None:
            values[key] = value
    if args.query_rule is not None:
        values["query_rule"] = args.query_rule
    return values


def run_search(args: argparse.Namespace, factory: SearchFactory, stdin: TextIO | None = None) -> int:
    from qello_knowledge.adapters.postgres.connection import target_label
    from qello_knowledge.retrieval import RetrievalDeps, retrieve
    from qello_knowledge.security.policy import load_policy
    from qello_knowledge.sources.config import load_sources

    question = (stdin or sys.stdin).read()
    source = merge_sources(os.environ, read_env_file(args.env_file))
    target = target_label(source)
    if target == "remote" and not args.allow_remote:
        print(json.dumps({"exit_code": EXIT_REMOTE, "error": "remote_confirmation_required"}))
        return EXIT_REMOTE
    settings = load(Entrypoint.INDEX, environ=source, env_file=None)
    try:
        base = RetrievalSettings(context_budget=int(str(settings.get("QK_RETRIEVAL_CONTEXT_BUDGET"))))
        configured = base.with_overrides(_overrides(args))
    except (ValueError, TypeError, KeyError):
        print(json.dumps({"exit_code": EXIT_ARGS, "error": "settings_out_of_range"}))
        return EXIT_ARGS
    configs, issues = load_sources(args.sources)
    policy, policy_issues = load_policy(args.exceptions, configs) if not issues else (None, issues)
    if issues or policy_issues:
        print(json.dumps({"exit_code": EXIT_FAILURE, "error": "policy_invalid"}))
        return EXIT_FAILURE
    filters = SearchFilter(source_kinds=tuple(args.source_kind))
    request = RetrievalRequest(
        question, mode=RetrievalMode(args.mode), filters=filters, want_context=not args.ranks_only
    )
    parts = factory(settings, source, policy)
    try:
        result = retrieve(request, RetrievalDeps(store=parts.store, embedder=parts.embedder), configured)
        if result.failure is None:
            from dataclasses import replace

            result = replace(result, summary=replace(result.summary, source_revisions=parts.store.source_revisions()))
    except StoreError:
        result = RetrievalResult(status="store_unavailable")
    finally:
        for closer in reversed(parts.closers):
            closer.close()
    print(_render(result, target, args.json))
    return EXIT_OK if result.failure is None else EXIT_FAILURE


__all__: Sequence[str] = ["SearchParts", "add_search_parser", "postgres_search", "query_retry_delay", "run_search"]
