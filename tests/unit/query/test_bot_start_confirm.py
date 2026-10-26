import json
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from qello_knowledge.domain.discord import QueryStage
from tests.unit.discord.bot_builders import ask
from tests.unit.query.bot_runtime import bot_request, bot_runtime


def bot_waiting(runtime):
    body = ask("합성 질문")
    headers = runtime.key.sign(body, "1000")
    _, _, response_headers = bot_request(runtime, body, headers=headers)
    return response_headers["X-QK-Run"], headers


def test_bot_start_confirm_then_pipeline_and_one_patch():
    runtime = bot_runtime()
    run_id, headers = bot_waiting(runtime)
    body = json.dumps({"run_id": run_id}).encode()
    assert bot_request(runtime, body, "/discord/interactions/start", headers)[0] == 204
    assert runtime.jobs.stage(run_id) is QueryStage.QUEUED
    assert bot_request(runtime, body, "/discord/interactions/start", headers)[0] == 409
    runtime.jobs.poll()
    runtime.compute.run_next()
    runtime.deliveries.run_next()
    assert runtime.jobs.stage(run_id) is QueryStage.DONE and runtime.jobs.in_flight == 0
    assert runtime.calls == [run_id] and len(runtime.fake.requests) == 1


@pytest.mark.parametrize("case", ["unknown", "signature", "timestamp", "expired"])
def test_bot_bad_start_does_not_enqueue(case):
    runtime = bot_runtime()
    run_id, headers = bot_waiting(runtime)
    if case == "unknown":
        run_id = "unknown"
    if case in ("signature", "timestamp"):
        headers["X-Signature-Ed25519" if case == "signature" else "X-Signature-Timestamp"] = "wrong"
    if case == "expired":
        runtime.clock.advance(5)
    assert (
        bot_request(runtime, json.dumps({"run_id": run_id}).encode(), "/discord/interactions/start", headers)[0] == 409
    )
    assert not runtime.compute.pending and not runtime.calls


def test_bot_no_start_notice_uses_original_retry_and_releases_lifetime():
    runtime = bot_runtime(script=[(404, {}), (200, {})])
    run_id, _ = bot_waiting(runtime)
    runtime.clock.advance(5)
    runtime.jobs.poll()
    assert not runtime.fake.requests and not runtime.calls
    assert runtime.jobs.outcome(run_id) is QueryStage.NOT_STARTED
    runtime.deliveries.run_next()
    assert len(runtime.fake.requests) == 2 and runtime.clock.now() == 6
    assert "요청을 처리하지 못했습니다" in runtime.fake.requests[0].body["content"]
    assert runtime.jobs.in_flight == 0


def test_bot_start_expiry_race_has_only_one_winner():
    runtime = bot_runtime()
    run_id, headers = bot_waiting(runtime)
    runtime.clock.advance(5)
    barrier = Barrier(2)

    def start():
        barrier.wait()
        return runtime.jobs.start(run_id, headers["X-Signature-Ed25519"], headers["X-Signature-Timestamp"])

    def expire():
        barrier.wait()
        runtime.jobs.poll()

    with ThreadPoolExecutor(2) as pool:
        a, b = pool.submit(start), pool.submit(expire)
        assert a.result() is False
        b.result()
    assert len(runtime.deliveries.pending) == 1 and not runtime.compute.pending
