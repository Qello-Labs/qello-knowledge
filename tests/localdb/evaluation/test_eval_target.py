"""평가 대상 읽기(QK-EVL-001 research R-04·R-05, tasks T005).

대상은 시험마다 실제 동기화 경로로 새로 만든다(conftest). 모든 읽기는 읽기 전용 트랜잭션이다.
"""

from __future__ import annotations

import psycopg
import pytest

from qello_knowledge.adapters.postgres.eval_target import KEYWORD_INDEX, PostgresEvalTarget, eval_target_url
from qello_knowledge.adapters.postgres.store import PostgresStore
from qello_knowledge.domain.keyword_rules import INDEX_BASELINE, INDEX_IDSPLIT
from qello_knowledge.ports.evaluation import TargetUnavailable
from tests.localdb.evaluation.conftest import DOCS, LOCAL_ENV

pytestmark = pytest.mark.localdb


def _counts(url: str) -> tuple[int, int, int]:
    with psycopg.connect(url, autocommit=True) as conn:
        return conn.execute(
            "SELECT (SELECT count(*) FROM qk.embedding_usage), (SELECT count(*) FROM qk.chunk),"
            " (SELECT count(*) FROM qk.artifact)"
        ).fetchone()


def test_describe_reads_index_rule_tokenizer_and_commits(baseline_target: str) -> None:
    url = eval_target_url(baseline_target, LOCAL_ENV)
    before = _counts(url)
    with PostgresEvalTarget(baseline_target, LOCAL_ENV) as target:
        described = target.describe()
    with PostgresStore(url) as store:
        revisions = store.source_revisions()
    assert described.database == baseline_target
    assert described.index_version == "iv-4c0bc4fcc642"
    assert described.embedding_model == "@cf/baai/bge-m3" and described.dimension == 1024
    assert described.index_rule == INDEX_BASELINE
    assert described.tokenizer == "TokenBigramSplitSymbol"
    assert dict(described.commits) == revisions and revisions
    assert described.synced_at is not None
    assert described.sources == ("dnd-backend-docs",)
    assert _counts(url) == before


def test_idsplit_target_reads_idsplit_rule(idsplit_target: str) -> None:
    with PostgresEvalTarget(idsplit_target, LOCAL_ENV) as target:
        described = target.describe()
    assert described.index_rule == INDEX_IDSPLIT and described.index_version == "iv-8b7e93b22051"


def test_missing_keyword_index_reads_as_none(baseline_target: str) -> None:
    url = eval_target_url(baseline_target, LOCAL_ENV)
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute(f"DROP INDEX qk.{KEYWORD_INDEX}")
    with PostgresEvalTarget(baseline_target, LOCAL_ENV) as target:
        assert target.describe().tokenizer is None


def test_no_active_index_reads_as_none(baseline_target: str) -> None:
    url = eval_target_url(baseline_target, LOCAL_ENV)
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("UPDATE qk.index_version SET status = 'archived' WHERE status = 'active'")
    with PostgresEvalTarget(baseline_target, LOCAL_ENV) as target:
        described = target.describe()
        documents = target.documents()
    assert described.index_version is None and described.embedding_model is None and described.dimension is None
    assert described.index_rule == "unknown"
    assert documents == ()


def test_documents_lists_only_visible_documents(baseline_target: str) -> None:
    url = eval_target_url(baseline_target, LOCAL_ENV)
    with PostgresEvalTarget(baseline_target, LOCAL_ENV) as target:
        documents = target.documents()
    assert {(d.source, d.location) for d in documents} == {("dnd-backend-docs", f"docs/{key}.md") for key in DOCS}
    assert len({d.source_url for d in documents}) == len(documents)
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("UPDATE qk.artifact SET access_scope = NULL WHERE location = 'docs/B.md'")
    with PostgresEvalTarget(baseline_target, LOCAL_ENV) as target:
        assert {d.location for d in target.documents()} == {"docs/A.md"}


def test_documents_without_location_are_counted(baseline_target: str) -> None:
    url = eval_target_url(baseline_target, LOCAL_ENV)
    with PostgresEvalTarget(baseline_target, LOCAL_ENV) as target:
        assert target.describe().unlocated_documents == 0
    with psycopg.connect(url, autocommit=True) as conn:
        conn.execute("UPDATE qk.artifact SET location = NULL WHERE location = 'docs/B.md'")
    with PostgresEvalTarget(baseline_target, LOCAL_ENV) as target:
        assert target.describe().unlocated_documents == 1
        assert {d.location for d in target.documents()} == {"docs/A.md"}


def test_visible_chunk_texts_follow_visibility(baseline_target: str) -> None:
    with PostgresEvalTarget(baseline_target, LOCAL_ENV) as target:
        texts = list(target.visible_chunk_texts())
    assert {location for _, location, _ in texts} == {"docs/A.md", "docs/B.md"}
    assert any("retryPayment" in body for _, _, body in texts)


def test_reads_run_in_read_only_transactions(baseline_target: str) -> None:
    from qello_knowledge.adapters.postgres import eval_target

    url = eval_target_url(baseline_target, LOCAL_ENV)
    with pytest.raises(TargetUnavailable, match="25006"):  # read_only_sql_transaction
        with eval_target._read_only(url, TargetUnavailable) as conn:
            conn.execute("DELETE FROM qk.embedding_usage")


@pytest.mark.parametrize("name", ["postgres", "qk_test_abc", "eval_x", ""])
def test_rejects_non_eval_database_names(name: str) -> None:
    with pytest.raises(ValueError):
        PostgresEvalTarget(name, LOCAL_ENV)


def test_ignores_database_url(baseline_target: str) -> None:
    env = {"DATABASE_URL": "host=db.invalid port=5432 dbname=production user=x"}
    url = eval_target_url(baseline_target, env)
    assert "db.invalid" not in url and "production" not in url
    with PostgresEvalTarget(baseline_target, env) as target:
        assert target.describe().database == baseline_target


def test_missing_database_is_unavailable() -> None:
    with PostgresEvalTarget("qk_eval_missing_000000000000", LOCAL_ENV) as target:
        with pytest.raises(TargetUnavailable):
            target.describe()
