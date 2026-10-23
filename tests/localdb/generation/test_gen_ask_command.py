"""`qk-index ask` 로컬 DB 시험(QK-GEN-001 tasks T049, spec US7). 임베딩·생성은 가짜이고 외부 호출이 없다."""

from __future__ import annotations

import contextlib
import io
import json

import psycopg
import pytest

from qello_knowledge.adapters.postgres.store import PostgresStore
from qello_knowledge.adapters.workers_ai.generation import GenerationHttpResult, WorkersAiGenerationProvider
from qello_knowledge.config.loader import SecretValue
from qello_knowledge.embedding.fake import FakeEmbeddingProvider, fake_vector
from qello_knowledge.indexer.ask_cli import postgres_ask
from qello_knowledge.indexer.cli import main
from tests.localdb.retrieval.builders import seed_doc

pytestmark = pytest.mark.localdb

QUESTION = "배포 승인 절차 정리"


class FakeTransport:
    """합성 Workers AI 응답(research R-01 꼴 (b))을 돌려준다."""

    def post(self, url, headers, body, timeout):
        payload = {
            "result": {
                "choices": [{"message": {"content": "배포 승인 절차 본문을 따른다 [S1]."}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 700, "completion_tokens": 20},
            },
            "success": True,
        }
        return GenerationHttpResult(200, {"cf-ai-neurons": "3.85"}, json.dumps(payload).encode())


def _run(db_url, monkeypatch, tmp_path, *args: str, real: bool = False) -> tuple[int, str]:
    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "0" * 32)

    def factory(settings, source, policy, provider_name="fake"):
        generation = WorkersAiGenerationProvider("0" * 32, SecretValue("synthetic"), FakeTransport()) if real else None
        return postgres_ask(
            settings,
            source,
            policy,
            provider_name=provider_name,
            embedding_provider=FakeEmbeddingProvider(),
            generation_provider=generation,
        )

    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = main(
            ["ask", "--env-file", str(tmp_path / ".env"), *args], ask_factory=factory, stdin=io.StringIO(QUESTION)
        )
    return code, out.getvalue()


def test_fake_provider_answers_with_sources_and_writes_no_usage(store: PostgresStore, db_url, monkeypatch, tmp_path):
    seed_doc(store, "a.md", ["배포 승인 절차 본문", "다음 절"], vector=list(fake_vector(QUESTION, 1024)))
    code, out = _run(db_url, monkeypatch, tmp_path, "--json")
    data = json.loads(out)
    assert code == 0 and data["result"]["status"] == "answered"
    assert data["result"]["citations"][0]["source_url"].endswith("/a.md")
    with psycopg.connect(db_url) as conn:
        assert conn.execute("SELECT count(*) FROM qk.generation_usage").fetchone() == (0,)
    assert QUESTION not in json.dumps(data["result"]["summary"], ensure_ascii=False)


def test_workers_ai_path_records_usage_through_postgres_ledger(store: PostgresStore, db_url, monkeypatch, tmp_path):
    seed_doc(store, "a.md", ["배포 승인 절차 본문"], vector=list(fake_vector(QUESTION, 1024)))
    code, out = _run(db_url, monkeypatch, tmp_path, "--json", "--provider", "workers-ai", real=True)
    data = json.loads(out)
    summary = data["result"]["summary"]
    assert code == 0 and data["result"]["status"] == "answered"
    assert summary["usage_today"]["generation_used"] == pytest.approx(3.85)
    assert summary["response_shape"]["parsed_as"] == "choices"
    with psycopg.connect(db_url) as conn:
        rows = conn.execute(
            "SELECT attempt, neurons, measured, outcome, prompt_version FROM qk.generation_usage"
        ).fetchall()
        dump = repr(conn.execute("SELECT * FROM qk.generation_usage").fetchall())
    assert [(r[0], float(r[1]), r[2], r[3]) for r in rows] == [(1, 3.85, True, "ok")]
    assert rows[0][4].startswith("gen-p1-")
    assert QUESTION not in dump and "배포" not in dump


def test_no_active_index_exits_1(store: PostgresStore, db_url, monkeypatch, tmp_path):
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute("UPDATE qk.index_version SET status = 'ready' WHERE status = 'active'")
    code, out = _run(db_url, monkeypatch, tmp_path)
    assert code == 1 and "retrieval_failed" in out and "no_active_index" in out
