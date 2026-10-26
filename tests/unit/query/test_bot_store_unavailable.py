import pytest

from qello_knowledge.adapters.postgres.store import StoreDeadline
from qello_knowledge.domain.store import StoreUnavailable
from qello_knowledge.generation.fake import MemoryLedger, ScriptedProvider
from qello_knowledge.query.pipeline import QueryParts, QueryPipeline, _DeadlineStore
from tests.unit.discord.bot_builders import ask
from tests.unit.generation.gen_builders import never_blocks
from tests.unit.query.bot_runtime import bot_request, bot_runtime
from tests.unit.retrieval.fakes import FakeRetrievalStore, query_embedder


@pytest.mark.parametrize(
    "error", [StoreUnavailable("synthetic connection detail"), StoreDeadline("synthetic timeout detail")]
)
@pytest.mark.parametrize("delay", [0, 50])
def test_bot_store_failure_updates_search_notice_without_retry_or_generation(error, delay):
    runtime = bot_runtime()
    store = FakeRetrievalStore(fail={"search_vector": error})
    original = store._call

    def bot_delayed_failure(*args):
        runtime.clock.advance(delay)
        return original(*args)

    store._call = bot_delayed_failure
    embedder, embedding_provider, ledger = query_embedder()
    provider = ScriptedProvider()
    parts = QueryParts(_DeadlineStore(store), embedder, provider, MemoryLedger(), never_blocks)
    runtime.jobs._pipeline = QueryPipeline(lambda job, remaining: parts, clock=runtime.clock.now)
    body = ask("합성 질문")
    headers = runtime.key.sign(body, "1000")
    _, _, response = bot_request(runtime, body, headers=headers)
    run_id = response["X-QK-Run"]
    assert runtime.jobs.start(run_id, headers["X-Signature-Ed25519"], "1000")
    runtime.jobs.poll()
    runtime.compute.run_next()
    runtime.deliveries.run_next()
    content = runtime.fake.requests[0].body["content"]
    assert "지금은 자료를 검색할 수 없습니다" in content
    assert run_id[-8:] in content and "synthetic" not in content
    assert store.names() == ["search_vector"] and not provider.calls
    assert len(embedding_provider.calls) == 1 and runtime.clock.now() < 55


def test_bot_store_deadline_still_discards_late_result_and_does_not_retry():
    runtime = bot_runtime()
    store = FakeRetrievalStore()

    def bot_late(*args):
        store.calls.append(("search_vector", ()))
        runtime.clock.advance(55)
        raise StoreDeadline("synthetic late detail")

    store.search_vector = bot_late
    embedder, _, _ = query_embedder()
    parts = QueryParts(_DeadlineStore(store), embedder, ScriptedProvider(), MemoryLedger(), never_blocks)
    runtime.jobs._pipeline = QueryPipeline(lambda job, remaining: parts, clock=runtime.clock.now)
    body = ask("합성 질문")
    headers = runtime.key.sign(body, "1000")
    _, _, response = bot_request(runtime, body, headers=headers)
    runtime.jobs.start(response["X-QK-Run"], headers["X-Signature-Ed25519"], "1000")
    runtime.jobs.poll()
    runtime.compute.run_next()
    runtime.deliveries.run_next()
    assert store.names() == ["search_vector"]
    assert "답변이 늦어져" in runtime.fake.requests[0].body["content"]
