"""기존 검색·생성 경계를 질의별 마감과 연결한다. 원본 CLI는 변경하지 않는다."""

from __future__ import annotations

import math
from contextlib import ExitStack
from dataclasses import dataclass, replace
from time import monotonic, sleep

from qello_knowledge.config.check import budget_settings, generation_settings
from qello_knowledge.discord.render import render
from qello_knowledge.domain.discord import QueryStage
from qello_knowledge.domain.generation import GenerationRequest, GenerationSettings
from qello_knowledge.domain.retrieval import RetrievalRequest, RetrievalSettings
from qello_knowledge.domain.source_config import RetryPolicy
from qello_knowledge.generation import GenerationDeps, generate
from qello_knowledge.indexer.search_cli import query_retry_delay
from qello_knowledge.retrieval import RetrievalDeps, retrieve


class DeadlineReached(TimeoutError):
    """질의 실행을 더 시작하지 않는다. 문구에 원문이나 자격 정보를 넣지 않는다."""


def generation_for_remaining(settings: GenerationSettings, remaining: float) -> GenerationSettings:
    if remaining < 7:
        raise DeadlineReached("질의 마감")
    return replace(
        settings,
        timeout_seconds=min(settings.timeout_seconds, math.floor((remaining - 5) / 2)),
        deadline_seconds=min(settings.deadline, remaining),
    )


def embedding_timeout(remaining: float) -> float:
    if remaining <= 1:
        raise DeadlineReached("질의 마감")
    return min(10, remaining - 1)


def guarded_sleep(remaining, call_timeout, sleeper):
    def wait(seconds):
        timeout = call_timeout() if callable(call_timeout) else call_timeout
        if remaining() - seconds < timeout:
            raise DeadlineReached("질의 마감")
        sleeper(seconds)
        if remaining() <= 0:
            raise DeadlineReached("질의 마감")

    return wait


@dataclass(frozen=True)
class QueryParts:
    store: object
    embedder: object
    provider: object
    ledger: object
    outgoing_check: object
    closers: tuple = ()


class _DeadlineStore:
    def __init__(self, store):
        self._store = store

    def __getattr__(self, name):
        from qello_knowledge.adapters.postgres.store import StoreDeadline

        method = getattr(self._store, name)

        def call(*args, **kwargs):
            try:
                return method(*args, **kwargs)
            except StoreDeadline:
                raise DeadlineReached("질의 마감") from None

        return call


class _EmbeddingTransport:
    def __init__(self, remaining):
        self.remaining = remaining
        self.timeout = embedding_timeout(remaining())

    def post(self, url, headers, body):
        from qello_knowledge.adapters.workers_ai.rest import UrllibTransport

        self.timeout = embedding_timeout(self.remaining())
        return UrllibTransport(timeout=self.timeout).post(url, headers, body)


def postgres_parts(settings, source, policy, job, remaining, *, sleeper=sleep):
    from qello_knowledge.adapters.postgres.connection import database_url
    from qello_knowledge.adapters.postgres.generation_usage import PostgresGenerationLedger
    from qello_knowledge.adapters.postgres.store import PostgresStore
    from qello_knowledge.adapters.postgres.usage import PostgresUsageLedger
    from qello_knowledge.adapters.workers_ai.generation import WorkersAiGenerationProvider
    from qello_knowledge.adapters.workers_ai.rest import WorkersAiRestProvider
    from qello_knowledge.embedding.service import EmbeddingService
    from qello_knowledge.indexer.embedding import security_outgoing_check

    budget = budget_settings(settings)
    if budget is None:
        raise ValueError("질의 예산 설정 오류")
    url = database_url(source)
    with ExitStack() as stack:
        store = stack.enter_context(PostgresStore(url, deadline=remaining))
        embedding_ledger = stack.enter_context(PostgresUsageLedger(url, budget))
        generation_ledger = stack.enter_context(PostgresGenerationLedger(url, budget.query_reserve))
        check = security_outgoing_check(policy)
        transport = _EmbeddingTransport(remaining)
        provider = WorkersAiRestProvider(
            source["CLOUDFLARE_ACCOUNT_ID"], settings.get("CLOUDFLARE_API_TOKEN"), transport
        )
        embedder = EmbeddingService(
            provider,
            store,
            embedding_ledger,
            budget,
            check,
            retry_policy=RetryPolicy(max_retries=1),
            retry_delay=query_retry_delay,
            sleep=guarded_sleep(remaining, lambda: transport.timeout, sleeper),
        )
        generation_provider = WorkersAiGenerationProvider(
            source["CLOUDFLARE_ACCOUNT_ID"], settings.get("CLOUDFLARE_API_TOKEN")
        )
        parts = QueryParts(
            _DeadlineStore(store),
            embedder,
            generation_provider,
            generation_ledger,
            check,
            (store, embedding_ledger, generation_ledger),
        )
        stack.pop_all()
        return parts


class QueryPipeline:
    def __init__(
        self,
        factory,
        *,
        generation=None,
        retrieval=None,
        clock=monotonic,
        sleep=sleep,
        retrieve_fn=retrieve,
        generate_fn=generate,
        renderer=render,
        render_options=None,
        call_limit=20,
    ):
        self._factory = factory
        self._generation = generation or GenerationSettings()
        self._retrieval = retrieval or RetrievalSettings()
        self._clock, self._sleep = clock, sleep
        self._retrieve, self._generate, self._render = retrieve_fn, generate_fn, renderer
        self._render_options = render_options or {}
        self._call_limit = call_limit

    def __call__(self, job, stage):
        def remaining():
            return job.query_deadline - self._clock()

        if remaining() <= 0:
            raise DeadlineReached("질의 마감")
        parts = self._factory(job, remaining)
        try:
            stage(QueryStage.RETRIEVING)
            result = self._retrieve(
                RetrievalRequest(job.interaction.question or ""),
                RetrievalDeps(parts.store, parts.embedder),
                self._retrieval,
            )
            if result.summary.external_calls > 7:
                raise ValueError("검색 호출 상한")
            configured = generation_for_remaining(self._generation, remaining())
            stage(QueryStage.GENERATING)
            answer = self._generate(
                GenerationRequest(job.interaction.question or "", result, run_id=job.run_id),
                GenerationDeps(
                    parts.provider,
                    parts.ledger,
                    parts.outgoing_check,
                    retry_delay=query_retry_delay,
                    monotonic=self._clock,
                    sleep=guarded_sleep(remaining, configured.timeout_seconds, self._sleep),
                ),
                configured,
            )
            if remaining() <= 0:
                raise DeadlineReached("질의 마감")
            if answer.summary.generation_calls > 4:
                raise ValueError("생성 호출 상한")
            stage(QueryStage.RENDERING)
            reply = self._render(answer, private=job.interaction.private, **self._render_options)
            if (
                result.summary.external_calls + answer.summary.generation_calls + len(reply.messages) * 2
                > self._call_limit
            ):
                raise ValueError("질의 호출 상한")
            return reply
        finally:
            # 늦게 끝난 생성도 사용량을 먼저 기록한 뒤 연결을 닫는다.
            close_failed = False
            for closer in reversed(parts.closers):
                try:
                    closer.close()
                except Exception:
                    close_failed = True
            if close_failed:
                raise OSError("질의 연결 정리 실패") from None


def configured_pipeline(settings, source, policy):
    gen = generation_settings(settings)
    if gen is None:
        raise ValueError("질의 생성 설정 오류")
    return QueryPipeline(
        lambda job, remaining: postgres_parts(settings, source, policy, job, remaining),
        generation=gen,
        retrieval=RetrievalSettings(context_budget=int(settings.get("QK_RETRIEVAL_CONTEXT_BUDGET"))),
        call_limit=int(settings.get("QK_QUERY_CALL_LIMIT")),
        render_options={
            "max_messages": int(settings.get("QK_DISCORD_MAX_MESSAGES")),
            "title_max_chars": int(settings.get("QK_DISCORD_TITLE_MAX_CHARS")),
            "link_max_chars": int(settings.get("QK_DISCORD_LINK_MAX_CHARS")),
        },
    )
