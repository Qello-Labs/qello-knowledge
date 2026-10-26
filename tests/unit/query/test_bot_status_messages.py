import json

import pytest

from qello_knowledge.discord.notices import GENERATION_NOTICES, OUTPUT_TRUNCATED, RETRIEVAL_NOTICES, SOURCE_UNVERIFIED
from qello_knowledge.domain.generation import CANNOT_CONFIRM, GenerationFailure, GenerationFlags, GenerationStatus
from qello_knowledge.domain.retrieval import RetrievalFailure
from tests.unit.query.bot_scenarios import bot_result, bot_run_result


def test_bot_cannot_confirm_is_unchanged_and_has_no_sources():
    runtime, _ = bot_run_result(bot_result(GenerationStatus.CANNOT_CONFIRM, answer=CANNOT_CONFIRM))
    assert runtime.fake.requests[0].body["content"] == CANNOT_CONFIRM


def test_bot_unverified_and_truncated_flags_are_displayed():
    flags = GenerationFlags(unsupported_answer=True, truncated=True)
    runtime, _ = bot_run_result(bot_result(flags=flags))
    text = runtime.fake.requests[0].body["content"]
    assert text == SOURCE_UNVERIFIED + "\n\n합성 답변\n\n" + OUTPUT_TRUNCATED
    assert "자료 기준" not in text


@pytest.mark.parametrize("private", [False, True])
@pytest.mark.parametrize("failure", list(RetrievalFailure) + list(GenerationFailure))
def test_bot_failure_messages_use_fixed_text_and_reference(failure, private):
    retrieval = isinstance(failure, RetrievalFailure)
    result = bot_result(
        GenerationStatus.RETRIEVAL_FAILED if retrieval else GenerationStatus.GENERATION_FAILED,
        answer="표시하면 안 되는 오류 원문",
        failure=None if retrieval else failure,
        retrieval_failure=failure.value if retrieval else None,
    )
    runtime, run_id = bot_run_result(result, private=private)
    table = RETRIEVAL_NOTICES if retrieval else GENERATION_NOTICES
    expected = table[failure].format(question_max_chars=2000) + f" (확인 번호 {run_id[-8:]})"
    assert runtime.fake.requests[0].body["content"] == expected
    assert failure.value not in expected and result.answer not in expected
    assert len(runtime.fake.requests) == 1
    assert json.loads(runtime.first_response[1]).get("data", {}).get("flags", 0) == (64 if private else 0)


@pytest.mark.parametrize("private", [False, True])
def test_bot_outgoing_blocked_keeps_selected_privacy(private):
    runtime, run_id = bot_run_result(bot_result(GenerationStatus.OUTGOING_BLOCKED), private=private)
    text = runtime.fake.requests[0].body["content"]
    assert text == RETRIEVAL_NOTICES[RetrievalFailure.OUTGOING_BLOCKED] + f" (확인 번호 {run_id[-8:]})"
    assert json.loads(runtime.first_response[1]).get("data", {}).get("flags", 0) == (64 if private else 0)


def test_bot_timeout_and_unexpected_exception_use_safe_fixed_messages():
    from tests.unit.discord.bot_builders import ask
    from tests.unit.query.bot_runtime import bot_request, bot_runtime

    for error, expected in [
        (TimeoutError("원문 표식"), "답변이 늦어져"),
        (RuntimeError("원문 표식"), "요청을 처리하지 못했습니다"),
    ]:

        def pipeline(job, stage, error=error):
            raise error

        runtime = bot_runtime(pipeline=pipeline)
        body = ask("합성 질문")
        signature = runtime.key.sign(body, "1000")
        _, _, headers = bot_request(runtime, body, headers=signature)
        run_id = headers["X-QK-Run"]
        runtime.jobs.start(run_id, signature["X-Signature-Ed25519"], "1000")
        runtime.jobs.poll()
        runtime.compute.run_next()
        runtime.deliveries.run_next()
        text = runtime.fake.requests[0].body["content"]
        assert expected in text and text.endswith(f"(확인 번호 {run_id[-8:]})") and "원문 표식" not in text
