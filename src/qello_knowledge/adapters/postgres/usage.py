"""`UsageLedger`의 PostgreSQL 구현(QK-EMB-001 research R-08).

마이그레이션 `0003_embedding_usage.sql`의 함수를 한 번씩 부른다. DB 오류는 `EmbedError(usage_unavailable)`로 바꾸고
접속 정보를 문구에 넣지 않는다.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import date
from typing import Any

import psycopg

from qello_knowledge.adapters.postgres.connection import connect
from qello_knowledge.domain.embedding import (
    BudgetSettings,
    DailyUsage,
    EmbedError,
    EmbedErrorKind,
    PruneResult,
    QueryUsage,
    Reservation,
    UsageOutcome,
)
from qello_knowledge.domain.store import StoreUnavailable


def daily_usage(data: Mapping[str, Any]) -> DailyUsage:
    return DailyUsage(
        usage_day=date.fromisoformat(str(data["usage_day"])),
        total=float(data["total"]),
        index_used=float(data["index_used"]),
        query_used=float(data["query_used"]),
        index_remaining=float(data["index_remaining"]),
        estimated_share=float(data["estimated_share"]),
    )


class PostgresUsageLedger:
    """연결 하나를 쓴다. 스레드마다 따로 만든다."""

    def __init__(self, url: str, settings: BudgetSettings) -> None:
        self._url = url
        self._settings = settings
        self._conn: psycopg.Connection | None = None

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> PostgresUsageLedger:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @contextmanager
    def _db(self) -> Iterator[psycopg.Connection]:
        try:
            if self._conn is None or self._conn.closed:
                self._conn = connect(self._url)
            yield self._conn
        except StoreUnavailable as exc:
            raise EmbedError(EmbedErrorKind.USAGE_UNAVAILABLE, "사용량 저장소에 연결할 수 없다") from exc
        except psycopg.OperationalError as exc:
            self.close()
            raise EmbedError(EmbedErrorKind.USAGE_UNAVAILABLE, "사용량 저장소를 쓸 수 없다") from exc
        except psycopg.Error as exc:
            raise EmbedError(EmbedErrorKind.USAGE_UNAVAILABLE, f"사용량 저장소 오류: {exc.diag.sqlstate}") from exc

    def _call(self, sql: str, params: tuple[object, ...]) -> Any:
        with self._db() as conn:
            row = conn.execute(sql, params).fetchone()
        return row[0] if row else None

    def reserve(
        self, run_id: str, model_version: str, input_count: int, input_bytes: int, estimated: float
    ) -> Reservation | None:
        data = self._call(
            "SELECT qk.embedding_reserve(%s, %s, %s, %s, %s::numeric, %s::numeric)",
            (run_id, model_version, input_count, input_bytes, estimated, self._settings.index_budget),
        )
        if not data["granted"]:
            return None
        return Reservation(int(data["reservation_id"]), estimated)

    def settle(self, reservation: Reservation, neurons: float, measured: bool, outcome: UsageOutcome) -> None:
        self._call(
            "SELECT qk.embedding_settle(%s, %s::numeric, %s, %s)",
            (reservation.reservation_id, neurons, measured, outcome.value),
        )

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
        data = self._call(
            "SELECT qk.embedding_record(%s, %s, %s, %s, %s::numeric, %s::numeric, %s, %s, %s::numeric)",
            (
                run_id,
                model_version,
                input_count,
                input_bytes,
                estimated,
                neurons,
                measured,
                outcome.value,
                self._settings.query_reserve,
            ),
        )
        return QueryUsage(float(data["query_used"]), bool(data["query_reserve_exceeded"]))

    def today(self) -> DailyUsage:
        data = self._call(
            "SELECT qk.embedding_usage_today(%s::numeric, %s::numeric)",
            (self._settings.index_budget, self._settings.query_reserve),
        )
        return daily_usage(data)

    def prune(self, retention_days: int = 90) -> PruneResult:
        data = self._call("SELECT qk.embedding_usage_prune(%s)", (retention_days,))
        return PruneResult(int(data["days_rolled_up"]), int(data["rows_deleted"]))
