"""실제 루프백 HTTP 왕복. 검색·생성·Discord는 메모리 가짜만 사용한다."""

import json
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

import pytest

from qello_knowledge.discord.access import AccessPolicy
from qello_knowledge.domain.discord import QueryStage
from tests.unit.discord.bot_builders import CHANNEL, GUILD, ask, ping
from tests.unit.query.bot_http_server import bot_live_server
from tests.unit.query.bot_runtime import bot_runtime
from tests.unit.query.test_bot_pipeline import bot_pipeline


@pytest.fixture
def bot_http_runtime():
    runtime = bot_runtime()
    pipeline, provider, ledger, closer, searches = bot_pipeline(runtime.clock)
    runtime.jobs._pipeline = pipeline
    runtime.app.access_check = AccessPolicy(GUILD, (CHANNEL,), ()).check
    with bot_live_server(runtime) as server:
        assert isinstance(server, ThreadingHTTPServer)
        assert server.server_address[0] == "127.0.0.1" and server.server_port > 0
        yield runtime, server, searches, provider


def bot_post(server, body, signature, path="/discord/interactions"):
    connection = HTTPConnection("127.0.0.1", server.server_port, timeout=2)
    try:
        connection.request("POST", path, body=body, headers=signature)
        response = connection.getresponse()
        return response.status, response.read(), response.getheader("X-QK-Run")
    finally:
        connection.close()


def test_bot_http_signed_ping_returns_pong_without_jobs(bot_http_runtime):
    runtime, server, searches, provider = bot_http_runtime
    body = ping()
    status, raw, run_id = bot_post(server, body, runtime.key.sign(body, "1000"))
    assert status == 200 and json.loads(raw) == {"type": 1} and run_id is None
    assert runtime.jobs.in_flight == 0 and not searches and not provider.calls and not runtime.fake.requests


@pytest.mark.parametrize("private", [False, True])
def test_bot_http_ask_start_and_fake_reply_update_original(bot_http_runtime, private):
    runtime, server, searches, provider = bot_http_runtime
    body = ask("합성 통합 질문", private=private)
    signature = runtime.key.sign(body, "1000")
    status, raw, run_id = bot_post(server, body, signature)
    payload = json.loads(raw)
    assert status == 200 and payload["type"] == 5 and run_id
    assert payload.get("data", {}).get("flags", 0) == (64 if private else 0)
    assert not searches and not provider.calls and not runtime.fake.requests
    status, raw, _ = bot_post(server, json.dumps({"run_id": run_id}).encode(), signature, "/discord/interactions/start")
    assert status == 204 and raw == b""
    runtime.jobs.poll()
    runtime.compute.run_next()
    runtime.deliveries.run_next()
    assert len(searches) == len(provider.calls) == len(runtime.fake.requests) == 1
    assert runtime.jobs.stage(run_id) is QueryStage.DONE
    request = runtime.fake.requests[0]
    assert request.method == "PATCH" and request.path.endswith("/messages/@original")
    assert "자료 기준: 색인된 문서" in request.body["content"]
    assert request.body["allowed_mentions"] == {"parse": []}


def test_bot_http_missing_start_sends_one_notice_without_search_or_generation(bot_http_runtime):
    runtime, server, searches, provider = bot_http_runtime
    body = ask("합성 시작 누락 질문")
    status, raw, run_id = bot_post(server, body, runtime.key.sign(body, "1000"))
    assert status == 200 and json.loads(raw)["type"] == 5
    runtime.clock.advance(5)
    runtime.jobs.poll()
    runtime.deliveries.run_next()
    runtime.clock.advance(5)
    runtime.jobs.poll()
    assert runtime.jobs.outcome(run_id) is QueryStage.NOT_STARTED
    assert len(runtime.fake.requests) == 1
    assert "요청을 처리하지 못했습니다" in runtime.fake.requests[0].body["content"]
    assert not searches and not provider.calls and not runtime.compute.pending and not runtime.deliveries.pending


def test_bot_http_bad_signature_returns_401_without_any_work(bot_http_runtime):
    runtime, server, searches, provider = bot_http_runtime
    body = ask("합성 서명 거부 질문")
    status, raw, run_id = bot_post(server, body, runtime.key.other_key_sign(body, "1000"))
    assert status == 401 and raw == b"" and run_id is None
    assert runtime.jobs.in_flight == 0 and not searches and not provider.calls and not runtime.fake.requests
