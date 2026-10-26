from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest

from qello_knowledge.discord.interactions import parse
from qello_knowledge.domain.discord import QueryJob, QueryStage
from qello_knowledge.domain.generation import GenerationSettings
from qello_knowledge.generation.fake import MemoryLedger, ScriptedProvider
from qello_knowledge.query.pipeline import (
    DeadlineReached,
    QueryParts,
    QueryPipeline,
    embedding_timeout,
    generation_for_remaining,
    guarded_sleep,
)
from tests.unit.discord.bot_builders import ask
from tests.unit.generation.gen_builders import never_blocks, retrieval, three_blocks
from tests.unit.query.bot_runtime import bot_request, bot_runtime


class BotCloser:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def bot_pipeline(runtime_clock, *, provider=None, retrieve_fn=None):
    ledger = MemoryLedger()
    closer = BotCloser()
    provider = provider or ScriptedProvider()
    parts = QueryParts(object(), object(), provider, ledger, never_blocks, (closer,))
    calls = []

    def retrieve(request, deps, settings):
        calls.append(request)
        return retrieval(three_blocks())

    pipeline = QueryPipeline(
        lambda job, remaining: parts,
        clock=runtime_clock.now,
        sleep=runtime_clock.advance,
        retrieve_fn=retrieve_fn or retrieve,
    )
    return pipeline, provider, ledger, closer, calls


@pytest.mark.parametrize("remaining,timeout,deadline", [(55, 20, 45), (44, 19, 44), (15, 5, 15), (7, 1, 7)])
def test_bot_generation_per_query_settings(remaining, timeout, deadline):
    configured = generation_for_remaining(GenerationSettings(), remaining)
    assert configured.timeout_seconds == timeout and configured.deadline == deadline
    short = generation_for_remaining(GenerationSettings(timeout_seconds=2), remaining)
    assert short.timeout_seconds <= 2 and short.deadline <= 9
    with pytest.raises(DeadlineReached):
        generation_for_remaining(GenerationSettings(), 6.99)


def test_bot_embedding_timeout_and_retry_wait_check_before_waiting():
    assert embedding_timeout(55) == 10 and embedding_timeout(4) == 3
    slept = []
    with pytest.raises(DeadlineReached):
        guarded_sleep(lambda: 10.49, 10, slept.append)(0.5)
    assert not slept
    guarded_sleep(lambda: 10.5, 10, slept.append)(0.5)
    assert slept == [0.5]


def test_bot_real_generation_pipeline_updates_original_once_and_closes_parts():
    runtime = bot_runtime()
    pipeline, provider, ledger, closer, calls = bot_pipeline(runtime.clock)
    runtime.jobs._pipeline = pipeline
    body = ask("합성 질문", private=True)
    signature = runtime.key.sign(body, "1000")
    _, _, headers = bot_request(runtime, body, headers=signature)
    run_id = headers["X-QK-Run"]
    assert not calls and not provider.calls and not runtime.fake.requests
    assert runtime.jobs.start(run_id, signature["X-Signature-Ed25519"], "1000")
    runtime.jobs.poll()
    runtime.compute.run_next()
    assert closer.closed and ledger.records[0].run_id == run_id
    runtime.deliveries.run_next()
    assert len(runtime.fake.requests) == 1 and runtime.fake.requests[0].method == "PATCH"
    assert "자료 기준: 색인된 문서" in runtime.fake.requests[0].body["content"]
    assert len(provider.calls) == 1 and len(calls) == 1
    assert 5 + len(provider.calls) + len(runtime.fake.requests) <= 20


def test_bot_less_than_seven_seconds_does_not_start_generation_and_closes():
    runtime = bot_runtime()

    def retrieve_fn(*args):
        runtime.clock.advance(49)
        return retrieval(three_blocks())

    pipeline, provider, ledger, closer, _ = bot_pipeline(runtime.clock, retrieve_fn=retrieve_fn)
    job = QueryJob("run", parse(ask("합성 질문")), 0, 55, 60)
    with pytest.raises(DeadlineReached):
        pipeline(job, lambda stage: None)
    assert not provider.calls and not ledger.records and closer.closed


def test_bot_late_generation_keeps_usage_but_discards_answer_and_closes():
    runtime = bot_runtime()
    entered, release = Event(), Event()

    class BotLateProvider(ScriptedProvider):
        def complete(self, *args, **kwargs):
            entered.set()
            assert release.wait(0.8)
            return super().complete(*args, **kwargs)

    pipeline, provider, ledger, closer, _ = bot_pipeline(runtime.clock, provider=BotLateProvider())
    runtime.jobs._pipeline = pipeline
    body = ask("합성 질문")
    signature = runtime.key.sign(body, "1000")
    _, _, headers = bot_request(runtime, body, headers=signature)
    run_id = headers["X-QK-Run"]
    runtime.jobs.start(run_id, signature["X-Signature-Ed25519"], "1000")
    runtime.jobs.poll()
    with ThreadPoolExecutor(1) as pool:
        future = pool.submit(runtime.compute.run_next)
        try:
            assert entered.wait(0.3)
            runtime.clock.advance(55)
            runtime.jobs.poll()
            runtime.deliveries.run_next()
            assert runtime.jobs.running == 1 and runtime.jobs.stage(run_id) is QueryStage.DONE
            assert "답변이 늦어져" in runtime.fake.requests[0].body["content"]
        finally:
            release.set()
        future.result()
    assert closer.closed and len(ledger.records) == 1 and ledger.records[0].run_id == run_id
    assert len(runtime.fake.requests) == 1 and not runtime.deliveries.pending and runtime.jobs.running == 0


def test_bot_default_factory_builds_fresh_bounded_parts_without_connecting(monkeypatch):
    from qello_knowledge.config.loader import load
    from qello_knowledge.config.registry import Entrypoint
    from qello_knowledge.query.pipeline import postgres_parts
    from tests.unit.fakes import valid_environ

    monkeypatch.setattr("qello_knowledge.indexer.embedding.security_outgoing_check", lambda policy: never_blocks)
    source = valid_environ()
    settings = load(Entrypoint.QUERY, environ=source, env_file=None)
    job = QueryJob("run", parse(ask("합성 질문")), 0, 55, 60)
    parts = postgres_parts(settings, source, object(), job, lambda: 55)
    try:
        assert parts.store._store._deadline() == 55
        assert parts.embedder._retry.max_retries == 1
        assert parts.embedder._provider._transport.timeout == 10
        assert len(parts.closers) == 3 and all(p._conn is None for p in parts.closers)
    finally:
        for closer in parts.closers:
            closer.close()


def test_bot_all_closers_run_even_if_one_fails():
    from dataclasses import replace

    from tests.unit.discord.bot_builders import FakeClock

    pipeline, _, _, closer, _ = bot_pipeline(FakeClock())
    factory = pipeline._factory

    class BotFailClose:
        def close(self):
            raise OSError("synthetic close detail")

    pipeline._factory = lambda job, remaining: replace(factory(job, remaining), closers=(closer, BotFailClose()))
    with pytest.raises(OSError, match="질의 연결 정리 실패"):
        pipeline(QueryJob("run", parse(ask("합성 질문")), 0, 55, 60), lambda stage: None)
    assert closer.closed
