"""`GenerationLedger`의 PostgreSQL 구현(QK-GEN-001 research R-06).

마이그레이션 `0006_generation_usage.sql`의 함수를 한 번씩 부른다. DB 오류는 `GenerationUsageUnavailable`로 바꾸고
접속 정보를 문구에 넣지 않는다. 생성 경계는 이 오류를 잡아 답을 지킨다(spec FR-020).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from datetime import date
from typing import Any

import psycopg

from qello_knowledge.adapters.postgres.connection import connect
from qello_knowledge.domain.embedding import PruneResult
from qello_knowledge.domain.generation import AnswerUsageToday, GenerationUsage
from qello_knowledge.domain.store import StoreUnavailable


class GenerationUsageUnavailable(Exception):  # noqa: N818 - 저장소 상태 이름
    """생성 사용량 저장소를 쓸 수 없다. 문구에 접속 정보가 없다."""


def answer_usage(data: Mapping[str, Any]) -> AnswerUsageToday:
    return AnswerUsageToday(
        usage_day=date.fromisoformat(str(data["usage_day"])),
        generation_used=float(data["generation_used"]),
        query_embedding_used=float(data["query_embedding_used"]),
        answer_total=float(data["answer_total"]),
        index_used=float(data["index_used"]),
        day_total=float(data["day_total"]),
        query_reserve=int(data["query_reserve"]),
        query_reserve_exceeded=bool(data["query_reserve_exceeded"]),
    )


class PostgresGenerationLedger:
    """연결 하나를 쓴다. 스레드마다 따로 만든다."""

    def __init__(self, url: str, query_reserve: int) -> None:
        self._url = url
        self._query_reserve = query_reserve
        self._conn: psycopg.Connection | None = None

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> PostgresGenerationLedger:
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
            raise GenerationUsageUnavailable("생성 사용량 저장소에 연결할 수 없다") from exc
        except psycopg.OperationalError as exc:
            self.close()
            raise GenerationUsageUnavailable("생성 사용량 저장소를 쓸 수 없다") from exc
        except psycopg.Error as exc:
            raise GenerationUsageUnavailable(f"생성 사용량 저장소 오류: {exc.diag.sqlstate}") from exc

    def _call(self, sql: str, params: tuple[object, ...]) -> Any:
        with self._db() as conn:
            row = conn.execute(sql, params).fetchone()
        return row[0] if row else None

    def record(self, usage: GenerationUsage) -> AnswerUsageToday:
        data = self._call(
            "SELECT qk.generation_record(%s, %s, %s, %s::smallint, %s, %s, %s, %s::numeric, %s, %s, %s, %s)",
            (
                usage.run_id,
                usage.model_id,
                usage.prompt_version,
                usage.attempt,
                usage.input_tokens,
                usage.output_tokens,
                usage.estimated_input_tokens,
                usage.neurons,
                usage.measured,
                usage.outcome,
                usage.truncated,
                self._query_reserve,
            ),
        )
        return answer_usage(data)

    def today(self) -> AnswerUsageToday:
        return answer_usage(self._call("SELECT qk.generation_usage_today(%s)", (self._query_reserve,)))

    def prune(self, retention_days: int = 90) -> PruneResult:
        data = self._call("SELECT qk.generation_usage_prune(%s)", (retention_days,))
        return PruneResult(int(data["days_rolled_up"]), int(data["rows_deleted"]))
