"""형식만 맞춘 가짜 설정 값. 토큰 형식 문자열이 파일에 그대로 남지 않게 실행 중에 이어 붙여 만든다."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime

from qello_knowledge.domain.embedding import (
    BudgetSettings,
    DailyUsage,
    PruneResult,
    QueryUsage,
    Reservation,
    UsageOutcome,
)
from qello_knowledge.domain.store import EmbeddingRef

GITHUB_PREFIX = "gh" + "p_"


def valid_environ() -> dict[str, str]:
    scheme = "postgres" + "ql"
    return {
        "DATABASE_URL": f"{scheme}://qk@127.0.0.1:54322/postgres",
        "GITHUB_API_TOKEN": GITHUB_PREFIX + "x" * 36,
        "CLOUDFLARE_API_TOKEN": "c" * 40,
        "CLOUDFLARE_ACCOUNT_ID": "a" * 32,
        "DISCORD_APPLICATION_ID": "1" * 18,
        "DISCORD_PUBLIC_KEY": "f" * 64,
        "DISCORD_BOT_TOKEN": "d" * 60,
    }


# ---- QK-EMB-001: 메모리 저장소·사용량 장부 -------------------------------------------------------


class MemoryEmbeddingStore:
    """`Store`의 임베딩 연산만 메모리로 구현한다. 나머지 연산은 임베딩 시험에서 쓰지 않는다."""

    def __init__(self) -> None:
        self.vectors: dict[EmbeddingRef, tuple[float, ...]] = {}
        self.put_calls: list[EmbeddingRef] = []
        self.find_calls = 0

    def put_embedding(self, ref: EmbeddingRef, vector: Sequence[float]) -> None:
        self.put_calls.append(ref)
        self.vectors.setdefault(ref, tuple(vector))

    def find_embedding(self, ref: EmbeddingRef) -> tuple[float, ...] | None:
        return self.vectors.get(ref)

    def find_embeddings(self, refs: Sequence[EmbeddingRef]) -> dict[EmbeddingRef, tuple[float, ...]]:
        if not refs:
            return {}
        self.find_calls += 1
        return {ref: self.vectors[ref] for ref in refs if ref in self.vectors}


class InMemoryUsageLedger:
    """`UsageLedger` 메모리 구현. 하루는 주입 시계의 UTC 날짜다. 판정 규칙은 `qk.embedding_reserve`와 같다."""

    def __init__(self, settings: BudgetSettings | None = None, clock: Callable[[], datetime] | None = None) -> None:
        self.settings = settings or BudgetSettings()
        self.clock = clock or (lambda: datetime.now(UTC))
        self.rows: list[dict[str, object]] = []

    def _day(self) -> date:
        return self.clock().astimezone(UTC).date()

    def _amount(self, row: dict[str, object]) -> float:
        return float(row["neurons"] if row["state"] == "settled" else row["estimated_neurons"])  # type: ignore[arg-type]

    def _used(self, day: date, purpose: str) -> float:
        return sum(self._amount(r) for r in self.rows if r["usage_day"] == day and r["purpose"] == purpose)

    def _insert(self, **values: object) -> int:
        row_id = len(self.rows) + 1
        now = self.clock()
        self.rows.append({"id": row_id, "occurred_at": now, "usage_day": now.astimezone(UTC).date(), **values})
        return row_id

    def reserve(
        self, run_id: str, model_version: str, input_count: int, input_bytes: int, estimated: float
    ) -> Reservation | None:
        if self._used(self._day(), "index") + estimated > self.settings.index_budget:
            return None
        row_id = self._insert(
            purpose="index", run_id=run_id, model_version=model_version, input_count=input_count,
            input_bytes=input_bytes, estimated_neurons=estimated, neurons=None, measured=None,
            state="reserved", outcome=None,
        )  # fmt: skip
        return Reservation(row_id, estimated)

    def settle(self, reservation: Reservation, neurons: float, measured: bool, outcome: UsageOutcome) -> None:
        row = self.rows[reservation.reservation_id - 1]
        if row["state"] == "settled":
            return
        row.update(neurons=neurons, measured=measured, state="settled", outcome=outcome.value)

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
        self._insert(
            purpose="query", run_id=run_id, model_version=model_version, input_count=input_count,
            input_bytes=input_bytes, estimated_neurons=estimated, neurons=neurons, measured=measured,
            state="settled", outcome=outcome.value,
        )  # fmt: skip
        used = self._used(self._day(), "query")
        return QueryUsage(used, used > self.settings.query_reserve)

    def today(self) -> DailyUsage:
        day = self._day()
        rows = [r for r in self.rows if r["usage_day"] == day]
        total = sum(self._amount(r) for r in rows)
        estimated = sum(self._amount(r) for r in rows if r["state"] == "reserved" or r["measured"] is False)
        index_used = self._used(day, "index")
        return DailyUsage(
            usage_day=day,
            total=total,
            index_used=index_used,
            query_used=self._used(day, "query"),
            index_remaining=max(0.0, self.settings.index_budget - index_used),
            estimated_share=estimated / total if total else 0.0,
        )

    def prune(self, retention_days: int = 90) -> PruneResult:
        cutoff = self._day().toordinal() - retention_days
        old = [r for r in self.rows if r["usage_day"].toordinal() < cutoff]  # type: ignore[union-attr]
        self.rows = [r for r in self.rows if r not in old]
        return PruneResult(len({r["usage_day"] for r in old}), len(old))
