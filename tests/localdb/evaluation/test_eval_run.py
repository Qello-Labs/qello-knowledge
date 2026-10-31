"""`qk-dev eval run` 로컬 DB 실행(QK-EVL-001 spec SC-004·SC-006·FR-022, tasks T030).

후보 A·B 대상을 실제 동기화 경로로 만들고 가짜 임베딩 제공자로 세 방식을 끝까지 돌린다. 장부는 가짜이고,
`--ledger-url-env`에는 로컬이 아닌 자리표시 접속 정보를 준다. 운영 판정에만 쓰고 연결하지 않는다. 네트워크 호출은 없다.
"""

from __future__ import annotations

import argparse
import io
import json
import tomllib
from pathlib import Path

import psycopg
import pytest

from qello_knowledge.adapters.postgres.eval_target import eval_target_url
from qello_knowledge.devtools import db
from qello_knowledge.devtools.eval_cli import metric_rows, run_eval
from qello_knowledge.embedding.fake import FakeEmbeddingProvider
from qello_knowledge.evaluation.metrics import metrics
from qello_knowledge.evaluation.records import read_record
from tests.localdb.evaluation.conftest import LOCAL_ENV
from tests.unit.evaluation.fakes import GOLDEN, FakeDayUsageReader, question_set_file
from tests.unit.fakes import valid_environ

pytestmark = pytest.mark.localdb

LEDGER_ENV = "QK_TEST_LEDGER_URL"


def _args(*argv: str) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    db._add_eval_parsers(parser.add_subparsers(dest="group"))
    return parser.parse_args(["eval", "run", *argv])


def _usage_rows(name: str) -> int:
    with psycopg.connect(eval_target_url(name, LOCAL_ENV), autocommit=True) as conn:
        return conn.execute("SELECT count(*) FROM qk.embedding_usage WHERE purpose = 'query'").fetchone()[0]


def _run(tmp_path: Path, set_path: Path, targets: list[str], out_name: str, provider: FakeEmbeddingProvider):
    argv = ["--set", str(set_path), "--out", str(tmp_path / out_name), "--json"]
    for name in targets:
        argv += ["--target", name]
    argv += ["--ledger-url-env", LEDGER_ENV, "--allow-remote-read", "--allow-query-embedding", "--max-neurons", "1"]
    out = io.StringIO()
    source = {**valid_environ(), LEDGER_ENV: "host=ledger.invalid port=5432 dbname=qk user=reader"}
    code = run_eval(
        _args(*argv),
        source,
        ledger_factory=lambda url, reserve: FakeDayUsageReader(),
        provider_factory=lambda source, settings: provider,
        git_state=lambda: ("c" * 40, False),
        out=out,
    )
    return code, json.loads(out.getvalue())


def test_two_runs_reproduce_keyword_ranks_and_metrics(
    tmp_path: Path, origin: str, baseline_target: str, idsplit_target: str
) -> None:
    set_path = question_set_file(tmp_path / "sets", "fixture-golden", 1, GOLDEN.read_text("utf-8"))
    with psycopg.connect(origin, autocommit=True) as conn:
        origin_before = conn.execute("SELECT count(*) FROM qk.embedding_usage").fetchone()[0]
    targets = [baseline_target, idsplit_target]
    first_provider, second_provider = FakeEmbeddingProvider(), FakeEmbeddingProvider()
    code1, out1 = _run(tmp_path, set_path, targets, "first.json", first_provider)
    code2, out2 = _run(tmp_path, set_path, targets, "second.json", second_provider)
    assert code1 == code2 == 0, (out1, out2)
    first, second = read_record(tmp_path / "first.json"), read_record(tmp_path / "second.json")
    assert first.complete and second.complete

    def keyword(record):
        return [
            (x.question, x.target, x.result_digest, x.first_evidence_rank)
            for x in record.results
            if x.mode == "keyword"
        ]

    assert keyword(first) == keyword(second) and keyword(first)
    for record, output in ((first, out1), (second, out2)):
        assert metric_rows(record, metrics(record)) == output["metrics"]  # 기록으로 다시 계산한 지표 = 출력
    searched = sum(q.metric_target for q in first.questions)
    assert first.usage.provider_calls == searched == len(first_provider.calls)  # 질문마다 한 번(SC-006)
    assert _usage_rows(baseline_target) == 2 * searched and _usage_rows(idsplit_target) == 0  # 사용량 대상에만(FR-022)
    with psycopg.connect(origin, autocommit=True) as conn:
        assert conn.execute("SELECT count(*) FROM qk.embedding_usage").fetchone()[0] == origin_before
    raw = (tmp_path / "first.json").read_text(encoding="utf-8") + (tmp_path / "second.json").read_text(encoding="utf-8")
    for question in tomllib.loads(GOLDEN.read_text("utf-8"))["question"]:
        for value in (question["text"], question.get("facts", "")):
            assert not value or value not in raw  # SC-008: 실제로 쓴 기록에 문장·핵심 사실 0번
    candidates = {t.database: t.candidate for t in first.targets}
    assert candidates == {baseline_target: "A", idsplit_target: "B"}
