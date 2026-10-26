"""FR-006·011 안내 문구. 실패 종류·외부 오류 원문을 사용자에게 내보내지 않는다."""

from types import MappingProxyType

from qello_knowledge.domain.generation import GenerationFailure, GenerationStatus
from qello_knowledge.domain.retrieval import RetrievalFailure

OUTGOING_BLOCKED = "질문에 비밀값으로 보이는 내용이 있어 처리하지 않았습니다. 해당 값을 지우고 다시 질문해 주세요."
SEARCH_RETRY = "지금은 자료를 검색할 수 없습니다. 잠시 후 다시 질문해 주세요."
GENERATION_RETRY = "답변을 만들지 못했습니다. 잠시 후 다시 질문해 주세요."
GENERATION_OPERATOR = "답변을 만드는 중 문제가 생겼습니다. 운영 담당자에게 알려 주세요."
QUESTION_LENGTH = "질문을 {question_max_chars:,}자 안으로 입력해 주세요."
SOURCE_UNVERIFIED = "⚠️ 출처를 확인하지 못한 답변입니다. 원문으로 확인해 주세요."
OUTPUT_TRUNCATED = "(답변이 길어 일부가 잘렸습니다.)"

FIXED_NOTICES = MappingProxyType(
    {
        "unsupported": "지원하지 않는 요청입니다.",
        "access": "이 채널에서는 `/ask`를 쓸 수 없습니다.",
        "secret": OUTGOING_BLOCKED,
        "duplicate": "이미 처리 중인 요청입니다.",
        "busy": "지금 요청이 많습니다. 잠시 후 다시 질문해 주세요.",
        "not_started": "요청을 처리하지 못했습니다. 잠시 후 다시 질문해 주세요.",
        "relay_failed": "지금은 답할 수 없습니다. 잠시 후 다시 질문해 주세요.",
        "timed_out": "답변이 늦어져 처리를 멈췄습니다. 잠시 후 다시 질문해 주세요.",
        "unexpected": "요청을 처리하지 못했습니다. 운영 담당자에게 알려 주세요.",
    }
)
RETRIEVAL_NOTICES = MappingProxyType(
    {
        RetrievalFailure.EMPTY_QUESTION: QUESTION_LENGTH,
        RetrievalFailure.QUESTION_TOO_LONG: QUESTION_LENGTH,
        RetrievalFailure.NO_ACTIVE_INDEX: "검색할 자료가 아직 준비되지 않았습니다. 운영 담당자에게 알려 주세요.",
        RetrievalFailure.STORE_UNAVAILABLE: SEARCH_RETRY,
        RetrievalFailure.INDEX_VERSION_CHANGED: SEARCH_RETRY,
        RetrievalFailure.QUERY_EMBEDDING_FAILED: SEARCH_RETRY,
        RetrievalFailure.OUTGOING_BLOCKED: OUTGOING_BLOCKED,
        RetrievalFailure.KEYWORD_SEARCH_FAILED: SEARCH_RETRY,
        RetrievalFailure.BOTH_SEARCHES_FAILED: SEARCH_RETRY,
    }
)
GENERATION_NOTICES = MappingProxyType(
    {
        GenerationFailure.TRANSIENT: GENERATION_RETRY,
        GenerationFailure.TIMEOUT: GENERATION_RETRY,
        GenerationFailure.PROVIDER_QUOTA: "오늘 사용 한도에 닿아 답변할 수 없습니다. 내일 다시 질문해 주세요.",
        GenerationFailure.AUTH_CONFIG: GENERATION_OPERATOR,
        GenerationFailure.BAD_RESPONSE: GENERATION_OPERATOR,
        GenerationFailure.INPUT_TOO_LONG: GENERATION_OPERATOR,
    }
)
STATUS_NOTICES = MappingProxyType(
    {
        GenerationStatus.ANSWERED: None,
        GenerationStatus.CANNOT_CONFIRM: None,
        GenerationStatus.RETRIEVAL_FAILED: SEARCH_RETRY,
        GenerationStatus.OUTGOING_BLOCKED: OUTGOING_BLOCKED,
        GenerationStatus.GENERATION_FAILED: GENERATION_OPERATOR,
    }
)


def _with_reference(text: str, run_id: str) -> str:
    return f"{text} (확인 번호 {run_id[-8:]})"


def failure_notice(
    failure: RetrievalFailure | GenerationFailure | str, run_id: str, *, question_max_chars: int = 2000
) -> str:
    if isinstance(failure, RetrievalFailure):
        text = RETRIEVAL_NOTICES[failure]
    elif isinstance(failure, GenerationFailure):
        text = GENERATION_NOTICES[failure]
    else:
        text = FIXED_NOTICES.get(failure, FIXED_NOTICES["unexpected"])
    return _with_reference(text.format(question_max_chars=question_max_chars), run_id)


def status_notice(
    status: GenerationStatus,
    run_id: str,
    *,
    body: str = "",
    retrieval_failure: RetrievalFailure | None = None,
    generation_failure: GenerationFailure | None = None,
    question_max_chars: int = 2000,
) -> str:
    if status in (GenerationStatus.ANSWERED, GenerationStatus.CANNOT_CONFIRM):
        return body
    if status is GenerationStatus.RETRIEVAL_FAILED and retrieval_failure is not None:
        return failure_notice(retrieval_failure, run_id, question_max_chars=question_max_chars)
    if status is GenerationStatus.GENERATION_FAILED and generation_failure is not None:
        return failure_notice(generation_failure, run_id)
    return _with_reference(STATUS_NOTICES[status], run_id)
