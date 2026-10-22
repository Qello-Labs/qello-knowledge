"""`qk-index search` 로컬 DB 시험(spec US7 수용 시나리오 1~3, tasks T052). 임베딩은 가짜 제공자다."""

from __future__ import annotations

import contextlib
import io
import json

import psycopg
import pytest

from qello_knowledge.adapters.postgres.store import PostgresStore
from qello_knowledge.embedding.fake import FakeEmbeddingProvider, fake_vector
from qello_knowledge.indexer.cli import main
from qello_knowledge.indexer.search_cli import postgres_search
from tests.localdb.retrieval.builders import seed_doc

pytestmark = pytest.mark.localdb

QUESTION = "배포 승인 절차 정리"


def _run(db_url: str, monkeypatch, tmp_path, *args: str) -> tuple[int, str]:
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "0" * 32)

    def factory(settings, source, policy):
        return postgres_search(settings, source, policy, provider=FakeEmbeddingProvider())

    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        code = main(
            ["search", "--env-file", str(tmp_path / ".env"), *args], search_factory=factory, stdin=io.StringIO(QUESTION)
        )
    return code, out.getvalue()


def test_search_shows_ranks_sources_and_summary(store: PostgresStore, db_url: str, monkeypatch, tmp_path) -> None:
    seed_doc(store, "a.md", ["배포 승인 절차 본문", "다음 절"], vector=list(fake_vector(QUESTION, 1024)))
    code, out = _run(db_url, monkeypatch, tmp_path, "--json")
    data = json.loads(out)
    assert code == 0 and data["status"] == "ok" and data["target"] == "local"
    assert data["hits"][0]["source_url"].endswith("/a.md")
    assert data["summary"]["block_count"] == 1
    assert QUESTION not in out and "본문" not in out


def test_no_active_index_exits_1(store: PostgresStore, db_url: str, monkeypatch, tmp_path) -> None:
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute("UPDATE qk.index_version SET status = 'ready' WHERE status = 'active'")
    code, out = _run(db_url, monkeypatch, tmp_path)
    assert code == 1 and "no_active_index" in out


def test_usage_record_has_no_question(store: PostgresStore, db_url: str, monkeypatch, tmp_path) -> None:
    seed_doc(store, "a.md", ["배포 승인 절차 본문"], vector=list(fake_vector(QUESTION, 1024)))
    assert _run(db_url, monkeypatch, tmp_path)[0] == 0
    with psycopg.connect(db_url, autocommit=True) as conn:
        rows = conn.execute("SELECT purpose, run_id, model_version, input_count FROM qk.embedding_usage").fetchall()
        dump = repr(conn.execute("SELECT * FROM qk.embedding_usage").fetchall())
    assert [(r[0], r[3]) for r in rows] == [("query", 1)]
    assert QUESTION not in dump and "배포" not in dump
