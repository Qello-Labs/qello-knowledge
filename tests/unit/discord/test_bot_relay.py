import json

import pytest

from qello_knowledge.discord.relay import fallback, precheck, relay_plan, relay_response, start_request

BOT_HEADERS = {"X-Signature-Ed25519": "a" * 128, "X-Signature-Timestamp": "1000"}


def test_bot_relay_prechecks_and_ping():
    assert precheck(b" " * 65537, BOT_HEADERS, 1000) == 413
    assert precheck(b"{}", {}, 1000) == 401
    assert precheck(b"{}", BOT_HEADERS, 1300) is None
    assert precheck(b"{}", BOT_HEADERS, 1300.01) == 401
    assert precheck(b"{}", BOT_HEADERS, 699.99) == 401
    assert precheck(b"{}", {**BOT_HEADERS, "X-Signature-Timestamp": "NaN"}, 1000) == 401
    assert relay_plan(b'{"type":1}', BOT_HEADERS) == ()


@pytest.mark.parametrize("status", [None, 500, 401])
def test_bot_service_failure_fallback(status):
    result = relay_response(b'{"type":2}', status, b"", {})
    assert result.body == fallback()
    assert result.log_kind == "relay_failed" and result.run_id is None
    assert fallback() == {
        "type": 4,
        "data": {
            "content": "지금은 답할 수 없습니다. 잠시 후 다시 질문해 주세요.",
            "flags": 64,
            "allowed_mentions": {"parse": []},
        },
    }
    assert relay_response(b'{"type":1}', None, b"", {}).body == {"type": 1}


def test_bot_relay_bytes_start_and_log_allowlist():
    body = b'{"type":2}'
    plan = relay_plan(body, BOT_HEADERS)
    assert len(plan) == 1 and plan[0].body == body and dict(plan[0].headers) == BOT_HEADERS
    result = relay_response(body, 200, b'{"type":5}', {"X-QK-Run": "run"})
    assert result.body == {"type": 5} and result.log_kind == "relayed"
    start = start_request(result, BOT_HEADERS)
    assert start.path == "/discord/interactions/start" and json.loads(start.body) == {"run_id": "run"}
    assert dict(start.headers) == BOT_HEADERS and len(plan) + 1 <= 2
    assert start_request(relay_response(body, 200, b'{"type":4}', {}), BOT_HEADERS) is None
    assert set(result.log(12)) == {"kind", "elapsed_ms"}
