"""운영 사용 장부 읽기 구현(QK-EVL-001 research R-07, tasks T006).

실행 명령의 관문은 로컬 장부를 거부하므로 이 시험은 구현만 직접 부른다. 시험용 데이터베이스는 세션 픽스처(`db_url`)다.
"""

from __future__ import annotations

from datetime import UTC, datetime

import psycopg
import pytest

from qello_knowledge.adapters.postgres.eval_target import PostgresDayUsageReader
from qello_knowledge.domain.generation import AnswerUsageToday
from qello_knowledge.ports.evaluation import LedgerUnavailable
from tests.localdb.store.conftest import db_url  # noqa: F401 - 세션 fixture를 이 디렉터리에서도 쓴다

pytestmark = pytest.mark.localdb


def _rows(url: str) -> tuple[int, int]:
    with psycopg.connect(url, autocommit=True) as conn:
        return conn.execute(
            "SELECT (SELECT count(*) FROM qk.embedding_usage), (SELECT count(*) FROM qk.generation_usage)"
        ).fetchone()


def test_today_reads_day_total_once(db_url: str) -> None:  # noqa: F811
    before = _rows(db_url)
    usage = PostgresDayUsageReader(db_url, query_reserve=500).today()
    assert isinstance(usage, AnswerUsageToday)
    assert usage.usage_day == datetime.now(UTC).date()
    assert usage.day_total >= 0 and usage.query_reserve == 500
    assert _rows(db_url) == before


def test_reader_connection_is_read_only(db_url: str) -> None:  # noqa: F811
    reader = PostgresDayUsageReader(db_url, query_reserve=500)
    with pytest.raises(LedgerUnavailable):
        with reader._open() as conn:
            conn.execute("DELETE FROM qk.embedding_usage")


def test_unreachable_ledger_is_unavailable() -> None:
    reader = PostgresDayUsageReader("host=127.0.0.1 port=1 dbname=qk user=x connect_timeout=1", query_reserve=500)
    with pytest.raises(LedgerUnavailable):
        reader.today()
