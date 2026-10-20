"""임베딩 경계의 입력·출력 타입(QK-EMB-001 data-model.md 1절).

외부 제공자 고유 타입·HTTP 상태·오류 코드는 여기에 나오지 않는다(FR-001, SC-007).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import StrEnum

HASH_RULE = "emb-hash-v1"  # 바꾸면 인덱스 버전을 올린다(C-07, research R-07)


@dataclass(frozen=True)
class ModelSpec:
    """모델별 고정값. 어떤 모델을 쓸지는 인덱스 버전의 `embedding_model`이 정한다(research R-03)."""

    model_version: str
    dimension: int
    max_input_tokens: int
    neurons_per_million_tokens: float
    bytes_per_token_estimate: float


MODELS: Mapping[str, ModelSpec] = {
    "@cf/baai/bge-m3": ModelSpec(
        model_version="@cf/baai/bge-m3",
        dimension=1024,
        max_input_tokens=8192,
        neurons_per_million_tokens=1075,
        bytes_per_token_estimate=3.5,
    ),
}


class EmbedPurpose(StrEnum):
    INDEX = "index"
    QUERY = "query"


class EmbedFailureKind(StrEnum):
    """항목 하나의 실패. 같은 묶음의 다른 항목은 계속 처리한다(FR-004)."""

    EMPTY_INPUT = "empty_input"
    NO_ORIGIN = "no_origin"
    SECRET_BLOCKED = "secret_blocked"  # noqa: S105 - 실패 종류 이름이다
    INPUT_TOO_LONG = "input_too_long"
    TRANSIENT = "transient"
    PROVIDER_QUOTA = "provider_quota"
    INDEX_BUDGET = "index_budget"
    BAD_RESPONSE = "bad_response"
    USAGE_UNAVAILABLE = "usage_unavailable"  # 사용량 기록이 실패해 보내지 않은 항목(spec Edge Cases)


class EmbedErrorKind(StrEnum):
    """묶음 전체를 멈추는 실패. 이미 만든 벡터는 예외 전에 저장된다(FR-011)."""

    AUTH_CONFIG = "auth_config"
    NO_ACTIVE_INDEX = "no_active_index"
    USAGE_UNAVAILABLE = "usage_unavailable"


class EmbedError(Exception):
    """메시지에 텍스트·토큰·계정 정보를 넣지 않는다."""

    def __init__(self, kind: EmbedErrorKind, message: str = "") -> None:
        self.kind = kind
        super().__init__(f"{kind.value}: {message}" if message else kind.value)


class ProviderFailureKind(StrEnum):
    INPUT_TOO_LONG = "input_too_long"
    TRANSIENT = "transient"
    PROVIDER_QUOTA = "provider_quota"
    AUTH_CONFIG = "auth_config"
    BAD_RESPONSE = "bad_response"


class UsageOutcome(StrEnum):
    """사용량 기록의 `outcome` 칼럼 값(data-model.md 2절)."""

    OK = "ok"
    INPUT_TOO_LONG = "input_too_long"
    TRANSIENT = "transient"
    PROVIDER_QUOTA = "provider_quota"
    BAD_RESPONSE = "bad_response"
    AUTH_CONFIG = "auth_config"


@dataclass(frozen=True)
class EmbedInput:
    """`origin`은 (자료원 이름, 경로)다. 색인용은 반드시 있고 질의용은 `None`이다(FR-005)."""

    text: str = field(repr=False)
    origin: tuple[str, str] | None = None


@dataclass(frozen=True)
class EmbedRequest:
    inputs: tuple[EmbedInput, ...]
    purpose: EmbedPurpose
    model_version: str
    run_id: str
    allow_partial: bool = False  # 색인용에서만 뜻이 있다(FR-024)


@dataclass(frozen=True)
class EmbedItem:
    index: int
    vector: tuple[float, ...] | None = field(default=None, repr=False)
    failure: EmbedFailureKind | None = None
    cached: bool = False

    def __post_init__(self) -> None:
        if (self.vector is None) == (self.failure is None):
            raise ValueError("vector와 failure 중 하나만 있어야 한다")


@dataclass(frozen=True)
class RunSummary:
    """QK-SYN-001 실행 기록이 그대로 쓴다(FR-015)."""

    requested: int
    cache_hits: int = 0
    deduplicated: int = 0
    provider_calls: int = 0
    failures: Mapping[str, int] = field(default_factory=dict)
    neurons: float = 0.0
    estimated_neurons: float = 0.0
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class EmbedResult:
    items: tuple[EmbedItem, ...]
    model_version: str
    dimension: int
    summary: RunSummary


@dataclass(frozen=True)
class EstimateBasis:
    """예상 Neurons 계산 근거(FR-023)."""

    bytes_total: int
    bytes_per_token: float
    neurons_per_million_tokens: float


@dataclass(frozen=True)
class EmbedPreview:
    requested: int
    cache_hits: int
    deduplicated: int
    to_embed: int
    over_limit_expected: int
    estimated_neurons: float
    basis: EstimateBasis
    index_budget: float
    index_used_today: float
    index_remaining: float
    runnable: bool


@dataclass(frozen=True)
class BudgetSettings:
    """하루 무료 할당과 용도별 몫. 단위는 Neurons다(FR-017, research R-11)."""

    daily_allowance: int = 10000
    index_budget: int = 5000
    query_reserve: int = 3000

    @property
    def within_allowance(self) -> bool:
        return self.index_budget + self.query_reserve <= self.daily_allowance


@dataclass(frozen=True)
class Reservation:
    reservation_id: int
    estimated: float


@dataclass(frozen=True)
class DailyUsage:
    usage_day: date
    total: float
    index_used: float
    query_used: float
    index_remaining: float
    estimated_share: float  # 합계 중 추정값(측정 안 됨·정산 전)의 비율, 0~1


@dataclass(frozen=True)
class QueryUsage:
    query_used: float
    query_reserve_exceeded: bool


@dataclass(frozen=True)
class PruneResult:
    days_rolled_up: int
    rows_deleted: int


@dataclass(frozen=True)
class SendBlock:
    """전송 직전 검사에 걸린 규칙. 텍스트와 맞은 문자열은 담지 않는다(QK-SEC-001 FR-013)."""

    rule: str
    line: int
