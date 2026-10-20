"""임베딩 경계(QK-EMB-001 contracts/embedder.md).

후속 명세(QK-SYN-001, QK-RET-001)는 `Embedder`만 보고 임베딩을 쓴다. 외부 제공자 한 번 호출은 `EmbeddingProvider`,
사용량 기록과 예산 예약은 `UsageLedger`가 맡는다(research R-01, R-08).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from qello_knowledge.domain.embedding import (
    DailyUsage,
    EmbedPreview,
    EmbedRequest,
    EmbedResult,
    ModelSpec,
    ProviderFailureKind,
    PruneResult,
    QueryUsage,
    Reservation,
    SendBlock,
    UsageOutcome,
)


class Embedder(Protocol):
    """텍스트 묶음을 활성 인덱스 버전 모델의 벡터로 바꾼다."""

    def embed(self, request: EmbedRequest) -> EmbedResult:
        """결과 길이와 순서는 입력과 같다. 항목별 실패는 값으로, 묶음 전체 실패는 `EmbedError`로 알린다."""
        ...

    def preview(self, request: EmbedRequest) -> EmbedPreview:
        """외부 호출·예약·저장 없이 예상 사용량과 실행 가능 여부를 계산한다(FR-022)."""
        ...


@dataclass(frozen=True)
class ProviderBatch:
    vectors: tuple[tuple[float, ...], ...]
    neurons: float | None  # 제공자가 알려 준 사용량. 없으면 `None`(FR-014)


class ProviderFailure(Exception):  # noqa: N818 - 계약(contracts/embedder.md)의 이름을 따른다
    """제공자 호출 실패. 메시지에 토큰·계정 ID·텍스트를 넣지 않는다."""

    def __init__(self, kind: ProviderFailureKind, retry_after_seconds: float | None = None) -> None:
        self.kind = kind
        self.retry_after_seconds = retry_after_seconds
        super().__init__(kind.value)


class EmbeddingProvider(Protocol):
    """외부 제공자 한 번 호출. 재시도는 하지 않는다(재시도는 `EmbeddingService`가 한다)."""

    def embed_texts(self, model: ModelSpec, texts: Sequence[str]) -> ProviderBatch: ...


class UsageLedger(Protocol):
    """하루(UTC) 사용량 장부. `index_budget`, `query_reserve`는 생성 시 `BudgetSettings`로 받는다."""

    def reserve(
        self, run_id: str, model_version: str, input_count: int, input_bytes: int, estimated: float
    ) -> Reservation | None:
        """색인용 요청 직전 예약. 색인 예산을 넘으면 `None`(FR-018, FR-021)."""
        ...

    def settle(self, reservation: Reservation, neurons: float, measured: bool, outcome: UsageOutcome) -> None:
        """예약을 실제 값으로 바꾼다. 이미 정산된 예약이면 아무것도 하지 않는다."""
        ...

    def record(
        self,
        run_id: str,
        model_version: str,
        input_count: int,
        input_bytes: int,
        estimated: float,
        neurons: float,
        measured: bool,
        outcome: UsageOutcome,
    ) -> QueryUsage:
        """질의용 호출을 예약 없이 기록한다(FR-019)."""
        ...

    def today(self) -> DailyUsage: ...

    def prune(self, retention_days: int = 90) -> PruneResult: ...


OutgoingCheck = Callable[[str, tuple[str, str] | None], Sequence[SendBlock]]
"""전송 직전 검사. 걸린 규칙을 돌려주고, 비어 있으면 보낼 수 있다(FR-005). 조립 코드가 QK-SEC-001 검사를 넘긴다."""

RetryDelay = Callable[[int, float | None], float]
"""(재시도 번호 0부터, 제공자가 알려 준 대기 초) → 대기 초. 조립 코드가 QK-ING-001 재시도 규칙을 넘긴다."""
