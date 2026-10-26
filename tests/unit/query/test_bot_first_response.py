import json
import re

import pytest

from qello_knowledge.domain.discord import QueryStage
from tests.unit.discord.bot_builders import ask, ping
from tests.unit.query.bot_runtime import bot_request, bot_runtime


def test_bot_ping_without_work():
    runtime = bot_runtime()
    status, raw, headers = bot_request(runtime, ping())
    assert status == 200 and json.loads(raw) == {"type": 1} and not headers
    assert not runtime.compute.pending and not runtime.fake.requests


@pytest.mark.parametrize("private", [False, True])
def test_bot_first_response_no_external_work(private):
    runtime = bot_runtime()
    status, raw, headers = bot_request(runtime, ask("합성 질문", private=private))
    assert status == 200
    assert json.loads(raw) == ({"type": 5, "data": {"flags": 64}} if private else {"type": 5})
    run_id = headers["X-QK-Run"]
    assert re.fullmatch(r"q-\d{8}T\d{6}-[0-9a-f]{8}", run_id)
    assert runtime.jobs.stage(run_id) is QueryStage.AWAITING_START
    assert runtime.jobs.in_flight == 1
    assert not runtime.calls and not runtime.compute.pending and not runtime.fake.requests


def test_bot_invalid_signature_no_work():
    runtime = bot_runtime()
    status, raw, headers = bot_request(runtime, ask("합성 질문"), headers={"X-Signature-Ed25519": "bad"})
    assert status == 401 and raw == "" and not headers
    assert runtime.jobs.in_flight == 0 and not runtime.calls and not runtime.fake.requests
