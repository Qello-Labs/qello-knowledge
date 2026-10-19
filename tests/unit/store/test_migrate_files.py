"""마이그레이션 파일 읽기(US3, FR-016·019)."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from qello_knowledge.adapters.postgres.migrate import (
    MIGRATIONS_DIR,
    MigrationFileError,
    load_migrations,
    parse_migration,
)


def test_parses_version_description_and_checksum() -> None:
    sql = "CREATE TABLE qk.x (id int);\n"
    migration = parse_migration("0003_add_x.sql", sql)
    assert (migration.version, migration.description) == (3, "add_x")
    assert migration.checksum == hashlib.sha256(sql.encode()).hexdigest()
    assert migration.destructive is False
    assert migration.label == "0003 add_x"


def test_destructive_mark_on_first_line() -> None:
    assert parse_migration("0004_drop_x.sql", "-- qk:destructive\nDROP TABLE qk.x;\n").destructive is True
    assert parse_migration("0004_drop_x.sql", "\n  -- qk:destructive\nDROP TABLE qk.x;\n").destructive is True
    assert parse_migration("0004_drop_x.sql", "SELECT 1;\n-- qk:destructive\n").destructive is False


@pytest.mark.parametrize("name", ["1_init.sql", "0001-init.sql", "0001_Init.sql", "0001_init.txt", "init.sql"])
def test_bad_file_name_is_rejected(name: str) -> None:
    with pytest.raises(MigrationFileError):
        parse_migration(name, "SELECT 1;")


def test_duplicate_versions_are_rejected(tmp_path: Path) -> None:
    (tmp_path / "0001_a.sql").write_text("SELECT 1;", encoding="utf-8")
    (tmp_path / "0001_b.sql").write_text("SELECT 2;", encoding="utf-8")
    with pytest.raises(MigrationFileError, match="0001"):
        load_migrations(tmp_path)


def test_packaged_migrations_load_in_order() -> None:
    migrations = load_migrations(MIGRATIONS_DIR)
    assert [m.version for m in migrations] == sorted(m.version for m in migrations)
    assert migrations[0].description == "initial_schema"
    assert not any(m.destructive for m in migrations)
