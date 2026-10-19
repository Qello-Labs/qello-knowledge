"""로컬 대상 판정(QK-STO-001 FR-019의 원격 보호에 쓴다)."""

from __future__ import annotations

import pytest

from qello_knowledge.adapters.postgres.connection import is_local, target_label, with_database


@pytest.mark.parametrize(
    "url",
    [
        "",
        "postgresql://u@127.0.0.1:54322/x",
        "postgres://u@localhost:54322/x",
        "host=127.0.0.1 port=54322 dbname=x",
    ],
)
def test_local_targets(url: str) -> None:
    assert is_local({"DATABASE_URL": url})
    assert target_label({"DATABASE_URL": url}) == "local"


@pytest.mark.parametrize(
    "url",
    [
        "postgresql://u@db.example.invalid:5432/x",
        "postgresql://u@127.0.0.1:5432/x",
        "host=10.0.0.5 port=54322 dbname=x",
        "host=127.0.0.1 dbname=x",
        "not a conninfo ===",
    ],
)
def test_remote_or_unparsable_targets(url: str) -> None:
    assert not is_local({"DATABASE_URL": url})


def test_local_port_override() -> None:
    assert is_local({"DATABASE_URL": "host=127.0.0.1 port=6000", "QK_LOCAL_DB_PORT": "6000"})


def test_with_database_switches_only_dbname() -> None:
    switched = with_database("postgresql://u@127.0.0.1:54322/postgres", "qk_bench_1")
    assert "dbname=qk_bench_1" in switched
    assert "port=54322" in switched
