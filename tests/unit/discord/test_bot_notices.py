import pytest

from qello_knowledge.discord.notices import (
    FIXED_NOTICES,
    GENERATION_NOTICES,
    OUTPUT_TRUNCATED,
    RETRIEVAL_NOTICES,
    SOURCE_UNVERIFIED,
    STATUS_NOTICES,
    failure_notice,
    status_notice,
)
from qello_knowledge.domain.generation import GenerationFailure, GenerationStatus
from qello_knowledge.domain.retrieval import RetrievalFailure

BOT_RETRY_SEARCH = "지금은 자료를 검색할 수 없습니다. 잠시 후 다시 질문해 주세요."
BOT_SECRET = "질문에 비밀값으로 보이는 내용이 있어 처리하지 않았습니다. 해당 값을 지우고 다시 질문해 주세요."


def test_bot_notice_tables_cover_all_values():
    assert set(RETRIEVAL_NOTICES) == set(RetrievalFailure)
    assert set(GENERATION_NOTICES) == set(GenerationFailure)
    assert set(STATUS_NOTICES) == set(GenerationStatus)
    assert RETRIEVAL_NOTICES == {
        RetrievalFailure.STORE_UNAVAILABLE: BOT_RETRY_SEARCH,
        RetrievalFailure.INDEX_VERSION_CHANGED: BOT_RETRY_SEARCH,
        RetrievalFailure.QUERY_EMBEDDING_FAILED: BOT_RETRY_SEARCH,
        RetrievalFailure.KEYWORD_SEARCH_FAILED: BOT_RETRY_SEARCH,
        RetrievalFailure.BOTH_SEARCHES_FAILED: BOT_RETRY_SEARCH,
        RetrievalFailure.NO_ACTIVE_INDEX: "검색할 자료가 아직 준비되지 않았습니다. 운영 담당자에게 알려 주세요.",
        RetrievalFailure.EMPTY_QUESTION: "질문을 {question_max_chars:,}자 안으로 입력해 주세요.",
        RetrievalFailure.QUESTION_TOO_LONG: "질문을 {question_max_chars:,}자 안으로 입력해 주세요.",
        RetrievalFailure.OUTGOING_BLOCKED: BOT_SECRET,
    }
    retry = "답변을 만들지 못했습니다. 잠시 후 다시 질문해 주세요."
    operator = "답변을 만드는 중 문제가 생겼습니다. 운영 담당자에게 알려 주세요."
    assert GENERATION_NOTICES == {
        GenerationFailure.TRANSIENT: retry,
        GenerationFailure.TIMEOUT: retry,
        GenerationFailure.PROVIDER_QUOTA: "오늘 사용 한도에 닿아 답변할 수 없습니다. 내일 다시 질문해 주세요.",
        GenerationFailure.AUTH_CONFIG: operator,
        GenerationFailure.BAD_RESPONSE: operator,
        GenerationFailure.INPUT_TOO_LONG: operator,
    }


def test_bot_fixed_notices_and_display_flags():
    assert FIXED_NOTICES == {
        "unsupported": "지원하지 않는 요청입니다.",
        "access": "이 채널에서는 `/ask`를 쓸 수 없습니다.",
        "secret": BOT_SECRET,
        "duplicate": "이미 처리 중인 요청입니다.",
        "busy": "지금 요청이 많습니다. 잠시 후 다시 질문해 주세요.",
        "not_started": "요청을 처리하지 못했습니다. 잠시 후 다시 질문해 주세요.",
        "relay_failed": "지금은 답할 수 없습니다. 잠시 후 다시 질문해 주세요.",
        "timed_out": "답변이 늦어져 처리를 멈췄습니다. 잠시 후 다시 질문해 주세요.",
        "unexpected": "요청을 처리하지 못했습니다. 운영 담당자에게 알려 주세요.",
    }
    assert SOURCE_UNVERIFIED == "⚠️ 출처를 확인하지 못한 답변입니다. 원문으로 확인해 주세요."
    assert OUTPUT_TRUNCATED == "(답변이 길어 일부가 잘렸습니다.)"


@pytest.mark.parametrize(
    "failure", list(RetrievalFailure) + list(GenerationFailure) + ["timed_out", "unexpected", "not_started"]
)
def test_bot_failure_reference_no_internal_names(failure):
    text = failure_notice(failure, "q-run-1a2b3c4d")
    assert text.endswith(" (확인 번호 1a2b3c4d)")
    assert str(failure) not in text
    if failure is RetrievalFailure.QUESTION_TOO_LONG:
        assert "2,000자" in text
        assert "500자" in failure_notice(failure, "run", question_max_chars=500)


def test_bot_status_mapping_and_next_actions():
    for status in GenerationStatus:
        result = status_notice(
            status,
            "q-run-1a2b3c4d",
            body="synthetic body",
            retrieval_failure=RetrievalFailure.STORE_UNAVAILABLE,
            generation_failure=GenerationFailure.TIMEOUT,
        )
        if status in (GenerationStatus.ANSWERED, GenerationStatus.CANNOT_CONFIRM):
            assert result == "synthetic body"
        else:
            assert result.endswith("(확인 번호 1a2b3c4d)")
    assert "내일 다시" in failure_notice(GenerationFailure.PROVIDER_QUOTA, "run")
    assert "운영 담당자" in failure_notice(GenerationFailure.AUTH_CONFIG, "run")
    assert "잠시 후 다시" in failure_notice(GenerationFailure.TRANSIENT, "run")
