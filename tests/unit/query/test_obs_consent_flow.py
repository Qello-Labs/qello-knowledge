"""동의 계약 5~13행. 선점 전 상태와 결과 불명의 재시도."""

import json
from datetime import date

import pytest

from qello_knowledge.query.pending import PendingQuestions
from qello_knowledge.query.recorder import QueryRecorder
from tests.unit.query.bot_runtime import bot_request
from tests.unit.query.obs_builders import QUESTIONER, RATER, RUN, FakeQueryLog, component
from tests.unit.query.test_obs_feedback_flow import feedback_runtime


def consent_runtime(recorder, **options):
    runtime = feedback_runtime(recorder)
    p = PendingQuestions(retain_until=date(2026, 12, 31), today=lambda: date(2026, 10, 29), **options)
    runtime.jobs.pending = p
    p.put(RUN, QUESTIONER, "합성 질문 1", "answered")
    return runtime, p


def click(runtime, action, user=QUESTIONER):
    return json.loads(bot_request(runtime, component(action, user=user))[1])


def test_down_prompts_only_questioner():
    port = FakeQueryLog()
    with QueryRecorder(lambda: port, lambda: port) as recorder:
        runtime, p = consent_runtime(recorder)
        assert "components" not in click(runtime, "down", RATER)["data"]
        answer = click(runtime, "down")
        assert answer["type"] == 4 and answer["data"]["flags"] == 64
        assert "저장하는 것" in answer["data"]["content"] and len(answer["data"]["components"]) == 1
        assert "components" not in click(runtime, "up")["data"]
        p.close()
        assert "components" not in click(runtime, "down")["data"]
        runtime.jobs.close()


@pytest.mark.parametrize(
    "action,state,result,message,callback,after",
    [
        ("keep", "waiting", "stored", "질문을 저장했습니다.", 7, "chosen"),
        ("keep", "uncertain", "exists", "질문을 저장했습니다.", 7, "chosen"),
        ("keep", "waiting", "missing", "저장하지 못했습니다.", 4, "chosen"),
        ("keep", "waiting", "not_questioner", "저장하지 못했습니다.", 4, "chosen"),
        ("keep", "waiting", "failure", "저장 여부를 확인하지 못했습니다.", 4, "uncertain"),
        ("skip", "waiting", "none", "저장하지 않았습니다.", 7, "chosen"),
        ("skip", "uncertain", "stored", "이미 저장된 질문입니다.", 4, "chosen"),
        ("skip", "uncertain", "none", "저장하지 않았습니다.", 4, "chosen"),
        ("keep", "chosen", "none", "이미 선택했습니다.", 4, "chosen"),
        ("keep", "absent", "none", "질문이 남아 있지 않아", 4, "absent"),
        ("skip", "absent", "none", "저장하지 않았습니다.", 4, "absent"),
        ("keep", "absent", "stored", "이미 저장된 질문입니다.", 4, "absent"),
        ("skip", "chosen", "not_questioner", "평가를 남기지 못했습니다.", 4, "chosen"),
        ("keep", "chosen", "missing", "평가를 남기지 못했습니다.", 4, "chosen"),
        ("skip", "uncertain", "failure", "저장 여부를 확인하지 못했습니다.", 4, "uncertain"),
        ("keep", "claimed", "none", "저장 여부를 확인하지 못했습니다.", 4, "claimed"),
    ],
)
def test_consent_rows(action, state, result, message, callback, after):
    value = ValueError("합성 질문 1") if result == "failure" else result
    port = FakeQueryLog(store_question=value, question_status=value)
    with QueryRecorder(lambda: port, lambda: port) as recorder:
        runtime, p = consent_runtime(recorder)
        if state in ("chosen", "uncertain", "claimed"):
            claim = p.claim(RUN, QUESTIONER)
            if state != "claimed":
                p.finish(claim, uncertain=state == "uncertain")
        if state == "absent":
            p.close()
        response = click(runtime, action)
        assert response["type"] == callback and message in response["data"]["content"]
        assert response["data"]["allowed_mentions"] == {"parse": []}
        if callback == 7:
            assert response["data"]["components"] == []
        item = p.get(RUN)
        assert (item.state if item else "absent") == after
        if after == "uncertain":
            assert item.question == "합성 질문 1"
        runtime.jobs.close()


@pytest.mark.parametrize("state", ["waiting", "uncertain", "claimed", "chosen"])
def test_wrong_user_before_any_store_or_status(state):
    port = FakeQueryLog()
    with QueryRecorder(lambda: port, lambda: port) as recorder:
        runtime, p = consent_runtime(recorder)
        if state != "waiting":
            claim = p.claim(RUN, QUESTIONER)
            if state != "claimed":
                p.finish(claim, uncertain=state == "uncertain")
        assert "평가를 남기지 못했습니다" in click(runtime, "keep", RATER)["data"]["content"]
        assert not port.calls
        runtime.jobs.close()


def test_secret_recheck_skips_text():
    port = FakeQueryLog()
    with QueryRecorder(lambda: port, lambda: port) as recorder:
        runtime, p = consent_runtime(recorder)
        runtime.app.outgoing_check = lambda item: False
        assert "비밀값으로 보이는" in click(runtime, "keep")["data"]["content"]
        assert port.calls == [("mark_text_skipped", (RUN,))]
        assert p.get(RUN).question is None
        runtime.jobs.close()


def test_concurrent_keep_skip_and_expiry_during_store():
    from concurrent.futures import ThreadPoolExecutor
    from threading import Event

    from tests.unit.query.obs_builders import FakeClock

    started, release = Event(), Event()

    def store(*args):
        started.set()
        release.wait(2)
        return "stored"

    port = FakeQueryLog(store_question=store)
    clock = FakeClock()
    with QueryRecorder(lambda: port, lambda: port) as recorder:
        runtime, p = consent_runtime(recorder, clock=clock.now, seconds=10)
        with ThreadPoolExecutor(1) as clients:
            first = clients.submit(click, runtime, "keep")
            assert started.wait(1)
            assert "저장 여부를 확인하지 못했습니다" in click(runtime, "skip")["data"]["content"]
            clock.advance(11)
            p.prune()
            release.set()
            assert first.result(1)["type"] == 7
        assert p.get(RUN) is None
        assert [method for method, args in port.calls] == ["store_question"]
        runtime.jobs.close()


def test_retention_boundary_stops_prompt_and_checks_actual_status():
    from datetime import timedelta

    today = [date(2026, 10, 29)]
    port = FakeQueryLog(question_status="none")
    with QueryRecorder(lambda: port, lambda: port) as recorder:
        runtime = feedback_runtime(recorder)
        p = PendingQuestions(retain_until=today[0], today=lambda: today[0])
        runtime.jobs.pending = p
        p.put(RUN, QUESTIONER, "합성 질문 1", "answered")
        assert "components" in click(runtime, "down")["data"]
        today[0] += timedelta(days=1)
        assert "components" not in click(runtime, "down")["data"]
        assert "질문이 남아 있지 않아" in click(runtime, "keep")["data"]["content"]
        assert not any(method == "store_question" for method, args in port.calls)
        runtime.jobs.close()


def test_real_secret_policy_rechecks_before_text_store():
    from qello_knowledge.indexer.embedding import security_outgoing_check
    from qello_knowledge.security.policy import SecurityPolicy
    from tests.unit.synthetic_secrets import SYNTHETIC

    port = FakeQueryLog()
    with QueryRecorder(lambda: port, lambda: port) as recorder:
        runtime, p = consent_runtime(recorder)
        p._items.clear()
        p.put(RUN, QUESTIONER, SYNTHETIC["github-classic"], "answered")
        check = security_outgoing_check(SecurityPolicy())
        runtime.app.outgoing_check = lambda item: not check(item.question or "", None)
        assert "비밀값으로 보이는" in click(runtime, "keep")["data"]["content"]
        assert [name for name, args in port.calls] == ["mark_text_skipped"]
        runtime.jobs.close()
