"""답변 생성의 설정·입력·결과·사용량 타입(QK-GEN-001 data-model 1~5절).

질문·답변·청크 본문·생성 입력 원문은 `repr`에 나오지 않는다(spec FR-012). 제공자 고유 타입은 나오지 않는다(C-06).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import StrEnum

from qello_knowledge.domain.retrieval import ContextBlock, RetrievalResult, RetrievalSummary

CANNOT_CONFIRM = "제공된 자료만으로 확인할 수 없습니다."  # constitution C-01, 승인 프롬프트 규칙 3
CHECK_ORIGIN = "현재 상태는 원본에서 확인해야 합니다."  # 승인 프롬프트 규칙 6
NO_THINK = " /no_think"  # qwen3 계열 추론 끔 표기(ADR-009). 템플릿 끝에 들어 있다
PROMPT_NAMES = ("gen-p1", "gen-base")  # `generation/prompts.py`의 이름과 같아야 한다(tasks T007)
MODEL_PREFIX = "@cf/qwen/qwen3-"  # 다른 계열은 ADR-009 개정이 필요하다(spec FR-018)
CONTEXT_WINDOW = 32768  # ADR-009
MAX_RETRY_WAIT = 2.0  # 질의 경로 재시도 대기 상한(QK-RET-001 research R-07)


class GenerationStatus(StrEnum):
    ANSWERED = "answered"
    CANNOT_CONFIRM = "cannot_confirm"
    RETRIEVAL_FAILED = "retrieval_failed"
    OUTGOING_BLOCKED = "outgoing_blocked"
    GENERATION_FAILED = "generation_failed"


class GenerationFailure(StrEnum):
    TRANSIENT = "transient"
    TIMEOUT = "timeout"
    PROVIDER_QUOTA = "provider_quota"
    AUTH_CONFIG = "auth_config"
    BAD_RESPONSE = "bad_response"
    INPUT_TOO_LONG = "input_too_long"


class CannotConfirmReason(StrEnum):
    NO_RESULTS = "no_results"
    EMPTY_CONTEXT = "empty_context"
    ALL_BLOCKS_BLOCKED = "all_blocks_blocked"
    MODEL_CANNOT_CONFIRM = "model_cannot_confirm"
    MODEL_UNCONFIRMABLE_PARTS = "model_unconfirmable_parts"


RETRYABLE = frozenset({GenerationFailure.TRANSIENT, GenerationFailure.TIMEOUT})


@dataclass(frozen=True)
class GenerationSettings:
    """생성 조건(data-model 1절). 범위를 벗어나면 만들 때 `ValueError`."""

    model_id: str = "@cf/qwen/qwen3-30b-a3b-fp8"
    max_tokens: int = 800
    temperature: float = 0.2
    timeout_seconds: float = 20
    prompt_version: str = "gen-p1"
    bytes_per_token: float = 3.5
    underestimate_factor: float = 2.0
    context_window: int = CONTEXT_WINDOW
    input_price_per_m: float = 4625
    output_price_per_m: float = 30475
    max_attempts: int = 2
    deadline_seconds: float | None = None  # 없으면 `2 × timeout_seconds + 5`

    def __post_init__(self) -> None:
        problems = []
        if not self.model_id.startswith(MODEL_PREFIX):
            problems.append("model_id")
        if not 1 <= self.max_tokens <= 4096:
            problems.append("max_tokens")
        if not 0 <= self.temperature <= 1:
            problems.append("temperature")
        if not 1 <= self.timeout_seconds <= 60:
            problems.append("timeout_seconds")
        if self.prompt_version not in PROMPT_NAMES:
            problems.append("prompt_version")
        if self.bytes_per_token <= 0:
            problems.append("bytes_per_token")
        if not 1.0 <= self.underestimate_factor <= 4.0:
            problems.append("underestimate_factor")
        if self.context_window != CONTEXT_WINDOW:
            problems.append("context_window")
        if self.input_price_per_m <= 0 or self.output_price_per_m <= 0:
            problems.append("price")
        if self.max_attempts != 2:
            problems.append("max_attempts")
        if self.deadline_seconds is not None and not (
            2 * self.timeout_seconds + MAX_RETRY_WAIT <= self.deadline_seconds <= 130
        ):
            problems.append("deadline_seconds")
        if problems:
            raise ValueError("생성 설정 범위 밖: " + ", ".join(problems))

    @property
    def deadline(self) -> float:
        """재시도를 시작할 수 있는 마감(초). 설정만으로 재시도가 꺼지지 않게 시간 제한에서 계산한다(research R-07)."""
        return self.deadline_seconds if self.deadline_seconds is not None else 2 * self.timeout_seconds + 5

    def estimated_neurons(self, input_tokens: int, output_tokens: int) -> float:
        return (input_tokens * self.input_price_per_m + output_tokens * self.output_price_per_m) / 1_000_000


@dataclass(frozen=True)
class PromptSpec:
    """프롬프트 하나(research R-02). `version`은 세 값에서 결정적으로 정해진다."""

    name: str
    system: str = field(repr=False)
    user_template: str = field(repr=False)
    render_rule: str

    def __post_init__(self) -> None:
        if not self.user_template.endswith(NO_THINK):
            raise ValueError("사용자 메시지 템플릿은 추론 끔 표기로 끝나야 한다")
        if "{context}" not in self.user_template or "{question}" not in self.user_template:
            raise ValueError("사용자 메시지 템플릿에 {context}·{question} 자리가 있어야 한다")

    @property
    def version(self) -> str:
        material = json.dumps(
            {"system": self.system, "template": self.user_template, "render_rule": self.render_rule},
            ensure_ascii=False,
            sort_keys=True,
        )
        return f"{self.name}-{hashlib.sha256(material.encode('utf-8')).hexdigest()[:12]}"


@dataclass(frozen=True)
class GenerationRequest:
    question: str = field(repr=False)
    retrieval: RetrievalResult
    prompt_version: str | None = None
    run_id: str | None = None


@dataclass(frozen=True)
class RenderedBlock:
    source_id: str
    block: ContextBlock = field(repr=False)
    raw_title: str = field(repr=False)
    title: str = field(repr=False)
    modified_label: str
    text: str = field(repr=False)
    excerpt_urls: frozenset[str] = field(repr=False)
    estimated_tokens: int


@dataclass(frozen=True)
class DroppedBlock:
    source_id: str
    rules: tuple[str, ...]


@dataclass(frozen=True)
class RenderedInput:
    system: str = field(repr=False)
    user: str = field(repr=False)
    blocks: tuple[RenderedBlock, ...]
    dropped: tuple[DroppedBlock, ...] = ()
    neutralized: int = 0
    estimated_input_tokens: int = 0


@dataclass(frozen=True)
class ResponseShape:
    """응답의 꼴. 키 이름만 담고 값·본문은 담지 않는다(research R-01)."""

    top_keys: tuple[str, ...] = ()
    result_keys: tuple[str, ...] = ()
    has_usage: bool = False
    has_neurons_header: bool = False
    has_finish_reason: bool = False
    parsed_as: str | None = None  # "response" | "choices" | None


@dataclass(frozen=True)
class ProviderReply:
    text: str = field(repr=False)
    input_tokens: int | None = None
    output_tokens: int | None = None
    neurons: float | None = None
    finish_reason: str | None = None
    shape: ResponseShape = field(default_factory=ResponseShape)


@dataclass(frozen=True)
class Citation:
    source_id: str
    title: str
    source_url: str
    source_version: str
    source_modified_at: datetime | None
    collected_at: datetime


@dataclass(frozen=True)
class GenerationFlags:
    unsupported_answer: bool = False  # 출처 확인 안 됨(spec FR-015)
    truncated: bool = False  # 출력 잘림(spec FR-023)
    usage_record_failed: bool = False  # 사용량 기록 실패(spec FR-020)
    thinking_detected: bool = False  # 추론 출력 감지(Edge Cases)


@dataclass(frozen=True)
class AnswerUsageToday:
    usage_day: date
    generation_used: float
    query_embedding_used: float
    answer_total: float
    index_used: float
    day_total: float
    query_reserve: int
    query_reserve_exceeded: bool


@dataclass(frozen=True)
class GenerationSummary:
    """생성 요약(spec FR-026). 질문·답변·청크 본문·URL은 없다."""

    status: GenerationStatus
    failure: GenerationFailure | None = None
    cannot_confirm_reason: CannotConfirmReason | None = None
    retrieval_failure: str | None = None
    prompt_version: str = ""
    model_id: str = ""
    max_tokens: int = 0
    temperature: float = 0.0
    no_think: bool = True
    blocks_sent: int = 0
    dropped: tuple[DroppedBlock, ...] = ()
    estimated_input_tokens: int = 0
    input_tokens: int | None = None
    output_tokens: int | None = None
    neurons: float = 0.0
    measured: bool = False
    attempts: int = 0
    latency_ms: int = 0
    removed_citations: int = 0
    unrecognized_citations: int = 0
    uncited_sentences: int = 0
    removed_urls: int = 0
    removed_source_lines: int = 0
    neutralized: int = 0
    flags: GenerationFlags = field(default_factory=GenerationFlags)
    generation_calls: int = 0
    total_calls: int = 0
    usage_today: AnswerUsageToday | None = None
    response_shape: ResponseShape | None = None


@dataclass(frozen=True)
class GenerationResult:
    status: GenerationStatus
    answer: str = field(repr=False)
    citations: tuple[Citation, ...]
    summary: GenerationSummary
    retrieval: RetrievalSummary

    def __post_init__(self) -> None:
        if self.status is GenerationStatus.CANNOT_CONFIRM and self.citations:
            raise ValueError("확인 불가 결과에는 출처가 없어야 한다")
        if self.summary.flags.unsupported_answer and (self.status is not GenerationStatus.ANSWERED or self.citations):
            raise ValueError("출처 확인 안 됨은 출처 없는 답변에만 붙는다")
        ids = [c.source_id for c in self.citations]
        if len(set(ids)) != len(ids):
            raise ValueError("출처 목록의 Source ID는 한 번씩만 나온다")


@dataclass(frozen=True)
class GenerationUsage:
    """생성 호출 시도 하나의 사용량(spec FR-020). 원문 필드는 없다."""

    run_id: str
    model_id: str
    prompt_version: str
    attempt: int
    input_tokens: int | None
    output_tokens: int | None
    estimated_input_tokens: int
    neurons: float
    measured: bool
    outcome: str  # "ok" 또는 GenerationFailure 값
    truncated: bool = False

    def __post_init__(self) -> None:
        if self.attempt not in (1, 2):
            raise ValueError("시도 번호는 1 또는 2")
        if self.outcome != "ok" and self.outcome not in {f.value for f in GenerationFailure}:
            raise ValueError("알 수 없는 결과 종류")
        if self.neurons < 0 or self.estimated_input_tokens < 0:
            raise ValueError("사용량은 음수가 아니다")
