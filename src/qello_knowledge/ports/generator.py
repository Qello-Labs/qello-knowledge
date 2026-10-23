"""생성 경계(QK-GEN-001 contracts/generation.md 2절).

후속 명세(QK-BOT-001 등)는 `Generator`만 보고 답변을 만든다. 외부 생성 모델 한 번 호출은 `GenerationProvider`,
사용량 기록은 `GenerationLedger`가 맡는다.
"""

from __future__ import annotations

from typing import Protocol

from qello_knowledge.domain.embedding import PruneResult
from qello_knowledge.domain.generation import (
    AnswerUsageToday,
    GenerationFailure,
    GenerationRequest,
    GenerationResult,
    GenerationUsage,
    ProviderReply,
    ResponseShape,
)


class Generator(Protocol):
    """검색된 근거로 답변을 만든다."""

    def generate(self, request: GenerationRequest) -> GenerationResult: ...


class GenerationProviderFailure(Exception):  # noqa: N818 - 계약(contracts/generation.md)의 이름을 따른다
    """생성 제공자 호출 실패. 메시지에 토큰·계정 ID·본문을 넣지 않는다."""

    def __init__(
        self,
        kind: GenerationFailure,
        *,
        billable: bool,
        retry_after_seconds: float | None = None,
        neurons: float | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        shape: ResponseShape | None = None,
    ) -> None:
        self.kind = kind
        self.billable = billable
        self.retry_after_seconds = retry_after_seconds
        self.neurons = neurons
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.shape = shape
        super().__init__(kind.value)


class GenerationProvider(Protocol):
    """외부 생성 모델 한 번 호출. 재시도는 하지 않는다(재시도는 생성 경계가 한다)."""

    def complete(
        self, model_id: str, system: str, user: str, max_tokens: int, temperature: float, timeout_seconds: float
    ) -> ProviderReply: ...


class GenerationLedger(Protocol):
    """생성 사용량 장부. 하루 경계는 UTC다(QK-EMB-001과 같음)."""

    def record(self, usage: GenerationUsage) -> AnswerUsageToday: ...

    def today(self) -> AnswerUsageToday: ...

    def prune(self, retention_days: int = 90) -> PruneResult: ...
