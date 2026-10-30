"""고정 기록에서 손으로 계산한 집계와 측정 조건."""

import json

import pytest

from qello_knowledge.adapters.postgres.query_log_admin import PostgresQueryLogAdmin
from qello_knowledge.indexer.cli import main
from tests.localdb.query.obs_db import obs_connection, seed_feedback, seed_record, seed_text
from tests.unit.query.obs_builders import QUESTIONER

pytestmark = pytest.mark.localdb


def test_fixed_report(db_url, capsys, monkeypatch):
    monkeypatch.setenv("QK_QUERY_TEXT_RETAIN_UNTIL", "2026-01-01")
    with obs_connection(db_url) as conn:
        for n in range(4):
            run = f"q-20261029T01020{n}-1234abcd"
            seed_record(
                conn,
                run_id=run,
                first_response_ms=n * 10,
                private=n % 2 == 0,
                status="answered" if n < 3 else "generation_failed",
                failure="timeout" if n == 3 else None,
                retrieval={"neurons": 1, "measured": True},
                generation={"neurons": 2, "measured": False},
                index_version="v1",
                model_id="model1",
                prompt_version="prompt1",
            )
            conn.execute("SELECT qk.query_record_delivered(%s,%s::jsonb)", (run, json.dumps({"total_ms": n * 100})))
            if n < 2:
                seed_feedback(conn, run_id=run, value="up" if n == 0 else "down")
            if n == 1:
                seed_text(conn, run_id=run)
        conn.execute("UPDATE qk.query_feedback SET rater_id=NULL WHERE value='up'")
        assert (
            main(
                [
                    "queries",
                    "report",
                    "--since",
                    "2026-10-29",
                    "--until",
                    "2026-10-29",
                    "--json",
                    "--env-file",
                    "/dev/null",
                ],
                queries_factory=lambda source: PostgresQueryLogAdmin(db_url),
            )
            == 0
        )
        out = capsys.readouterr()
        report = json.loads(out.out)
        assert report["records"] == report["sample_size"] == 4
        assert report["period"] == {"since": "2026-10-29", "until": "2026-10-29"}
        assert report["by_status"] == {"answered": 3, "generation_failed": 1}
        assert report["by_failure"] == {"timeout": 1}
        assert report["first_response_ms"] == {"p50": 15, "p95": 28.5}
        assert report["total_ms"] == {"p50": 150, "p95": 285}
        assert report["private_ratio"] == 0.5 and report["rated_ratio"] == 0.5
        assert report["feedback"] == {"up": 1, "down": 1, "anonymous": 1} and report["consented"] == 1
        assert report["neurons"] == {"measured": 4, "estimated": 8}
        assert report["index_versions"] == {"v1": 4} and report["models"] == {"model1": 4}
        assert report["prompt_versions"] == {"prompt1": 4}
        assert "Worker 서명 검사" in report["measurement_boundary"]
        assert "relay_failed" in report["relay_failures_note"] and report["warnings"]
        assert report["answer_usage_by_day"][0]["usage_day"] == "2026-10-29"
        assert QUESTIONER not in out.out and "합성 질문" not in out.out


def test_empty_report_and_invalid_dates(db_url, capsys):
    with obs_connection(db_url):

        def factory(source):
            return PostgresQueryLogAdmin(db_url)

        assert (
            main(
                ["queries", "report", "--since", "2026-10-30", "--until", "2026-10-29", "--env-file", "/dev/null"],
                queries_factory=factory,
            )
            == 2
        )
        capsys.readouterr()
        assert (
            main(
                [
                    "queries",
                    "report",
                    "--since",
                    "2026-10-29",
                    "--until",
                    "2026-10-29",
                    "--json",
                    "--env-file",
                    "/dev/null",
                ],
                queries_factory=factory,
            )
            == 0
        )
        report = json.loads(capsys.readouterr().out)
        assert report["records"] == 0 and report["rated_ratio"] == 0 and report["private_ratio"] == 0
        assert report["first_response_ms"] == {"p50": None, "p95": None}
