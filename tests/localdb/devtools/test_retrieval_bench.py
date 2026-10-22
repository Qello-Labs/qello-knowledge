"""`qk-dev store bench --retrieval` 동작 확인(QK-RET-001 tasks T053). 작은 합성 규모로만 돈다."""

from __future__ import annotations

import io

import pytest

from qello_knowledge.devtools.bench import run_retrieval_bench
from tests.conftest import _local_db_reachable, local_db_port
from tests.localdb.store.builders import admin_url

pytestmark = pytest.mark.localdb


def test_small_run_reports_conditions_and_percentiles() -> None:
    if not _local_db_reachable(local_db_port()):
        pytest.skip("로컬 DB가 없다")
    out = io.StringIO()
    code = run_retrieval_bench({"DATABASE_URL": admin_url()}, text_bytes=20_000, questions=3, repeat=1, out=out)
    text = out.getvalue()
    assert code == 0
    for key in ("conditions:", "data:", "retrieve_with_context_ms:", "pure_processing_ms:"):
        assert key in text


def test_refuses_remote_target() -> None:
    out = io.StringIO()
    assert run_retrieval_bench({"DATABASE_URL": "postgresql://placeholder@remote.example.invalid/db"}, out=out) == 1
