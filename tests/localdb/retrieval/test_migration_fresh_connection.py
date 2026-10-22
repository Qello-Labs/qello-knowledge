"""0005가 앞 마이그레이션을 이미 적용한 DB에 새 연결로 적용되는지(구현 중 발견, tasks 실행 기록).

슈퍼유저가 아닌 로컬 역할에서 PGroonga 라이브러리가 로드되기 전에 `CREATE FUNCTION ... SET pgroonga.*`가 실패했다.
"""

from __future__ import annotations

import io

import psycopg
import pytest

from qello_knowledge.adapters.postgres.migrate import apply_migrations, load_migrations
from tests.conftest import _local_db_reachable, local_db_port
from tests.localdb.store.builders import create_database, database_url_for, drop_database

pytestmark = pytest.mark.localdb


def test_0005_applies_on_fresh_connection_after_earlier_migrations() -> None:
    if not _local_db_reachable(local_db_port()):
        pytest.skip("로컬 DB가 없다")
    migrations = load_migrations()
    retrieval = next(i for i, m in enumerate(migrations) if m.version == 5)
    name = create_database()
    try:
        url = database_url_for(name)
        with psycopg.connect(url, autocommit=True) as conn:
            assert apply_migrations(conn, migrations[:retrieval], is_local=True, out=io.StringIO()) == 0
        with psycopg.connect(url, autocommit=True) as conn:  # 라이브러리가 로드되지 않은 새 연결
            out = io.StringIO()
            assert apply_migrations(conn, migrations, is_local=True, out=out) == 0, out.getvalue()
    finally:
        drop_database(name)
