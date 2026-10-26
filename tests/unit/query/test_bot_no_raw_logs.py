import json

import pytest

from qello_knowledge.domain.generation import CANNOT_CONFIRM, GenerationFailure, GenerationStatus
from qello_knowledge.domain.retrieval import RetrievalFailure
from qello_knowledge.query.server import write_run_log
from tests.unit.discord.bot_builders import CHANNEL, INTERACTION, TOKEN, ask, component
from tests.unit.query.bot_runtime import bot_request
from tests.unit.query.bot_scenarios import bot_result, bot_run_result
from tests.unit.query.bot_security import bot_secured_runtime
from tests.unit.synthetic_secrets import SYNTHETIC

BOT_FORBIDDEN = (
    "합성 질문 표식",
    "합성 답변 원문 표식",
    "합성 청크 원문 표식",
    "합성 제목 표식",
    "https://example.invalid/private-source",
    INTERACTION,
    TOKEN,
    CHANNEL,
    SYNTHETIC["db-url"],
    SYNTHETIC["cloudflare-account"],
    "900000000000000009",
    "합성 사용자명",
)


def bot_logs(capsys, caplog):
    capture = capsys.readouterr()
    combined = capture.out + capture.err + caplog.text
    assert all(value not in combined for value in BOT_FORBIDDEN)
    return [json.loads(line) for line in capture.err.splitlines()]


@pytest.mark.parametrize("failure", [None, *RetrievalFailure, *GenerationFailure, "cannot_confirm", "outgoing_blocked"])
def test_bot_all_result_logs_are_structured_and_contain_no_raw_values(failure, capsys, caplog):
    if isinstance(failure, RetrievalFailure):
        result = bot_result(GenerationStatus.RETRIEVAL_FAILED, retrieval_failure=failure.value)
    elif isinstance(failure, GenerationFailure):
        result = bot_result(GenerationStatus.GENERATION_FAILED, failure=failure)
    elif failure == "cannot_confirm":
        result = bot_result(GenerationStatus.CANNOT_CONFIRM, answer=CANNOT_CONFIRM)
    elif failure == "outgoing_blocked":
        result = bot_result(GenerationStatus.OUTGOING_BLOCKED)
    else:
        from tests.unit.discord.test_bot_render_basic import bot_citation

        result = bot_result(
            answer=BOT_FORBIDDEN[1], citations=(bot_citation(title=BOT_FORBIDDEN[3], source_url=BOT_FORBIDDEN[4]),)
        )
    runtime, run_id = bot_run_result(result, on_finished=write_run_log)
    logs = bot_logs(capsys, caplog)
    assert len(logs) == 1 and logs[0]["run_id"] == run_id
    assert logs[0]["status"] == result.status.value
    assert not runtime.jobs.in_flight


@pytest.mark.parametrize(
    "case",
    ["timeout", "exception", "delivery", "duplicate", "busy", "unsupported", "denied", "not_started", "deadline"],
)
def test_bot_failure_and_rejection_logs_do_not_expose_raw_exception_or_identity(case, capsys, caplog):
    runtime = bot_secured_runtime(
        on_finished=write_run_log, script=[(400, {"message": "|".join(BOT_FORBIDDEN)})] if case == "delivery" else ()
    )
    runtime.app.on_response = write_run_log
    if case in ("timeout", "exception"):

        def fail(job, stage):
            raise (TimeoutError if case == "timeout" else RuntimeError)("|".join(BOT_FORBIDDEN))

        runtime.jobs._pipeline = fail
    changes = {"channel": "8" * 18} if case == "denied" else {}
    body = component() if case == "unsupported" else ask(BOT_FORBIDDEN[0], **changes)
    payload = json.loads(body)
    payload.setdefault("member", {})["user"] = {"id": BOT_FORBIDDEN[-2], "username": BOT_FORBIDDEN[-1]}
    payload["user"] = payload["member"]["user"]
    body = json.dumps(payload).encode()
    headers = runtime.key.sign(body, "1000")
    _, _, response = bot_request(runtime, body, headers=headers)
    if "X-QK-Run" in response:
        run_id = response["X-QK-Run"]
        if case == "duplicate":
            bot_request(runtime, body, headers=headers)
        elif case == "busy":
            for i in range(1, 7):
                bot_request(runtime, ask(BOT_FORBIDDEN[0], interaction_id=str(i)))
        elif case in ("not_started", "deadline"):
            if case == "deadline":
                runtime.jobs.start(run_id, headers["X-Signature-Ed25519"], "1000")
                runtime.jobs.poll()
            runtime.clock.advance(5 if case == "not_started" else 55)
            runtime.jobs.poll()
            runtime.deliveries.run_next()
        else:
            runtime.jobs.start(run_id, headers["X-Signature-Ed25519"], "1000")
            runtime.jobs.poll()
            runtime.compute.run_next()
            runtime.deliveries.run_next()
    logs = bot_logs(capsys, caplog)
    assert len(logs) == 1
    assert all(headers["X-Signature-Ed25519"] not in json.dumps(log) for log in logs)
    if case == "delivery":
        assert logs[0]["deliver_failure"] == "http_400"
        assert logs[0]["status"] == "undelivered"


def test_bot_signature_rejection_is_not_logged(capsys, caplog):
    runtime = bot_secured_runtime(on_finished=write_run_log)
    runtime.app.on_response = write_run_log
    assert bot_request(runtime, ask("합성 질문"), headers={"X-Signature-Ed25519": "invalid"})[0] == 401
    assert bot_logs(capsys, caplog) == []


def test_bot_http_access_log_does_not_print_arbitrary_request_path(capsys):
    from qello_knowledge.query.server import _Handler

    handler = object.__new__(_Handler)
    handler.command = "POST"
    handler.path = "/" + TOKEN
    handler.log_message("%s", TOKEN)
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("guard", ["access_check", "outgoing_check"])
def test_bot_pre_deferral_guard_exception_is_private_and_has_no_raw_exception(guard, capsys, caplog):
    runtime = bot_secured_runtime()
    runtime.app.on_response = write_run_log

    def fail(item):
        raise RuntimeError("|".join(BOT_FORBIDDEN))

    setattr(runtime.app, guard, fail)
    _, raw, headers = bot_request(runtime, ask(BOT_FORBIDDEN[0]))
    data = json.loads(raw)["data"]
    assert data["flags"] == 64 and "요청을 처리하지 못했습니다" in data["content"] and not headers
    assert len(bot_logs(capsys, caplog)) == 1
    assert runtime.jobs.in_flight == 0 and not runtime.calls
