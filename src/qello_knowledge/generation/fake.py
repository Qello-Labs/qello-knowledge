"""가짜 생성 제공자와 메모리 장부(QK-GEN-001 research R-13). 외부 호출이 없다."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime

from qello_knowledge.domain.embedding import PruneResult
from qello_knowledge.domain.generation import AnswerUsageToday, GenerationUsage, ProviderReply
from qello_knowledge.ports.generator import GenerationProviderFailure

FAKE_ANSWER = "자료에 따르면 그렇다 [S1]."  # 확인 명령의 기본 가짜 답(research R-10)


@dataclass(frozen=True)
class ProviderCall:
    model_id: str
    system: str = field(repr=False)
    user: str = field(repr=False)
    max_tokens: int
    temperature: float
    timeout_seconds: float


class ScriptedProvider:
    """호출 순서대로 미리 정한 응답이나 실패를 돌려준다. 다 쓰면 마지막 항목을 되풀이한다."""

    def __init__(self, script: Iterable[ProviderReply | GenerationProviderFailure] | None = None) -> None:
        self._script = list(script or [ProviderReply(FAKE_ANSWER, 10, 5)])
        self.calls: list[ProviderCall] = []

    def __repr__(self) -> str:
        return "ScriptedProvider()"

    def complete(
        self, model_id: str, system: str, user: str, max_tokens: int, temperature: float, timeout_seconds: float
    ) -> ProviderReply:
        self.calls.append(ProviderCall(model_id, system, user, max_tokens, temperature, timeout_seconds))
        item = self._script[min(len(self.calls), len(self._script)) - 1]
        if isinstance(item, GenerationProviderFailure):
            raise item
        return item


class MemoryLedger:
    """메모리 사용량 장부. `fail_record`가 참이면 기록할 때마다 오류를 낸다."""

    def __init__(
        self,
        *,
        query_embedding_used: float = 0.0,
        index_used: float = 0.0,
        query_reserve: int = 3000,
        fail_record: bool = False,
        day: date | None = None,
    ) -> None:
        self.records: list[GenerationUsage] = []
        self._query_embedding_used = query_embedding_used
        self._index_used = index_used
        self._query_reserve = query_reserve
        self._fail_record = fail_record
        self._day = day or datetime.now(UTC).date()

    def record(self, usage: GenerationUsage) -> AnswerUsageToday:
        if self._fail_record:
            raise OSError("usage store unavailable")
        self.records.append(usage)
        return self.today()

    def today(self) -> AnswerUsageToday:
        generation = sum(r.neurons for r in self.records)
        answer = generation + self._query_embedding_used
        return AnswerUsageToday(
            usage_day=self._day,
            generation_used=generation,
            query_embedding_used=self._query_embedding_used,
            answer_total=answer,
            index_used=self._index_used,
            day_total=answer + self._index_used,
            query_reserve=self._query_reserve,
            query_reserve_exceeded=answer > self._query_reserve,
        )

    def prune(self, retention_days: int = 90) -> PruneResult:
        return PruneResult(days_rolled_up=0, rows_deleted=0)
