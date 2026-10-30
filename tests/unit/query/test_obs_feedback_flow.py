"""서명된 버튼의 앞 길 저장, 비공개 안내, 실패 비노출."""

import json

import pytest

from qello_knowledge.query.recorder import QueryRecorder
from tests.unit.query.bot_runtime import bot_request, bot_runtime
from tests.unit.query.obs_builders import QUESTIONER, RUN, FakeQueryLog, component


def feedback_runtime(recorder):
    runtime = bot_runtime(recorder=recorder)
    runtime.app.component_timeout_ms = 500
    return runtime


@pytest.mark.parametrize(
    "mode,text",
    [
        ("stored", "평가를 남겼습니다."),
        ("missing", "평가를 남기지 못했습니다."),
        ("failed", "저장 여부를 확인하지 못했습니다. 다시 눌러 주세요."),
        ("denied", "여기서는 이 버튼을 쓸 수 없습니다."),
        ("invalid", "평가를 남기지 못했습니다."),
        ("off", "평가를 남기지 못했습니다."),
        ("user_missing", "평가를 남기지 못했습니다."),
    ],
)
def test_feedback_contract(mode, text, capsys):
    port = FakeQueryLog(feedback=ValueError("합성 질문 1") if mode == "failed" else mode)
    with QueryRecorder(lambda: port, (lambda: port) if mode != "off" else None) as recorder:
        runtime = feedback_runtime(recorder)
        if mode == "denied":
            runtime.app.access_check = lambda item: False
        body = (
            component(custom_id="bad")
            if mode == "invalid"
            else component(user=None if mode == "user_missing" else QUESTIONER)
        )
        code, raw, headers = bot_request(runtime, body)
        payload = json.loads(raw)
        assert code == 200 and not headers
        assert payload == {"type": 4, "data": {"content": text, "flags": 64, "allowed_mentions": {"parse": []}}}
        assert not runtime.calls and not runtime.fake.requests
        if mode not in ("invalid", "off", "denied", "user_missing"):
            assert port.calls == [("feedback", (RUN, QUESTIONER, "up"))]
        else:
            assert not port.calls
        captured = capsys.readouterr()
        assert QUESTIONER not in captured.err and RUN not in captured.err
        assert len(captured.err.splitlines()) == 1
        runtime.jobs.close()
