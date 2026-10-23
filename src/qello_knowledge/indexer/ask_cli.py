"""`qk-index ask`(QK-GEN-001 contracts/cli.md, research R-10).

질문은 표준 입력에서만 읽는다. 검색(QK-RET-001)과 생성을 이어 실행하고 답변 본문·출처·상태·요약을 보인다.
기본은 가짜 생성 제공자이며 사용량을 기록하지 않는다. `--provider workers-ai`일 때만 실제 생성 모델을 부르고, 그 전에 예상 Neurons를 표준 오류로 알린다.
출력·기록에 질문 원문을 넣지 않는다(spec FR-012). 종료 코드: 0 답변·확인 불가, 1 검색 실패·전송 차단·생성 실패, 2 인자·설정 오류, 3 원격 대상인데 `--allow-remote` 없음.
"""  # noqa: E501

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, TextIO

from qello_knowledge.config.check import budget_settings, generation_settings
from qello_knowledge.config.loader import load, merge_sources, read_env_file
from qello_knowledge.config.registry import Entrypoint
from qello_knowledge.domain.generation import AnswerUsageToday, GenerationRequest, GenerationResult, GenerationStatus
from qello_knowledge.domain.retrieval import RetrievalMode, RetrievalRequest, RetrievalResult, RetrievalSettings
from qello_knowledge.domain.store import SearchFilter, StoreError
from qello_knowledge.indexer.search_cli import EXIT_ARGS, EXIT_FAILURE, EXIT_OK, EXIT_REMOTE, _overrides, _plain

FAKE = "fake"
WORKERS_AI = "workers-ai"


@dataclass(frozen=True)
class AskParts:
    store: Any  # RetrievalStore
    embedder: Any
    provider: Any  # GenerationProvider
    ledger: Any  # GenerationLedger(가짜 제공자면 메모리 장부)
    usage_reader: Any | None  # 가짜 제공자일 때 오늘 사용량을 읽기만 하는 저장소 장부
    closers: tuple = ()


AskFactory = Callable[..., AskParts]


def postgres_ask(
    settings,
    source,
    policy,
    *,
    provider_name: str = FAKE,
    embedding_provider=None,
    generation_provider=None,
    transport=None,
) -> AskParts:
    """기본 조립. `embedding_provider`·`generation_provider`·`transport`는 시험용 주입 자리다."""
    from qello_knowledge.adapters.postgres.connection import database_url
    from qello_knowledge.adapters.postgres.generation_usage import PostgresGenerationLedger
    from qello_knowledge.generation.fake import MemoryLedger, ScriptedProvider
    from qello_knowledge.indexer.search_cli import postgres_search

    search = postgres_search(settings, source, policy, provider=embedding_provider)
    budget = budget_settings(settings)
    reserve = budget.query_reserve if budget is not None else 3000
    db_ledger = PostgresGenerationLedger(database_url(source), reserve)
    if provider_name == WORKERS_AI:
        if generation_provider is None:
            from qello_knowledge.adapters.workers_ai.generation import WorkersAiGenerationProvider

            generation_provider = WorkersAiGenerationProvider(
                source["CLOUDFLARE_ACCOUNT_ID"], settings.get("CLOUDFLARE_API_TOKEN"), transport
            )
        return AskParts(
            search.store, search.embedder, generation_provider, db_ledger, None, (*search.closers, db_ledger)
        )
    provider = generation_provider or ScriptedProvider()
    ledger = MemoryLedger(query_reserve=reserve)
    return AskParts(search.store, search.embedder, provider, ledger, db_ledger, (*search.closers, db_ledger))


def add_ask_parser(sub: argparse._SubParsersAction) -> None:
    ask = sub.add_parser("ask", help="표준 입력의 질문 하나로 검색하고 답변을 생성한다. 기본은 가짜 생성 제공자")
    ask.add_argument("--provider", choices=(FAKE, WORKERS_AI), default=FAKE)
    ask.add_argument("--prompt", choices=("gen-p1", "gen-base"), default=None)
    ask.add_argument("--query-rule", choices=("kw-query-v1", "kw-query-raw"), default=None)
    ask.add_argument("--candidates", type=int, default=None)
    ask.add_argument("--budget", type=int, default=None)
    ask.add_argument("--expand-top", type=int, default=None)
    ask.add_argument("--source-kind", action="append", default=[])
    ask.add_argument("--allow-remote", action="store_true")
    ask.add_argument("--sources", type=Path, default=Path("config/sources.toml"))
    ask.add_argument("--exceptions", type=Path, default=Path("config/security_exceptions.toml"))
    ask.add_argument("--json", action="store_true")
    ask.add_argument("--env-file", type=Path, default=Path(".env"))


def _usage_dict(usage: AnswerUsageToday | None) -> dict | None:
    if usage is None:
        return None
    return {
        "usage_day": usage.usage_day.isoformat(),
        "generation_used": usage.generation_used,
        "query_embedding_used": usage.query_embedding_used,
        "answer_total": usage.answer_total,
        "index_used": usage.index_used,
        "day_total": usage.day_total,
        "query_reserve": usage.query_reserve,
        "query_reserve_exceeded": usage.query_reserve_exceeded,
    }


def _summary_dict(result: GenerationResult, fake: bool, usage: AnswerUsageToday | None) -> dict:
    s = result.summary
    generation_calls = 0 if fake else s.generation_calls
    data = _plain(s)
    data.update(
        {
            "generation_calls": generation_calls,
            "total_calls": generation_calls + (s.total_calls - s.generation_calls),
            "usage_today": _usage_dict(usage),
            "fake_provider": fake,
        }
    )
    return data


def _citation_line(c) -> str:
    modified = c.source_modified_at.date().isoformat() if c.source_modified_at else "미상"
    version, collected = c.source_version[:12], c.collected_at.date()
    return f"[{c.source_id}] {c.title} — {c.source_url} (버전 {version}, 수정 {modified}, 수집 {collected})"


def _render(result: GenerationResult, target: str, provider: str, usage, json_output: bool) -> str:
    fake = provider == FAKE
    summary = _summary_dict(result, fake, usage)
    citations = [
        {
            "source_id": c.source_id,
            "title": c.title,
            "source_url": c.source_url,
            "source_version": c.source_version,
            "source_modified_at": c.source_modified_at.isoformat() if c.source_modified_at else None,
            "collected_at": c.collected_at.isoformat(),
        }
        for c in result.citations
    ]
    if json_output:
        data = {
            "target": target,
            "provider": provider,
            "result": {
                "status": result.status.value,
                "answer": result.answer,
                "citations": citations,
                "summary": summary,
                "retrieval": _plain(result.retrieval),
            },
        }
        return json.dumps(data, ensure_ascii=False, default=str)
    s = result.summary
    lines = [f"대상: {target} | 제공자: {provider} | 프롬프트: {s.prompt_version} | 상태: {result.status.value}"]
    if result.answer:
        lines += ["답변:", result.answer]
    if result.citations:
        lines += ["출처:", *(_citation_line(c) for c in result.citations)]
    flags = [
        label
        for flag, label in (
            (s.flags.unsupported_answer, "출처 확인 안 됨"),
            (s.flags.truncated, "출력 잘림"),
            (s.flags.usage_record_failed, "사용량 기록 실패"),
        )
        if flag
    ]
    if flags:
        lines.append("표시: " + " / ".join(flags))
    reason = s.failure or s.cannot_confirm_reason
    if reason is not None or s.retrieval_failure:
        lines.append(f"사유: {s.retrieval_failure or reason.value}")
    dropped = ", ".join(f"{d.source_id} {'/'.join(d.rules)}" for d in s.dropped)
    lines.append(
        f"요약: 묶음 {s.blocks_sent}/{s.blocks_sent + len(s.dropped)}"
        + (f"(뺀 {len(s.dropped)}: {dropped})" if dropped else "")
        + f" · 입력 {s.input_tokens}(예상 {s.estimated_input_tokens}) · 출력 {s.output_tokens}"
        + f" · {s.neurons:.2f} Neurons({'측정' if s.measured else '추정'}) · 시도 {s.attempts} · {s.latency_ms} ms"
        + f" · 호출 {summary['total_calls']}(생성 {summary['generation_calls']})"
    )  # fmt: skip
    lines.append(
        f"후처리: 지운 인용 {s.removed_citations} · 인식 못 한 꼴 {s.unrecognized_citations}"
        f" · 인용 없는 문장 {s.uncited_sentences} · 지운 URL {s.removed_urls} · 지운 출처 줄 {s.removed_source_lines}"
        f" · 무력화 {s.neutralized}"
    )
    if usage is not None:
        note = " · 가짜 실행은 기록하지 않음" if fake else ""
        lines.append(
            f"오늘 사용량: 생성 {usage.generation_used:.2f} · 질의 임베딩 {usage.query_embedding_used:.2f}"
            f" · 질의응답 합계 {usage.answer_total:.2f} / 예비분 {usage.query_reserve}"
            f" · 하루 전체 {usage.day_total:.2f}"
            f" (qk-index usage의 query_used는 질의 임베딩만 센다){note}"
        )
    shape = s.response_shape
    if shape is not None and not fake:
        lines.append(
            f"응답 꼴: {shape.parsed_as} · usage {'있음' if shape.has_usage else '없음'}"
            f" · Neurons 헤더 {'있음' if shape.has_neurons_header else '없음'}"
            f" · 종료 사유 {'있음' if shape.has_finish_reason else '없음'}"
        )
    r = result.retrieval
    lines.append(
        f"검색: index_version={r.index_version} blocks={r.block_count} tokens={r.used_tokens}/{r.budget}"
        f" external={r.external_calls}"
    )
    return "\n".join(lines)


def _exit_code(result: GenerationResult) -> int:
    return EXIT_OK if result.status in (GenerationStatus.ANSWERED, GenerationStatus.CANNOT_CONFIRM) else EXIT_FAILURE


def run_ask(args: argparse.Namespace, factory: AskFactory, stdin: TextIO | None = None) -> int:
    from qello_knowledge.adapters.postgres.connection import target_label
    from qello_knowledge.generation import GenerationDeps, check_settings, generate
    from qello_knowledge.generation.prompts import prompt_spec
    from qello_knowledge.generation.render import render
    from qello_knowledge.indexer.embedding import security_outgoing_check
    from qello_knowledge.indexer.search_cli import query_retry_delay
    from qello_knowledge.retrieval import RetrievalDeps, retrieve
    from qello_knowledge.security.policy import load_policy
    from qello_knowledge.sources.config import load_sources

    question = (stdin or sys.stdin).read()
    if not question.strip():
        print(json.dumps({"exit_code": EXIT_ARGS, "error": "empty_question"}))
        return EXIT_ARGS
    source = merge_sources(os.environ, read_env_file(args.env_file))
    target = target_label(source)
    if target == "remote" and not args.allow_remote:
        print(json.dumps({"exit_code": EXIT_REMOTE, "error": "remote_confirmation_required"}))
        return EXIT_REMOTE
    settings = load(Entrypoint.INDEX, environ=source, env_file=None)
    gen = generation_settings(settings)
    try:
        base = RetrievalSettings(context_budget=int(str(settings.get("QK_RETRIEVAL_CONTEXT_BUDGET"))))
        configured = base.with_overrides(_overrides(args))
    except (ValueError, TypeError, KeyError):
        configured = None
    if gen is not None and args.prompt:
        gen = replace(gen, prompt_version=args.prompt)
    if gen is None or configured is None or check_settings(gen, configured):
        print(json.dumps({"exit_code": EXIT_ARGS, "error": "settings_out_of_range"}))
        return EXIT_ARGS
    configs, issues = load_sources(args.sources)
    policy, policy_issues = load_policy(args.exceptions, configs) if not issues else (None, issues)
    if issues or policy_issues:
        print(json.dumps({"exit_code": EXIT_FAILURE, "error": "policy_invalid"}))
        return EXIT_FAILURE

    parts = factory(settings, source, policy, provider_name=args.provider)
    usage = None
    try:
        request = RetrievalRequest(
            question, mode=RetrievalMode.HYBRID, filters=SearchFilter(source_kinds=tuple(args.source_kind))
        )
        try:
            retrieval = retrieve(request, RetrievalDeps(store=parts.store, embedder=parts.embedder), configured)
        except StoreError:
            retrieval = RetrievalResult(status="store_unavailable")
        if args.provider == WORKERS_AI and retrieval.context:
            rendered = render(question.strip(), retrieval.context, prompt_spec(gen.prompt_version), gen)
            estimate = gen.estimated_neurons(rendered.estimated_input_tokens, gen.max_tokens)
            print(
                json.dumps({"model": gen.model_id, "prompt": prompt_spec(gen.prompt_version).version,
                            "estimated_input_tokens": rendered.estimated_input_tokens,
                            "estimated_neurons": round(estimate, 2), "with_retry_max": round(2 * estimate, 2)}),
                file=sys.stderr,
            )  # fmt: skip
        deps = GenerationDeps(
            provider=parts.provider,
            ledger=parts.ledger,
            outgoing_check=security_outgoing_check(policy),
            retry_delay=query_retry_delay,
        )
        result = generate(GenerationRequest(question, retrieval), deps, gen)
        usage = result.summary.usage_today
        if parts.usage_reader is not None:
            try:
                usage = parts.usage_reader.today()
            except Exception:  # noqa: BLE001 - 표시용 읽기다. 실패해도 답은 보인다
                usage = None
    finally:
        for closer in reversed(parts.closers):
            closer.close()
    print(_render(result, target, args.provider, usage, args.json))
    return _exit_code(result)


__all__: Sequence[str] = ["AskParts", "add_ask_parser", "postgres_ask", "run_ask"]
