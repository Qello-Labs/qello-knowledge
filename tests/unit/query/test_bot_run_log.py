import json

import pytest

from qello_knowledge.domain.discord import RenderedReply
from qello_knowledge.domain.embedding import ProviderFailureKind
from qello_knowledge.domain.generation import GenerationFailure, ProviderReply
from qello_knowledge.embedding.fake import FakeEmbeddingProvider
from qello_knowledge.generation import generate
from qello_knowledge.generation.fake import MemoryLedger, ScriptedProvider
from qello_knowledge.ports.embedder import ProviderFailure
from qello_knowledge.ports.generator import GenerationProviderFailure
from qello_knowledge.query.pipeline import QueryCalls, QueryParts, QueryPipeline
from qello_knowledge.query.server import write_run_log
from qello_knowledge.retrieval import retrieve
from tests.unit.discord.bot_builders import ask, component
from tests.unit.generation.gen_builders import never_blocks
from tests.unit.query.bot_runtime import bot_request, bot_runtime
from tests.unit.retrieval.fakes import (
    FakeRetrievalStore,
    document_context,
    keyword_result,
    query_embedder,
    vector_result,
)


def bot_logged_pipeline(runtime, *, provider=None, embedding_provider=None):
    calls = QueryCalls()
    store = FakeRetrievalStore(
        vector=vector_result(1), keyword=keyword_result((1, 1)), context=document_context({1: [1]})
    )
    embedder, embedding_provider, embedding_ledger = query_embedder(provider=embedding_provider)
    embedder._provider = calls.track(embedding_provider, "retrieve", {"embed_texts"})
    embedder._ledger = calls.track(embedding_ledger, "retrieve", {"record"}, embedding_usage=True)
    provider = provider or ScriptedProvider()
    ledger = MemoryLedger()
    parts = QueryParts(
        calls.track(store, "retrieve", {"search_vector", "search_keyword_terms", "chunk_context"}),
        embedder,
        calls.track(provider, "generate", {"complete"}),
        calls.track(ledger, "generate", {"record"}),
        never_blocks,
        counter=calls,
    )

    def bot_retrieve(*args):
        runtime.clock.advance(0.9)
        return retrieve(*args)

    def bot_generate(*args):
        runtime.clock.advance(2)
        return generate(*args)

    runtime.jobs._pipeline = QueryPipeline(
        lambda job, remaining: parts,
        clock=runtime.clock.now,
        sleep=runtime.clock.advance,
        retrieve_fn=bot_retrieve,
        generate_fn=bot_generate,
    )
    return store, embedding_provider, embedding_ledger, provider, ledger


def bot_start_logged(runtime):
    def bot_access(item):
        runtime.clock.advance(0.04)
        return True

    runtime.app.access_check = bot_access
    body = ask("합성 질문")
    signed = runtime.key.sign(body, "1000")
    _, _, response = bot_request(runtime, body, headers=signed)
    run_id = response["X-QK-Run"]
    assert runtime.jobs.start(run_id, signed["X-Signature-Ed25519"], "1000")
    runtime.jobs.poll()
    return run_id


def test_bot_one_log_measures_all_phases_actual_calls_and_neuron_basis(capsys):
    runtime = bot_runtime(script=[(500, {}, 0.2), (200, {}, 0.3)], on_finished=write_run_log)
    store, embedding_provider, embedding_ledger, provider, ledger = bot_logged_pipeline(runtime)
    run_id = bot_start_logged(runtime)
    runtime.compute.run_next()
    runtime.deliveries.run_next()
    capture = capsys.readouterr()
    assert capture.out == "" and len(capture.err.splitlines()) == 1
    record = json.loads(capture.err)
    assert record["run_id"] == run_id
    assert record["timings_ms"] == pytest.approx(
        {"first_response": 40, "retrieve": 900, "generate": 2000, "deliver": 1500}, abs=1
    )
    assert (
        record["calls"]
        == {
            "retrieve": len(store.calls) + len(embedding_provider.calls) + len(embedding_ledger.rows),
            "generate": len(provider.calls) + len(ledger.records),
            "deliver": len(runtime.fake.requests),
        }
        == {"retrieve": 5, "generate": 2, "deliver": 2}
    )
    assert sum(record["calls"].values()) <= 20
    assert record["deliver_retries"] == 1 and record["deliver_failure"] is None
    assert type(record["generation_summary"]["measured"]) is bool
    assert "neurons" in record["retrieval_summary"] and "estimated_neurons" in record["retrieval_summary"]
    assert all(
        type(value) in (int, float, bool)
        for name in ("retrieval_summary", "generation_summary")
        for value in record[name].values()
    )


def test_bot_rejection_log_has_zero_unused_phases(capsys):
    runtime = bot_runtime()
    runtime.app.on_response = write_run_log
    bot_request(runtime, component())
    record = json.loads(capsys.readouterr().err)
    assert set(record["timings_ms"]) == {"first_response", "retrieve", "generate", "deliver"}
    assert record["calls"] == {"retrieve": 0, "generate": 0, "deliver": 0}


def test_bot_timeout_log_counts_started_call_and_does_not_wait_for_late_usage(capsys):
    runtime = bot_runtime(on_finished=write_run_log)

    class BotLateProvider(ScriptedProvider):
        def complete(self, *args, **kwargs):
            runtime.clock.advance(55)
            runtime.jobs.poll()
            runtime.deliveries.run_next()
            return super().complete(*args, **kwargs)

    _, _, _, _, ledger = bot_logged_pipeline(runtime, provider=BotLateProvider())
    bot_start_logged(runtime)
    runtime.compute.run_next()
    lines = capsys.readouterr().err.splitlines()
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["status"] == "timed_out" and record["calls"] == {"retrieve": 5, "generate": 1, "deliver": 1}
    assert record["timings_ms"]["generate"] >= 55000 and len(ledger.records) == 1


def test_bot_failed_call_is_counted_without_logging_exception(capsys):
    runtime = bot_runtime(on_finished=write_run_log)
    store, _, _, provider, _ = bot_logged_pipeline(runtime)
    from qello_knowledge.domain.store import StoreUnavailable

    store.fail["search_vector"] = StoreUnavailable("synthetic raw error")
    bot_start_logged(runtime)
    runtime.compute.run_next()
    runtime.deliveries.run_next()
    captured = capsys.readouterr().err
    assert "synthetic raw error" not in captured and not provider.calls
    assert json.loads(captured)["calls"] == {"retrieve": 3, "generate": 0, "deliver": 1}


@pytest.mark.parametrize("measured", [True, False])
def test_bot_neurons_distinguish_measured_from_estimated_for_both_models(measured, capsys):
    runtime = bot_runtime(on_finished=write_run_log)
    bot_logged_pipeline(
        runtime,
        provider=ScriptedProvider([ProviderReply("합성 답변 [S1]", 10, 5, neurons=2 if measured else None)]),
        embedding_provider=FakeEmbeddingProvider(neurons=1 if measured else None),
    )
    bot_start_logged(runtime)
    runtime.compute.run_next()
    runtime.deliveries.run_next()
    record = json.loads(capsys.readouterr().err)
    assert record["generation_summary"]["measured"] is measured
    assert record["retrieval_summary"]["measured"] is measured
    assert record["generation_summary"]["neurons"] > 0


def test_bot_retries_and_four_messages_stay_within_call_limit(capsys):
    runtime = bot_runtime(script=[(500, {}), (200, {})] * 4, on_finished=write_run_log)
    bot_logged_pipeline(
        runtime,
        embedding_provider=FakeEmbeddingProvider(fail_calls={1: ProviderFailure(ProviderFailureKind.TRANSIENT)}),
        provider=ScriptedProvider(
            [
                GenerationProviderFailure(GenerationFailure.TRANSIENT, billable=True),
                ProviderReply("합성 답변 [S1]", 10, 5),
            ]
        ),
    )
    runtime.jobs._pipeline._render = lambda *args, **kwargs: RenderedReply(("합성 답변",) * 4, False)
    bot_start_logged(runtime)
    runtime.compute.run_next()
    runtime.deliveries.run_next()
    record = json.loads(capsys.readouterr().err)
    assert record["calls"] == {"retrieve": 7, "generate": 4, "deliver": 8}
    assert record["deliver_retries"] == 4 and sum(record["calls"].values()) <= 20
