"""FR-002 상태와 전달 전 메타데이터 기록. 제공자는 전부 가짜다."""

import json

import pytest

from qello_knowledge.query.pipeline import QueryReply
from qello_knowledge.query.recorder import QueryRecorder
from tests.unit.discord.bot_builders import ask
from tests.unit.query.bot_runtime import bot_request, bot_runtime
from tests.unit.query.obs_builders import QUESTIONER, FakeQueryLog


def question_body():
    payload = json.loads(ask("합성 질문 1"))
    payload["member"]["user"] = {"id": QUESTIONER}
    return json.dumps(payload).encode()


def run_query(runtime):
    body = question_body()
    signed = runtime.key.sign(body, "1000")
    _, _, headers = bot_request(runtime, body, headers=signed)
    run = headers["X-QK-Run"]
    assert runtime.jobs.start(run, signed["X-Signature-Ed25519"], "1000")
    runtime.jobs.poll()
    runtime.compute.run_next()
    runtime.deliveries.run_next()
    return run


@pytest.mark.parametrize(
    "status", ["answered", "cannot_confirm", "retrieval_failed", "generation_failed", "outgoing_blocked"]
)
def test_insert_before_delivery_and_metadata(status):
    port = FakeQueryLog()
    with QueryRecorder(lambda: port, lambda: port) as recorder:
        runtime = bot_runtime(
            recorder=recorder,
            pipeline=lambda job, stage: QueryReply(
                ("합성 답변",),
                False,
                status=status,
                context_chunk_ids=(1, 2, 3),
                context_block_sizes=(2, 1),
                cited_blocks=(2,),
                index_version="v1",
                model_id="model",
                prompt_version="prompt",
                input_tokens=10,
                output_tokens=5,
            ),
        )
        logs = []
        runtime.jobs._on_finished = logs.append
        original = runtime.jobs._deliver

        def deliver(job, reply):
            assert port.calls[0][0] == "insert"
            return original(job, reply)

        runtime.jobs._deliver = deliver
        run_query(runtime)
        recorder.close()
        records = [args[0] for method, args in port.calls if method == "insert"]
        assert len(records) == 1
        record = records[0]
        assert record.status == status and record.questioner_id == QUESTIONER
        assert record.context_chunk_ids == (1, 2, 3) and sum(record.context_block_sizes) == 3
        assert record.cited_blocks == (2,) and record.input_tokens == 10 and record.output_tokens == 5
        assert not hasattr(record, "question") and not hasattr(record, "answer")
        assert logs[0].record == "stored"
        runtime.jobs.close()


@pytest.mark.parametrize("failure", ["outgoing_blocked", "busy", "failed"])
def test_first_response_only_records_without_waiting(failure):
    port = FakeQueryLog()
    with QueryRecorder(lambda: port, lambda: port) as recorder:
        runtime = bot_runtime(recorder=recorder, workers=1, queue_size=0)
        runtime.app.recorder = recorder
        if failure == "outgoing_blocked":
            runtime.app.outgoing_check = lambda item: False
        elif failure == "failed":
            runtime.app.outgoing_check = lambda item: (_ for _ in ()).throw(ValueError("합성 질문 1"))
        else:
            bot_request(runtime, ask("합성 질문 2", interaction_id="100000000000000003"))
        body = question_body()
        assert json.loads(bot_request(runtime, body)[1])["type"] == 4
        bot_request(runtime, body)
        recorder.close()
        records = [args[0] for method, args in port.calls if method == "insert"]
        assert len(records) == 1 and records[0].status == failure
        runtime.jobs.close()


@pytest.mark.parametrize("mode", ["denied", "signature", "unsupported", "duplicate"])
def test_rejected_requests_not_recorded(mode):
    port = FakeQueryLog()
    with QueryRecorder(lambda: port, lambda: port) as recorder:
        runtime = bot_runtime(recorder=recorder)
        body = question_body()
        if mode == "denied":
            runtime.app.access_check = lambda item: False
        if mode == "unsupported":
            body = b'{"type":9}'
        if mode == "duplicate":
            bot_request(runtime, body)
        bot_request(runtime, body, headers={"bad": "header"} if mode == "signature" else None)
        recorder.close()
        assert not port.calls
        runtime.jobs.close()


@pytest.mark.parametrize("outcome", ["not_started", "timed_out", "failed", "undelivered"])
def test_terminal_status_and_delivery(outcome):
    port = FakeQueryLog()
    with QueryRecorder(lambda: port, lambda: port) as recorder:
        runtime = bot_runtime(recorder=recorder)
        if outcome == "failed":
            runtime.jobs._pipeline = lambda *args: (_ for _ in ()).throw(ValueError())
        if outcome == "undelivered":
            runtime.jobs._deliver = lambda *args: (_ for _ in ()).throw(OSError())
        if outcome in ("failed", "undelivered"):
            run_query(runtime)
        else:
            body = question_body()
            signed = runtime.key.sign(body, "1000")
            _, _, headers = bot_request(runtime, body, headers=signed)
            if outcome == "timed_out":
                runtime.jobs.start(headers["X-QK-Run"], signed["X-Signature-Ed25519"], "1000")
                runtime.clock.advance(56)
            else:
                runtime.clock.advance(6)
            runtime.jobs.poll()
            runtime.deliveries.run_next()
        recorder.close()
        records = [args[0] for method, args in port.calls if method == "insert"]
        deliveries = [args[0] for method, args in port.calls if method == "delivered"]
        assert len(records) == 1 and len(deliveries) == 1
        assert records[0].status == (outcome if outcome != "undelivered" else "answered")
        assert deliveries[0].final_status == ("undelivered" if outcome == "undelivered" else None)
        runtime.jobs.close()


def test_pipeline_records_context_and_citation_numbers():
    from tests.unit.query.test_bot_pipeline import bot_pipeline

    runtime = bot_runtime()
    pipeline, *_ = bot_pipeline(runtime.clock)
    reply = pipeline(
        __import__("qello_knowledge.domain.discord", fromlist=["QueryJob"]).QueryJob(
            "q-20261029T010203-1234abcd",
            __import__("qello_knowledge.discord.interactions", fromlist=["parse"]).parse(question_body()),
            0,
            55,
            60,
        ),
        lambda stage: None,
    )
    assert reply.context_chunk_ids == (100, 203, 301)
    assert reply.context_block_sizes == (1, 1, 1)
    assert reply.cited_blocks and all(1 <= n <= 3 for n in reply.cited_blocks)
    assert reply.model_id and reply.prompt_version
    runtime.jobs.close()


@pytest.mark.parametrize("mode", ["failed", "timeout"])
def test_record_failure_keeps_answer_and_buttons(mode):
    from threading import Event

    from qello_knowledge.query.pipeline import QueryReply

    release = Event()
    port = FakeQueryLog(insert=ValueError("합성 질문 1") if mode == "failed" else release)
    recorder = QueryRecorder(lambda: FakeQueryLog(), lambda: port, record_timeout_ms=100)
    runtime = bot_runtime(recorder=recorder, pipeline=lambda *args: QueryReply(("합성 답변",), True))
    logs = []
    runtime.jobs._on_finished = logs.append
    try:
        run_query(runtime)
        body = runtime.fake.requests[0].body
        assert body["content"] == "합성 답변" and body["components"][0]["components"][0]["label"] == "👍"
        assert logs[0].record == mode
    finally:
        release.set()
        runtime.jobs.close()


def test_busy_retry_after_capacity_frees_does_not_create_another_run():
    port = FakeQueryLog()
    with QueryRecorder(lambda: port, lambda: port) as recorder:
        runtime = bot_runtime(recorder=recorder, workers=1, queue_size=0)
        bot_request(runtime, ask("합성 질문 2", interaction_id="100000000000000003"))
        body = question_body()
        assert json.loads(bot_request(runtime, body)[1])["type"] == 4
        runtime.clock.advance(6)
        runtime.jobs.poll()
        runtime.deliveries.run_next()
        assert json.loads(bot_request(runtime, body)[1])["data"]["content"] == "이미 처리 중인 요청입니다."
        runtime.jobs.close()


def test_total_time_starts_at_request_receipt():
    port = FakeQueryLog()
    with QueryRecorder(lambda: port, lambda: port) as recorder:
        runtime = bot_runtime(recorder=recorder)

        def access(item):
            runtime.clock.advance(0.2)
            return True

        runtime.app.access_check = access
        run_query(runtime)
        recorder._back.executor.submit(lambda: None).result(1)
        delivery = next(args[0] for name, args in port.calls if name == "delivered")
        assert delivery.total_ms == 200
        runtime.jobs.close()
