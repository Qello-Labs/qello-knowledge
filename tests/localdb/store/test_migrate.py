"""US3: 스키마 변경을 버전 순서대로, 다시 실행해도 안전하게 적용한다(SC-004, FR-016~019).

각 테스트는 자기 전용 `qk_test_<무작위>` 데이터베이스를 만들고 지운다. 원격 대상은 판정만 흉내 내고 연결하지 않는다.
"""

from __future__ import annotations

import io
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest

from qello_knowledge.adapters.postgres.migrate import (
    EXIT_CHECKSUM,
    EXIT_DESTRUCTIVE,
    EXIT_FAILED,
    EXIT_OK,
    EXIT_UNAVAILABLE,
    MIGRATIONS_DIR,
    apply_migrations,
    load_migrations,
    run,
)
from qello_knowledge.domain.store import StoreUnavailable
from tests.localdb.store.builders import create_database, database_url_for, drop_database

pytestmark = pytest.mark.localdb


@pytest.fixture
def empty_db() -> Iterator[str]:
    name = create_database("qk_test_mig")
    try:
        yield database_url_for(name)
    finally:
        drop_database(name)


def _apply(url: str, directory: Path, *, is_local: bool = True, allow_destructive: bool = False) -> tuple[int, str]:
    out = io.StringIO()
    with psycopg.connect(url, autocommit=True) as conn:
        code = apply_migrations(
            conn, load_migrations(directory), is_local=is_local, allow_destructive=allow_destructive, out=out
        )
    return code, out.getvalue()


def _write(directory: Path, name: str, sql: str) -> None:
    (directory / name).write_text(sql, encoding="utf-8")


def _schema(url: str) -> list[tuple]:
    with psycopg.connect(url) as conn:
        return conn.execute(
            "SELECT table_name, column_name, data_type FROM information_schema.columns"
            " WHERE table_schema = 'qk' ORDER BY 1, 2"
        ).fetchall()


def _records(url: str) -> list[tuple]:
    with psycopg.connect(url) as conn:
        return conn.execute("SELECT version, result FROM qk.schema_migration ORDER BY id").fetchall()


def test_full_apply_then_reapply_changes_nothing(empty_db: str) -> None:
    total = len(list(MIGRATIONS_DIR.glob("*.sql")))  # 마이그레이션이 늘어도 같은 검사를 한다
    code, out = _apply(empty_db, MIGRATIONS_DIR)
    assert code == EXIT_OK
    assert f"applied={total} skipped=0" in out
    schema = _schema(empty_db)
    assert {row[0] for row in schema} >= {"artifact", "chunk", "embedding", "index_version", "schema_migration"}
    with psycopg.connect(empty_db) as conn:
        applied_at = conn.execute("SELECT count(*) FROM qk.schema_migration WHERE applied_at IS NOT NULL").fetchone()
    assert applied_at == (total,)

    code, out = _apply(empty_db, MIGRATIONS_DIR)
    assert code == EXIT_OK
    assert f"applied=0 skipped={total}" in out
    assert _schema(empty_db) == schema
    assert _records(empty_db) == [(version, "success") for version in range(1, total + 1)]


def test_failed_migration_leaves_no_partial_change(empty_db: str, tmp_path: Path) -> None:
    _write(tmp_path, "0001_ok.sql", "CREATE TABLE qk.first (id int);")
    _write(tmp_path, "0002_broken.sql", "CREATE TABLE qk.second (id int);\nSELECT * FROM qk.no_such_table;")
    code, out = _apply(empty_db, tmp_path)
    assert code == EXIT_FAILED
    assert "apply 0002 broken failed" in out
    with psycopg.connect(empty_db) as conn:
        tables = {row[0] for row in conn.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'qk'")}
        error = conn.execute("SELECT error FROM qk.schema_migration WHERE result = 'failed'").fetchone()
    assert "first" in tables
    assert "second" not in tables  # 같은 마이그레이션의 앞 문장도 남지 않는다
    assert _records(empty_db) == [(1, "success"), (2, "failed")]
    assert error is not None and error[0].startswith("42P01")

    _write(tmp_path, "0002_broken.sql", "CREATE TABLE qk.second (id int);")
    code, out = _apply(empty_db, tmp_path)
    assert code == EXIT_OK
    assert "applied=1 skipped=1" in out


def test_changed_applied_migration_stops_everything(empty_db: str, tmp_path: Path) -> None:
    _write(tmp_path, "0001_ok.sql", "CREATE TABLE qk.first (id int);")
    assert _apply(empty_db, tmp_path)[0] == EXIT_OK
    _write(tmp_path, "0001_ok.sql", "CREATE TABLE qk.first (id bigint);")
    _write(tmp_path, "0002_next.sql", "CREATE TABLE qk.second (id int);")
    code, out = _apply(empty_db, tmp_path)
    assert code == EXIT_CHECKSUM
    assert "0001" in out
    assert _records(empty_db) == [(1, "success")]


def test_destructive_migration_needs_flag_on_remote(empty_db: str, tmp_path: Path) -> None:
    _write(tmp_path, "0001_ok.sql", "CREATE TABLE qk.first (id int);")
    _write(tmp_path, "0002_drop.sql", "-- qk:destructive\nDROP TABLE qk.first;")
    code, out = _apply(empty_db, tmp_path, is_local=False)
    assert code == EXIT_DESTRUCTIVE
    assert "0002 drop" in out
    assert _records(empty_db) == []  # 막히면 앞 마이그레이션도 적용하지 않는다

    assert _apply(empty_db, tmp_path, is_local=False, allow_destructive=True)[0] == EXIT_OK


def test_destructive_migration_is_allowed_locally(empty_db: str, tmp_path: Path) -> None:
    _write(tmp_path, "0001_ok.sql", "CREATE TABLE qk.first (id int);")
    _write(tmp_path, "0002_drop.sql", "-- qk:destructive\nDROP TABLE qk.first;")
    assert _apply(empty_db, tmp_path)[0] == EXIT_OK


def test_dry_run_changes_nothing(empty_db: str) -> None:
    out = io.StringIO()
    code = run({"DATABASE_URL": empty_db}, dry_run=True, out=out)
    assert code == EXIT_OK
    assert "pending 0001 initial_schema" in out.getvalue()
    assert _records(empty_db) == []


def test_output_never_contains_connection_details(empty_db: str) -> None:
    out = io.StringIO()
    run({"DATABASE_URL": empty_db}, out=out)
    text = out.getvalue()
    assert text.startswith("target=local\n")
    assert "password" not in text and "127.0.0.1" not in text


def test_unreachable_target_returns_exit_4() -> None:
    def refuse(url: str) -> psycopg.Connection:
        raise StoreUnavailable("저장소에 연결할 수 없다")

    out = io.StringIO()
    code = run({"DATABASE_URL": "postgresql://user:pw@db.example.invalid:5432/x"}, out=out, connector=refuse)
    assert code == EXIT_UNAVAILABLE
    assert out.getvalue().startswith("target=remote\n")
    assert "db.example.invalid" not in out.getvalue() and "pw" not in out.getvalue()
