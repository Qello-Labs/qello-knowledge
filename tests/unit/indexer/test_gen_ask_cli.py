"""`qk-index ask`(QK-GEN-001 tasks T047, contracts/cli.md 1~4절, spec US7·FR-027).

가짜 저장소·가짜 임베딩·가짜 생성 제공자를 주입한다. 외부 호출과 DB 연결이 없다.
"""

from __future__ import annotations

import contextlib
import io
import json
from datetime import date

import pytest

from qello_knowledge.domain.generation import AnswerUsageToday, GenerationFailure, ProviderReply
from qello_knowledge.domain.store import StoreUnavailable
from qello_knowledge.generation.fake import MemoryLedger, ScriptedProvider
from qello_knowledge.indexer.ask_cli import AskParts
from qello_knowledge.indexer.cli import main
from qello_knowledge.ports.generator import GenerationProviderFailure
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
TODAY = AnswerUsageToday(date(2026, 10, 23), 12.5, 0.4, 12.9, 300.0, 312.9, 3000, False)


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
        return {}

    def close(self):
        self.closed = True


class Reader:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.closed = False

    def today(self) -> AnswerUsageToday:
        if self.error:
            raise self.error
        return TODAY

    def close(self) -> None:
        self.closed = True


@pytest.fixture
def made(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", LOCAL)
    for name in ("QK_RETRIEVAL_CONTEXT_BUDGET", "QK_GEN_MAX_TOKENS", "QK_GEN_PROMPT_VERSION"):
        monkeypatch.delenv(name, raising=False)
    record: dict = {"script": [ProviderReply("본문 하나에 따르면 그렇다 [S1].", 100, 10, neurons=1.2)], "calls": []}

    def factory(settings, source, policy, provider_name="fake", store=None):
        store = store or record.get("store") or Store()
        embedder, _, _ = query_embedder()
        provider = ScriptedProvider(record["script"])
        reader = Reader(record.get("reader_error"))
        ledger = MemoryLedger()
        record.update(store=store, provider=provider, reader=reader, ledger=ledger)
        record["calls"].append(provider_name)
        usage_reader = reader if provider_name == "fake" else None
        return AskParts(store, embedder, provider, ledger, usage_reader, (store, reader))

    record["factory"] = factory
    record["env"] = ["--env-file", str(tmp_path / ".env")]
    return record


def _main(made, *args: str, question: str = QUESTION) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(["ask", *made["env"], *args], ask_factory=made["factory"], stdin=io.StringIO(question))
    return code, out.getvalue(), err.getvalue()


def test_human_output_fake_provider(made):
    code, out, err = _main(made)
    lines = out.splitlines()
    assert code == 0 and err == ""
    assert lines[0].startswith("대상: local | 제공자: fake | 프롬프트: gen-p1-") and lines[0].endswith("상태: answered")
    assert lines[1] == "답변:" and lines[2] == "본문 하나에 따르면 그렇다 [S1]."
    assert lines[3] == "출처:" and lines[4].startswith("[S1] ") and "https://example.invalid/" in lines[4]
    assert any(line.startswith("요약: 묶음 1/1") and "(생성 0)" in line for line in lines)
    assert any("가짜 실행은 기록하지 않음" in line and "생성 12.50" in line for line in lines)
    assert not any(line.startswith("응답 꼴") for line in lines)
    assert QUESTION not in out and "결제" not in out
    assert made["store"].closed and made["reader"].closed
    assert made["calls"] == ["fake"] and made["ledger"].records  # 메모리 장부에만 남는다


def test_json_output(made):
    code, out, _ = _main(made, "--json")
    data = json.loads(out)
    result = data["result"]
    assert code == 0 and (data["target"], data["provider"]) == ("local", "fake")
    assert result["status"] == "answered" and [c["source_id"] for c in result["citations"]] == ["S1"]
    assert result["summary"]["generation_calls"] == 0 and result["summary"]["fake_provider"] is True
    assert result["summary"]["usage_today"]["answer_total"] == 12.9
    assert QUESTION not in json.dumps(result["summary"], ensure_ascii=False)
    assert QUESTION not in json.dumps(result["retrieval"], ensure_ascii=False)


def test_workers_ai_announces_estimate_before_calling(made):
    code, out, err = _main(made, "--provider", "workers-ai", "--prompt", "gen-base")
    estimate = json.loads(err)
    assert code == 0 and made["calls"] == ["workers-ai"]
    assert estimate["model"] == "@cf/qwen/qwen3-30b-a3b-fp8" and estimate["prompt"].startswith("gen-base-")
    assert estimate["with_retry_max"] == pytest.approx(estimate["estimated_neurons"] * 2, abs=0.02)
    assert QUESTION not in err
    assert "제공자: workers-ai" in out and "(생성 2)" in out and "응답 꼴:" in out


@pytest.mark.parametrize(
    ("setup", "code"),
    [
        ({"script": [ProviderReply("제공된 자료만으로 확인할 수 없습니다.", 1, 1)]}, 0),
        ({"script": [GenerationProviderFailure(GenerationFailure.AUTH_CONFIG, billable=False)]}, 1),
        ({"store": Store(fail={"search_vector": StoreUnavailable("x")})}, 1),
    ],
)
def test_exit_codes(made, setup, code):
    made.update(setup)
    assert _main(made)[0] == code


def test_empty_stdin_is_argument_error(made):
    code, out, _ = _main(made, question="   ")
    assert code == 2 and json.loads(out)["error"] == "empty_question"


def test_question_only_from_stdin(made):
    with pytest.raises(SystemExit) as excinfo:
        main(["ask", *made["env"], QUESTION], ask_factory=made["factory"], stdin=io.StringIO(""))
    assert excinfo.value.code == 2


def test_remote_needs_allow_remote(made, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", REMOTE)
    assert _main(made)[0] == 3 and made["calls"] == []
    assert _main(made, "--allow-remote")[0] == 0


def test_settings_error_is_exit_two(made, monkeypatch):
    monkeypatch.setenv("QK_GEN_PROMPT_VERSION", "gen-x")
    code, out, _ = _main(made)
    assert code == 2 and json.loads(out)["error"] == "settings_out_of_range" and made["calls"] == []


def test_usage_reader_failure_still_prints_answer(made):
    made["reader_error"] = OSError("db down")
    code, out, _ = _main(made)
    assert code == 0 and "본문 하나에 따르면" in out and "오늘 사용량" not in out
