"""`qk-index search`(QK-RET-001 contracts/cli.md 1절, spec US7·FR-025, research R-07·R-10, tasks T050).

가짜 저장소·가짜 제공자를 주입한다. 외부 호출과 DB 연결이 없다.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from qello_knowledge.domain.retrieval import RetrievalMode
from qello_knowledge.domain.store import SearchFilter, StoreUnavailable
from qello_knowledge.indexer.cli import main
from qello_knowledge.indexer.search_cli import SearchParts, query_retry_delay
from tests.unit.retrieval.fakes import (
    FakeRetrievalStore,
    document_context,
    keyword_result,
    query_embedder,
    vector_result,
)

QUESTION = "결제 취소 API 경로가 뭐야?"
LOCAL = "postgresql://placeholder@127.0.0.1:54322/db"
REMOTE = "postgresql://placeholder@remote.example.invalid/db"


class Store(FakeRetrievalStore):
    def __init__(self, **kwargs) -> None:
        super().__init__(
            vector=vector_result(1, 2),
            keyword=keyword_result((2, 3), (3, 1)),
            context=document_context({1: [1, 2, 3]}, bodies={1: "본문 하나", 2: "본문 둘", 3: "본문 셋"}),
            **kwargs,
        )
        self.closed = False

    def source_revisions(self):
        return {"dnd-backend-docs": "0123456789abcdef"}

    def close(self):
        self.closed = True


@pytest.fixture
def made(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", LOCAL)
    monkeypatch.delenv("QK_RETRIEVAL_CONTEXT_BUDGET", raising=False)
    record: dict = {}

    def factory(settings, source, policy, store=None):
        store = store or Store()
        embedder, provider, ledger = query_embedder()
        record.update(store=store, provider=provider, ledger=ledger, source=source, policy=policy)
        return SearchParts(store=store, embedder=embedder, closers=(store,))

    record["factory"] = factory
    record["env"] = ["--env-file", str(tmp_path / ".env")]
    return record


def _main(made, *args: str, question: str = QUESTION, factory=None) -> tuple[int, str]:
    out = io.StringIO()
    import contextlib

    with contextlib.redirect_stdout(out):
        code = main(
            ["search", *made["env"], *args], search_factory=factory or made["factory"], stdin=io.StringIO(question)
        )
    return code, out.getvalue()


def test_human_output_has_no_question_terms_or_bodies(made) -> None:
    code, out = _main(made)
    assert code == 0
    first = out.splitlines()[0]
    assert first.startswith("target=local mode=hybrid index_version=v1 index_rule=unknown query_rule=kw-query-v1")
    for secret in (QUESTION, "결제", "경로", "본문 하나", "본문 둘"):
        assert secret not in out
    assert "https://example.invalid/doc-2" in out and "0123456789abcdef" in out
    assert made["store"].closed


def test_json_output(made) -> None:
    code, out = _main(made, "--json")
    data = json.loads(out)
    assert code == 0 and data["status"] == "ok" and data["target"] == "local"
    assert data["summary"]["source_revisions"] == {"dnd-backend-docs": "0123456789abcdef"}
    assert data["hits"][0]["source_url"].startswith("https://example.invalid/")
    assert data["summary"]["external_calls"] == 5
    assert QUESTION not in out and "결제" not in out and "본문" not in out


def test_question_comes_only_from_stdin(made) -> None:
    with pytest.raises(SystemExit) as excinfo:
        main(["search", *made["env"], QUESTION], search_factory=made["factory"], stdin=io.StringIO(""))
    assert excinfo.value.code == 2


def test_empty_question_is_failure(made) -> None:
    code, out = _main(made, "--json", question="   ")
    assert code == 1 and json.loads(out)["status"] == "empty_question"


def test_remote_needs_allow_remote(made, monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", REMOTE)
    assert _main(made)[0] == 3
    code, out = _main(made, "--allow-remote")
    assert code == 0 and out.startswith("target=remote")


def test_options_are_passed(made) -> None:
    code, out = _main(
        made, "--json", "--mode", "keyword", "--query-rule", "kw-query-raw", "--candidates", "7",
        "--budget", "300", "--expand-top", "2", "--source-kind", "github_repo_files", "--ranks-only",
    )  # fmt: skip
    data = json.loads(out)
    assert code == 0 and data["summary"]["mode"] == RetrievalMode.KEYWORD
    store = made["store"]
    name, (terms, top_n, filters) = store.calls[0]
    assert name == "search_keyword_terms" and terms == (QUESTION,) and top_n == 7
    assert filters == SearchFilter(source_kinds=("github_repo_files",))
    assert "chunk_context" not in store.names() and data["summary"]["budget"] == 300


@pytest.mark.parametrize("args", [["--candidates", "0"], ["--budget", "8001"], ["--expand-top", "21"]])
def test_out_of_range_options_exit_2(made, args) -> None:
    assert _main(made, *args)[0] == 2


def test_budget_setting_from_environment(made, monkeypatch) -> None:
    monkeypatch.setenv("QK_RETRIEVAL_CONTEXT_BUDGET", "777")
    code, out = _main(made, "--json")
    assert code == 0 and json.loads(out)["summary"]["budget"] == 777


def test_store_unavailable_is_failure(made) -> None:
    def factory(settings, source, policy):
        return made["factory"](settings, source, policy, store=Store(fail={"search_vector": StoreUnavailable("x")}))

    code, out = _main(made, "--json", factory=factory)
    assert code == 1 and json.loads(out)["status"] == "store_unavailable"


def test_policy_is_loaded_from_sources_and_exceptions(made, tmp_path: Path) -> None:
    code, _ = _main(made, "--sources", "config/sources.toml", "--exceptions", "config/security_exceptions.toml")
    assert code == 0 and made["policy"] is not None
    bad = tmp_path / "bad.toml"
    bad.write_text("not toml [", encoding="utf-8")
    assert _main(made, "--exceptions", str(bad))[0] == 1


def test_query_retry_delay() -> None:
    assert query_retry_delay(1, None) == 0.5
    assert query_retry_delay(1, 1.0) == 1.0
    assert query_retry_delay(1, 30.0) == 2.0
