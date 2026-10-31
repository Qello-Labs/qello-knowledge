"""`qk-dev eval` 명령(QK-EVL-001 contracts/cli.md, tasks T011·T029·T034).

DB·네트워크에 닿지 않는다. 대상·장부·제공자·`git` 조회는 주입한다.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from qello_knowledge.devtools import db
from qello_knowledge.devtools.eval_cli import run_check
from qello_knowledge.ports.evaluation import TargetUnavailable
from tests.unit.evaluation.fakes import GOLDEN, IDENTIFIERS, FakeEvalTarget, document, question_set_file
from tests.unit.synthetic_secrets import SYNTHETIC

GOLDEN_TEXT = GOLDEN.read_text(encoding="utf-8")
SECRET = SYNTHETIC["github-classic"]


def _texts(path: Path) -> list[str]:
    import tomllib

    data = tomllib.loads(path.read_text(encoding="utf-8"))
    out = []
    for q in data["question"]:
        out.append(q["text"])
        out += [q.get("facts", "")] + list(q.get("label_terms", []))
    return [t for t in out if t]


def _golden(tmp_path: Path, text: str = GOLDEN_TEXT) -> Path:
    return question_set_file(tmp_path, "fixture-golden", 1, text)


# --- check (contracts/cli.md 1절) ---


def test_check_valid_set_exits_0_with_counts(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = _golden(tmp_path)
    assert db.main(["eval", "check", str(path), "--json", "--env-file", str(tmp_path / "none.env")]) == 0
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert data["exit_code"] == 0 and data["ok"] is True
    assert data["counts"]["questions"] == 4 and data["counts"]["pending"] == 1
    assert data["set"]["id"] == "fixture-golden" and len(data["set"]["fingerprint"]) == 64
    for text in _texts(path):
        assert text not in lines[0]


def test_check_invalid_set_exits_1_without_text(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    text = GOLDEN_TEXT.replace('text = "다음 회식은 어디서 해?"', f'text = "토큰 {SECRET} 은 어디에 둬?"')
    text = text.replace('id = "g04"', 'id = "g01"')
    path = _golden(tmp_path, text)
    for extra in (["--json"], []):
        assert db.main(["eval", "check", str(path), *extra, "--env-file", str(tmp_path / "none.env")]) == 1
        output = capsys.readouterr().out
        assert SECRET not in output and "어디에 둬" not in output and "두 번까지" not in output
        assert "text_secret" in output and "question_id_duplicate" in output


def test_check_missing_file_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert db.main(["eval", "check", str(tmp_path / "nope.toml"), "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["error"] == "set_not_found"


@pytest.mark.parametrize("name", ["postgres", "qk_test_x"])
def test_check_target_must_be_eval_database(tmp_path: Path, name: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert db.main(["eval", "check", str(_golden(tmp_path)), "--target", name, "--json"]) == 2
    assert json.loads(capsys.readouterr().out)["error"] == "target_not_eval"


def test_check_target_warnings_keep_exit_0(tmp_path: Path) -> None:
    out = io.StringIO()
    target = FakeEvalTarget(docs=(document("docs/A.md"),))
    code = run_check(
        _golden(tmp_path), target="qk_eval_x", as_json=True, source_env={}, target_factory=lambda *_: target, out=out
    )
    data = json.loads(out.getvalue())
    assert code == 0 and {w["question_id"] for w in data["warnings"]} == {"g02", "g04"}


def test_check_unreachable_target_exits_2(tmp_path: Path) -> None:
    out = io.StringIO()
    target = FakeEvalTarget(fail=TargetUnavailable("연결할 수 없다"))
    code = run_check(
        _golden(tmp_path), target="qk_eval_x", as_json=True, source_env={}, target_factory=lambda *_: target, out=out
    )
    assert code == 2 and json.loads(out.getvalue())["error"] == "target_unreachable"


def test_check_text_output_for_identifier_set(tmp_path: Path) -> None:
    path = question_set_file(tmp_path, "fixture-identifiers", 1, IDENTIFIERS.read_text(encoding="utf-8"))
    out = io.StringIO()
    assert run_check(path, target=None, as_json=False, source_env={}, out=out) == 0
    text = out.getvalue()
    assert "통과" in text and "fixture-identifiers" in text
    for value in _texts(path):
        assert value not in text


# --- run (contracts/cli.md 2절) ---

import argparse  # noqa: E402

from qello_knowledge.devtools.eval_cli import run_eval  # noqa: E402
from qello_knowledge.domain.embedding import BudgetSettings  # noqa: E402
from qello_knowledge.embedding.fake import FakeEmbeddingProvider  # noqa: E402
from qello_knowledge.embedding.service import EmbeddingService  # noqa: E402
from qello_knowledge.evaluation.records import read_record  # noqa: E402
from qello_knowledge.ports.evaluation import LedgerUnavailable  # noqa: E402
from tests.unit.evaluation.fakes import FakeDayUsageReader, description, usage  # noqa: E402
from tests.unit.fakes import InMemoryUsageLedger, MemoryEmbeddingStore, valid_environ  # noqa: E402
from tests.unit.retrieval.fakes import FakeRetrievalStore, keyword_result, no_block, vector_result  # noqa: E402

LEDGER_ENV = "QK_TEST_LEDGER_URL"
REMOTE_LEDGER = "host=ledger.invalid port=5432 dbname=qk user=reader"  # 운영 판정에만 쓰고 연결하지 않는다
DOCS = (document("docs/A.md", "https://example.invalid/doc-1"), document("docs/B.md", "https://example.invalid/doc-2"))


def _args(*argv: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    db._add_eval_parsers(parser.add_subparsers(dest="group"))
    return parser.parse_args(["eval", "run", *argv])


class _Harness:
    def __init__(self, *, ledger=None, provider=None, targets=None) -> None:
        self.ledger = ledger or FakeDayUsageReader(usage(day_total=100.0))
        self.provider = provider or FakeEmbeddingProvider()
        self.targets = targets or {}
        self.opened: list[str] = []
        self.ledger_urls: list[str] = []

    def target(self, name, env):
        self.opened.append(name)
        if name not in self.targets:
            store = FakeRetrievalStore(vector=vector_result(1, 2), keyword=keyword_result((1, 1), (2, 1)))
            self.targets[name] = FakeEvalTarget(description(name, index_version="v1"), DOCS, store)
        return self.targets[name]

    def ledger_factory(self, url, query_reserve):
        self.ledger_urls.append(url)
        return self.ledger

    def service(self, counter, target, budget, policy, retry):
        return EmbeddingService(
            counter,
            MemoryEmbeddingStore(),
            InMemoryUsageLedger(budget),
            budget,
            no_block,
            retry_policy=retry,
            sleep=lambda s: None,
        )

    def run(self, args: argparse.Namespace, env: dict | None = None) -> tuple[int, dict, str]:
        out = io.StringIO()
        source = {**valid_environ(), LEDGER_ENV: REMOTE_LEDGER, **(env or {})}
        code = run_eval(
            args,
            source,
            target_factory=self.target,
            ledger_factory=self.ledger_factory,
            provider_factory=lambda source, settings: self.provider,
            service_factory=self.service,
            git_state=lambda: ("c" * 40, False),
            out=out,
        )
        text = out.getvalue()
        return code, json.loads(text), text


def _run_args(tmp_path: Path, *extra: str, out_name: str = "run.json") -> argparse.Namespace:
    return _args(
        "--set", str(_golden(tmp_path)), "--target", "qk_eval_a", "--out", str(tmp_path / out_name), "--json", *extra
    )


APPROVED = ("--ledger-url-env", LEDGER_ENV, "--allow-remote-read", "--allow-query-embedding", "--max-neurons", "1")


def test_run_completes_and_writes_record(tmp_path: Path) -> None:
    harness = _Harness()
    code, data, text = harness.run(_run_args(tmp_path, *APPROVED))
    assert code == 0 and data["complete"] is True
    record = read_record(tmp_path / "run.json")
    assert record.complete and record.conditions.usage_target == "qk_eval_a"
    assert record.conditions.code_commit == ("c" * 40, False)
    assert record.conditions.ledger.target == "remote" and record.conditions.ledger.max_neurons == 1.0
    assert record.usage.provider_calls == 2 == harness.provider.calls.__len__()
    assert {(m["target"], m["mode"]) for m in data["metrics"]} == {
        ("qk_eval_a", mode) for mode in ("vector", "hybrid", "keyword")
    }
    raw = (tmp_path / "run.json").read_text(encoding="utf-8")
    for value in _texts(_golden(tmp_path)):
        assert value not in text and value not in raw  # SC-008: 출력과 실제로 쓴 기록 모두
    assert "ledger.invalid" not in text + raw and "127.0.0.1" not in text + raw


def test_two_step_approval_preview_then_run(tmp_path: Path) -> None:
    harness = _Harness(ledger=FakeDayUsageReader(usage(day_total=1_000.0, query_reserve=3_000)))
    code, data, _ = harness.run(_run_args(tmp_path, "--ledger-url-env", LEDGER_ENV, "--allow-remote-read"))
    assert code == 4 and data["error"] == "approval_missing"
    preview = data["preview"]
    assert preview["questions"] == 2 and preview["max_calls"] == 4 and preview["estimated_neurons"] > 0
    assert preview["usage_day"] == "2026-10-31" and preview["day_total"] == 1_000.0
    assert preview["remaining"] == 9_000.0 and preview["query_reserve"] == 3_000
    assert harness.provider.calls == [] and not (tmp_path / "run.json").exists()
    limit = str(preview["estimated_neurons"])
    code, data, _ = harness.run(
        _run_args(
            tmp_path,
            "--ledger-url-env",
            LEDGER_ENV,
            "--allow-remote-read",
            "--allow-query-embedding",
            "--max-neurons",
            limit,
        )
    )
    assert code == 0 and len(harness.provider.calls) == 2


@pytest.mark.parametrize(
    ("extra", "env", "ledger", "code", "error"),
    [
        (("--ledger-url-env", LEDGER_ENV), {}, None, 3, "remote_read_not_allowed"),
        (APPROVED, {LEDGER_ENV: "host=127.0.0.1 port=54322 dbname=postgres"}, None, 4, "ledger_not_production"),
        (APPROVED, {LEDGER_ENV: "host=ledger.invalid dbname=qk_eval_a"}, None, 4, "ledger_not_production"),
        (APPROVED, {LEDGER_ENV: ""}, None, 4, "ledger_unreadable"),
        (APPROVED, {}, FakeDayUsageReader(LedgerUnavailable("x")), 4, "ledger_unreadable"),
        (APPROVED, {}, FakeDayUsageReader(usage(day_total=9_999.99999)), 4, "over_remaining"),
        (APPROVED[:-1] + ("0",), {}, None, 4, "over_max_neurons"),
    ],
    ids=["no_remote_read", "local_ledger", "target_ledger", "empty_ledger", "ledger_fail", "remaining", "max_neurons"],
)
def test_cost_gate_blocks_without_embedding(tmp_path: Path, extra, env, ledger, code: int, error: str) -> None:
    harness = _Harness(ledger=ledger)
    got, data, _ = harness.run(_run_args(tmp_path, *extra), env)
    assert (got, data["error"]) == (code, error)
    assert harness.provider.calls == [] and not (tmp_path / "run.json").exists()
    if error in ("remote_read_not_allowed", "ledger_not_production"):
        assert harness.ledger.reads == 0


@pytest.mark.parametrize(
    ("extra", "error"),
    [
        (("--ledger-url-env", LEDGER_ENV, "--allow-remote-read", "--allow-query-embedding"), "max_neurons_required"),
        (APPROVED + ("--usage-target", "qk_eval_b"), "usage_target_not_in_targets"),
        (("--allow-remote-read",), "ledger_url_env_required"),
        (APPROVED + ("--candidates", "0"), "settings_out_of_range"),
    ],
)
def test_argument_errors_exit_2(tmp_path: Path, extra, error: str) -> None:
    harness = _Harness()
    code, data, _ = harness.run(_run_args(tmp_path, *extra))
    assert (code, data["error"]) == (2, error) and harness.opened == []


def test_existing_record_path_exits_2(tmp_path: Path) -> None:
    (tmp_path / "run.json").write_text("{}", encoding="utf-8")
    code, data, _ = _Harness().run(_run_args(tmp_path, *APPROVED))
    assert (code, data["error"]) == (2, "out_exists")


def test_precheck_failures_exit_1_without_ledger(tmp_path: Path) -> None:
    broken = FakeEvalTarget(description("qk_eval_a", tokenizer=None), DOCS)
    harness = _Harness(targets={"qk_eval_a": broken})
    code, data, _ = harness.run(_run_args(tmp_path, *APPROVED))
    assert (code, data["error"], data["target"]) == (1, "tokenizer_unreadable", "qk_eval_a")
    assert harness.ledger.reads == 0 and harness.provider.calls == []


def test_non_eval_target_exits_1_without_opening(tmp_path: Path) -> None:
    harness = _Harness()
    args = _args(
        "--set",
        str(_golden(tmp_path)),
        "--target",
        "postgres",
        "--out",
        str(tmp_path / "r.json"),
        "--json",
        "--mode",
        "keyword",
    )
    code, data, _ = harness.run(args)
    assert (code, data["error"]) == (1, "target_not_eval") and harness.opened == []


def test_invalid_set_exits_1(tmp_path: Path) -> None:
    path = _golden(tmp_path, GOLDEN_TEXT.replace('type = "no_answer"', 'type = "unknown"'))
    args = _args(
        "--set", str(path), "--target", "qk_eval_a", "--out", str(tmp_path / "r.json"), "--json", "--mode", "keyword"
    )
    harness = _Harness()
    code, data, _ = harness.run(args)
    assert (code, data["error"]) == (1, "set_invalid") and harness.opened == []


def test_keyword_only_needs_no_ledger(tmp_path: Path) -> None:
    harness = _Harness()
    code, data, _ = harness.run(_run_args(tmp_path, "--mode", "keyword"))
    assert code == 0 and harness.ledger.reads == 0 and harness.provider.calls == []
    record = read_record(tmp_path / "run.json")
    assert record.conditions.ledger.target == "none" and record.conditions.modes == ("keyword",)
    assert record.conditions.usage_target is None  # 사용량을 기록하지 않았다


def test_stop_writes_incomplete_record_and_exits_5(tmp_path: Path) -> None:
    from qello_knowledge.domain.embedding import ProviderFailureKind
    from qello_knowledge.ports.embedder import ProviderFailure

    quota = ProviderFailure(ProviderFailureKind.PROVIDER_QUOTA)
    harness = _Harness(provider=FakeEmbeddingProvider(fail_calls={2: quota}))
    code, data, _ = harness.run(_run_args(tmp_path, *APPROVED))
    assert code == 5 and data["stop_reason"] == "provider_quota"
    record = read_record(tmp_path / "run.json")
    assert not record.complete and {r.question for r in record.results} == {"g01"}


def test_database_url_is_never_a_target(tmp_path: Path) -> None:
    harness = _Harness()
    production = "postgres" + "ql://reader@db.invalid:5432/prod"  # 설정 점검은 형식만 본다. 실행은 이 값을 쓰지 않는다
    code, _, _ = harness.run(_run_args(tmp_path, "--mode", "keyword"), {"DATABASE_URL": production})
    assert code == 0 and harness.opened == ["qk_eval_a"]


def test_budget_settings_feed_the_remaining_amount(tmp_path: Path) -> None:
    harness = _Harness(ledger=FakeDayUsageReader(usage(day_total=0.0)))
    env = {"QK_EMBED_DAILY_ALLOWANCE": "8000", "QK_EMBED_INDEX_BUDGET": "4000", "QK_EMBED_QUERY_RESERVE": "2000"}
    code, data, _ = harness.run(_run_args(tmp_path, "--ledger-url-env", LEDGER_ENV, "--allow-remote-read"), env)
    assert code == 4 and data["preview"]["remaining"] == 8_000.0
    assert BudgetSettings(8000, 4000, 2000).within_allowance


# --- tables (contracts/cli.md 3절) ---

from qello_knowledge.devtools.eval_cli import run_tables  # noqa: E402
from qello_knowledge.evaluation.records import write_record  # noqa: E402
from tests.unit.evaluation.fakes import question_record, result, run_record  # noqa: E402


def _tables_args(*argv: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    db._add_eval_parsers(parser.add_subparsers(dest="group"))
    return parser.parse_args(["eval", "tables", *argv])


def _two_target_record(**conditions):
    targets = (("qk_eval_a", "A"), ("qk_eval_b", "B"))
    results = [
        result("q1", target=t, mode=m, rank=1, count=2, top=(True,))
        for t, _ in targets
        for m in ("vector", "hybrid", "keyword")
    ]
    return run_record([question_record("q1")], results, targets=targets, **conditions)


def _tables(*argv: str) -> tuple[int, str]:
    out = io.StringIO()
    return run_tables(_tables_args(*argv), out=out), out.getvalue()


def test_tables_prints_markdown(tmp_path: Path) -> None:
    write_record(_two_target_record(), tmp_path / "run.json")
    code, text = _tables("--run", str(tmp_path / "run.json"), "--breakdown", "identifier_form")
    assert code == 0 and "## 비교(공통 질문 집합)" in text and "### identifier_form" in text


def test_tables_target_filter_drops_comparison(tmp_path: Path) -> None:
    write_record(_two_target_record(), tmp_path / "run.json")
    code, text = _tables("--run", str(tmp_path / "run.json"), "--target", "qk_eval_b")
    assert code == 0 and "qk_eval_a" not in text and "## 비교" not in text


def test_tables_condition_mismatch_exits_1(tmp_path: Path) -> None:
    write_record(_two_target_record(), tmp_path / "a.json")
    write_record(_two_target_record(run_id="evl-20261031T100000Z-0000beef", rrf_k=30), tmp_path / "b.json")
    code, text = _tables("--run", str(tmp_path / "a.json"), "--run", str(tmp_path / "b.json"), "--json")
    data = json.loads(text)
    assert code == 1 and data["error"] == "condition_mismatch"
    assert data["mismatches"] == [
        {
            "item": "rrf_k",
            "values": [
                {"run_id": "evl-20261031T090000Z-0000abcd", "value": 60},
                {"run_id": "evl-20261031T100000Z-0000beef", "value": 30},
            ],
        }
    ]


def test_tables_incomplete_record_exits_1(tmp_path: Path) -> None:
    write_record(_two_target_record(complete=False), tmp_path / "run.json")
    code, text = _tables("--run", str(tmp_path / "run.json"), "--json")
    assert code == 1 and json.loads(text)["error"] == "incomplete_record"


@pytest.mark.parametrize("content", ["{}", "not json", None])
def test_tables_bad_record_exits_2(tmp_path: Path, content: str | None) -> None:
    path = tmp_path / "run.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    code, text = _tables("--run", str(path), "--json")
    assert code == 2 and json.loads(text)["error"] == "record_invalid"


# --- 구현 검토 반영(2026-10-31) ---


def test_missing_out_directory_exits_2_before_opening(tmp_path: Path) -> None:
    harness = _Harness()
    args = _args(
        "--set",
        str(_golden(tmp_path)),
        "--target",
        "qk_eval_a",
        "--out",
        str(tmp_path / "missing" / "r.json"),
        "--json",
        "--mode",
        "keyword",
    )
    code, data, _ = harness.run(args)
    assert (code, data["error"]) == (2, "out_dir_missing") and harness.opened == []


def test_out_directory_is_named_by_run_id(tmp_path: Path) -> None:
    runs = tmp_path / "runs"
    runs.mkdir()
    args = _args(
        "--set", str(_golden(tmp_path)), "--target", "qk_eval_a", "--out", str(runs), "--json", "--mode", "keyword"
    )
    code, data, _ = _Harness().run(args)
    assert code == 0 and data["record"] == str(runs / f"{data['run_id']}.json")
    assert read_record(runs / f"{data['run_id']}.json").run_id == data["run_id"]


def test_write_failure_keeps_usage_in_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from qello_knowledge.devtools import eval_cli

    def broken(record, path):
        raise PermissionError("읽기 전용")

    monkeypatch.setattr(eval_cli, "write_record", broken)
    code, data, _ = _Harness().run(_run_args(tmp_path, *APPROVED))
    assert (code, data["error"]) == (2, "record_write_failed")
    assert data["run_id"].startswith("evl-") and data["usage"]["provider_calls"] == 2


def test_config_and_policy_errors_exit_2(tmp_path: Path) -> None:
    harness = _Harness()
    code, data, _ = harness.run(_run_args(tmp_path, "--mode", "keyword"), {"QK_EMBED_DAILY_ALLOWANCE": "abc"})
    assert (code, data["error"]) == (2, "config_invalid") and harness.opened == []
    bad = tmp_path / "bad_exceptions.toml"
    bad.write_text("[[exception]]\nunknown = 1\n", encoding="utf-8")
    code, data, _ = harness.run(_run_args(tmp_path, *APPROVED, "--exceptions", str(bad)))
    assert (code, data["error"]) == (2, "policy_invalid") and harness.ledger.reads == 0 and harness.provider.calls == []


@pytest.mark.parametrize(
    ("target", "reason"),
    [
        (FakeEvalTarget(description("qk_eval_a", index_version=None, index_rule="unknown"), DOCS), "no_active_index"),
        (
            FakeEvalTarget(description("qk_eval_a", index_version="v1", index_rule="unknown"), DOCS),
            "index_rule_unknown",
        ),
        (
            FakeEvalTarget(description("qk_eval_a", index_version="v1", tokenizer="TokenNgram"), DOCS),
            "tokenizer_unknown",
        ),
        (
            FakeEvalTarget(description("qk_eval_a", index_version="v1", commits={"dnd-backend-docs": "f" * 40}), DOCS),
            "commit_mismatch",
        ),
        (
            FakeEvalTarget(
                description("qk_eval_a", index_version="v1"),
                (document("docs/A.md", "https://x.invalid/1"), document("docs/B.md", "https://x.invalid/1")),
            ),
            "source_url_duplicate",
        ),
        (FakeEvalTarget(description("qk_eval_a", index_version="v1", unlocated=1), DOCS), "document_location_missing"),
    ],
)
def test_precheck_failures_read_no_ledger_and_call_no_provider(tmp_path: Path, target, reason: str) -> None:
    harness = _Harness(targets={"qk_eval_a": target})
    code, data, _ = harness.run(_run_args(tmp_path, *APPROVED))
    assert (code, data["error"]) == (1, reason)
    assert harness.ledger.reads == 0 and harness.ledger_urls == [] and harness.provider.calls == []


def test_tables_target_missing_from_one_record_exits_2(tmp_path: Path) -> None:
    write_record(_two_target_record(), tmp_path / "a.json")
    other = run_record(
        [question_record("q1")],
        [result("q1", target="qk_eval_c", rank=1, count=1, top=(True,))],
        targets=(("qk_eval_c", "C"),),
        run_id="evl-20261031T100000Z-0000beef",
        modes=("keyword",),
    )
    write_record(other, tmp_path / "b.json")
    code, text = _tables(
        "--run", str(tmp_path / "a.json"), "--run", str(tmp_path / "b.json"), "--target", "qk_eval_a", "--json"
    )
    assert code == 2 and json.loads(text)["error"] == "target_not_in_record"


def test_tables_same_run_twice_exits_2(tmp_path: Path) -> None:
    write_record(_two_target_record(), tmp_path / "a.json")
    code, text = _tables("--run", str(tmp_path / "a.json"), "--run", str(tmp_path / "a.json"), "--json")
    assert code == 2 and json.loads(text)["error"] == "duplicate_run"


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("results", 0, "first_evidence_rank"), "1"),
        (("targets", 0, "commits"), ["abc"]),
        (("results", 0, "top5", 0, "evidence"), "yes"),
    ],
)
def test_tables_bad_record_values_exit_2(tmp_path: Path, path, value) -> None:
    from qello_knowledge.evaluation.records import record_to_json

    data = record_to_json(_two_target_record())
    node = data
    for key in path[:-1]:
        node = node[key]
    node[path[-1]] = value
    (tmp_path / "run.json").write_text(json.dumps(data), encoding="utf-8")
    code, text = _tables("--run", str(tmp_path / "run.json"), "--json")
    assert code == 2 and json.loads(text)["error"] == "record_invalid"
