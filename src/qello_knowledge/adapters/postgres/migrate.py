"""`qk-migrate`: 버전이 붙은 SQL 마이그레이션을 순서대로 적용한다(QK-STO-001 FR-016~020, research R-08).

- 성공 기록이 있는 버전은 건너뛴다. 두 번째 실행은 `applied=0`이다.
- 적용한 파일의 체크섬이 바뀌었으면 아무것도 적용하지 않고 멈춘다.
- 마이그레이션 하나는 트랜잭션 하나다. 실패하면 되돌리고 실패 기록만 남긴다.
- 첫 줄이 `-- qk:destructive`인 파일은 로컬이 아닌 대상에 `--allow-destructive` 없이 적용하지 않는다.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TextIO

import psycopg

from qello_knowledge.adapters.postgres.connection import connect, database_url, target_label
from qello_knowledge.config.loader import merge_sources, read_env_file
from qello_knowledge.domain.store import StoreUnavailable

MIGRATIONS_DIR = Path(__file__).with_name("migrations")
FILE_PATTERN = re.compile(r"(?P<version>\d{4})_(?P<description>[a-z0-9_]+)\.sql")
DESTRUCTIVE_MARK = "-- qk:destructive"
LOCK_KEY = 7_340_001  # qk-migrate 전용 advisory lock 키

EXIT_OK = 0
EXIT_FAILED = 1
EXIT_CHECKSUM = 2
EXIT_DESTRUCTIVE = 3
EXIT_UNAVAILABLE = 4

BOOTSTRAP = """
CREATE SCHEMA IF NOT EXISTS qk;
CREATE TABLE IF NOT EXISTS qk.schema_migration (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    version int NOT NULL,
    description text NOT NULL,
    checksum text NOT NULL,
    destructive boolean NOT NULL,
    applied_at timestamptz NOT NULL DEFAULT now(),
    result text NOT NULL CHECK (result IN ('success', 'failed')),
    error text
);
CREATE UNIQUE INDEX IF NOT EXISTS schema_migration_one_success
    ON qk.schema_migration (version) WHERE result = 'success';
"""


class MigrationFileError(ValueError):
    """마이그레이션 파일 이름이 형식에 맞지 않거나 번호가 겹친다."""


@dataclass(frozen=True)
class Migration:
    version: int
    description: str
    sql: str
    checksum: str
    destructive: bool

    @property
    def label(self) -> str:
        return f"{self.version:04d} {self.description}"


def parse_migration(name: str, sql: str) -> Migration:
    match = FILE_PATTERN.fullmatch(name)
    if match is None:
        raise MigrationFileError(f"파일 이름 형식이 아니다(NNNN_<설명>.sql): {name}")
    first_line = sql.lstrip().splitlines()[0].strip() if sql.strip() else ""
    return Migration(
        version=int(match["version"]),
        description=match["description"],
        sql=sql,
        checksum=hashlib.sha256(sql.encode("utf-8")).hexdigest(),
        destructive=first_line == DESTRUCTIVE_MARK,
    )


def load_migrations(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    migrations = [parse_migration(path.name, path.read_text(encoding="utf-8")) for path in directory.glob("*.sql")]
    migrations.sort(key=lambda m: m.version)
    versions = [m.version for m in migrations]
    duplicates = sorted({v for v in versions if versions.count(v) > 1})
    if duplicates:
        raise MigrationFileError(f"마이그레이션 번호가 겹친다: {', '.join(f'{v:04d}' for v in duplicates)}")
    return migrations


def _error_summary(exc: psycopg.Error) -> str:
    """오류 분류와 기본 메시지만 남긴다. DETAIL에는 행 값이 들어갈 수 있어 뺀다."""
    diag = exc.diag
    primary = diag.message_primary or type(exc).__name__
    return f"{diag.sqlstate or '-'} {primary}"


def apply_migrations(
    conn: psycopg.Connection,
    migrations: Sequence[Migration],
    *,
    is_local: bool,
    allow_destructive: bool = False,
    dry_run: bool = False,
    out: TextIO = sys.stdout,
) -> int:
    """`conn`은 autocommit 연결이어야 한다. 종료 코드를 돌려준다(contracts/cli.md)."""
    conn.execute("SELECT pg_advisory_lock(%s)", (LOCK_KEY,))
    try:
        conn.execute(BOOTSTRAP)
        applied = {
            version: checksum
            for version, checksum in conn.execute(
                "SELECT version, checksum FROM qk.schema_migration WHERE result = 'success'"
            ).fetchall()
        }
        known = {m.version: m for m in migrations}
        changed = [
            f"{v:04d}" for v, checksum in sorted(applied.items()) if v not in known or known[v].checksum != checksum
        ]
        if changed:
            print(f"적용한 마이그레이션의 내용이 바뀌었거나 파일이 없다: {', '.join(changed)}", file=out)
            return EXIT_CHECKSUM

        pending = [m for m in migrations if m.version not in applied]
        skipped = len(migrations) - len(pending)
        blocked = [m for m in pending if m.destructive and not is_local and not allow_destructive]
        if blocked:
            labels = ", ".join(m.label for m in blocked)
            print(f"파괴적 마이그레이션은 사람 확인 뒤 --allow-destructive로만 적용한다: {labels}", file=out)
            return EXIT_DESTRUCTIVE
        if dry_run:
            for m in pending:
                print(f"pending {m.label}{' destructive' if m.destructive else ''}", file=out)
            print(f"applied=0 skipped={skipped} pending={len(pending)}", file=out)
            return EXIT_OK

        count = 0
        for m in pending:
            try:
                with conn.transaction():
                    conn.execute(m.sql)
                    conn.execute(
                        "INSERT INTO qk.schema_migration (version, description, checksum, destructive, result)"
                        " VALUES (%s, %s, %s, %s, 'success')",
                        (m.version, m.description, m.checksum, m.destructive),
                    )
            except psycopg.Error as exc:
                conn.execute(
                    "INSERT INTO qk.schema_migration (version, description, checksum, destructive, result, error)"
                    " VALUES (%s, %s, %s, %s, 'failed', %s)",
                    (m.version, m.description, m.checksum, m.destructive, _error_summary(exc)),
                )
                print(f"apply {m.label} failed: {_error_summary(exc)}", file=out)
                print(f"applied={count} skipped={skipped}", file=out)
                return EXIT_FAILED
            count += 1
            print(f"apply {m.label} ok", file=out)
        print(f"applied={count} skipped={skipped}", file=out)
        return EXIT_OK
    finally:
        conn.execute("SELECT pg_advisory_unlock(%s)", (LOCK_KEY,))


def run(
    source: dict[str, str],
    *,
    directory: Path = MIGRATIONS_DIR,
    allow_destructive: bool = False,
    dry_run: bool = False,
    out: TextIO = sys.stdout,
    connector: Callable[[str], psycopg.Connection] = connect,
) -> int:
    label = target_label(source)
    print(f"target={label}", file=out)
    try:
        migrations = load_migrations(directory)
    except MigrationFileError as exc:
        print(str(exc), file=out)
        return EXIT_FAILED
    try:
        conn = connector(database_url(source))
    except StoreUnavailable as exc:
        print(str(exc), file=out)
        return EXIT_UNAVAILABLE
    with conn:
        return apply_migrations(
            conn,
            migrations,
            is_local=label == "local",
            allow_destructive=allow_destructive,
            dry_run=dry_run,
            out=out,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="qk-migrate", description="저장소 스키마 마이그레이션")
    parser.add_argument("--dry-run", action="store_true", help="적용할 목록만 출력한다")
    parser.add_argument(
        "--allow-destructive", action="store_true", help="로컬이 아닌 대상에 파괴적 마이그레이션 적용을 허용한다"
    )
    parser.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args(argv)
    source = merge_sources(os.environ, read_env_file(args.env_file))
    return run(dict(source), allow_destructive=args.allow_destructive, dry_run=args.dry_run)


if __name__ == "__main__":
    raise SystemExit(main())
