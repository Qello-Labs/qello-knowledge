"""실행 기록 스키마와 쓰기 규칙(QK-EVL-001 contracts/run-record.md, spec SC-008, research R-10, tasks T023)."""

from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path

import pytest

from qello_knowledge.evaluation.records import RecordError, new_run_id, read_record, record_to_json, write_record
from tests.unit.evaluation.fakes import GOLDEN, IDENTIFIERS, question_record, result, run_record

TOP = {"schema", "run_id", "complete", "stop_reason", "conditions", "targets", "questions", "results", "usage"}
CONDITIONS = {
    "question_set",
    "label_commits",
    "modes",
    "query_rule",
    "candidates",
    "rrf_k",
    "filters",
    "embedding_model",
    "query_vector_reuse",
    "usage_target",
    "ledger",
    "started_at",
    "finished_at",
    "code_commit",
}
NESTED = {
    "question_set": {"id", "version", "fingerprint", "confirmed"},
    "ledger": {"target", "usage_day", "day_total", "remaining", "estimated_neurons", "max_calls", "max_neurons"},
    "filters": {"source_kinds", "artifact_kinds"},
    "code_commit": {"sha", "dirty"},
}
TARGET = {
    "database",
    "candidate",
    "index_version",
    "index_rule",
    "tokenizer",
    "embedding_model",
    "dimension",
    "commits",
    "synced_at",
    "documents",
}
QUESTION = {"id", "type", "label", "origin", "identifier_form", "query_form", "evidence", "metric_target"}
RESULT = {
    "question",
    "target",
    "mode",
    "status",
    "skipped_reason",
    "omitted",
    "keyword_terms",
    "result_count",
    "first_evidence_rank",
    "top5",
    "unindexed_evidence",
    "result_digest",
}
USAGE = {"provider_calls", "neurons", "measured_neurons", "estimated_neurons"}


def _record():
    questions = [question_record("camel-01-original"), question_record("sentence-01", form="sentence")]
    results = [
        result(
            "camel-01-original",
            rank=1,
            count=2,
            top=(True, False),
            omitted=[("vector", "query_embedding_failed", "transient")],
        ),
        result("sentence-01", status="skipped"),
    ]
    return run_record(questions, results)


def test_keys_match_contract_exactly() -> None:
    data = record_to_json(_record())
    assert set(data) == TOP and set(data["conditions"]) == CONDITIONS
    for key, keys in NESTED.items():
        assert set(data["conditions"][key]) == keys, key
    assert all(set(t) == TARGET for t in data["targets"])
    assert all(set(q) == QUESTION for q in data["questions"])
    assert all(set(e) == {"source", "location"} for q in data["questions"] for e in q["evidence"])
    assert all(set(r) == RESULT for r in data["results"])
    assert all(set(o) == {"search", "reason", "detail"} for r in data["results"] for o in r["omitted"])
    assert all(set(h) == {"rank", "source", "location", "evidence"} for r in data["results"] for h in r["top5"])
    assert set(data["usage"]) == USAGE
    assert data["schema"] == "qk-evl-001-run/v1"
    assert data["questions"][1]["identifier_form"] is None  # 값이 없는 선택 필드는 null


def _texts() -> list[str]:
    out = []
    for path in (GOLDEN, IDENTIFIERS):
        for q in tomllib.loads(path.read_text("utf-8"))["question"]:
            out += [q["text"], q.get("facts", ""), *q.get("label_terms", [])]
    return [t for t in out if t]


def test_question_text_never_appears_in_written_file(tmp_path: Path) -> None:
    path = tmp_path / "run.json"
    write_record(_record(), path)
    raw = path.read_text(encoding="utf-8")
    for text in _texts():
        assert text not in raw
    assert raw == json.dumps(json.loads(raw), ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def test_write_refuses_existing_path_and_leaves_no_partial(tmp_path: Path) -> None:
    path = tmp_path / "run.json"
    write_record(_record(), path)
    with pytest.raises(FileExistsError):
        write_record(_record(), path)
    assert not (tmp_path / "run.json.partial").exists()


def test_incomplete_record_is_written_the_same_way(tmp_path: Path) -> None:
    path = tmp_path / "run.json"
    write_record(run_record([question_record("a")], [], complete=False), path)
    data = json.loads(path.read_text("utf-8"))
    assert data["complete"] is False and data["stop_reason"] == "provider_quota"


def test_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "run.json"
    record = _record()
    write_record(record, path)
    assert read_record(path) == record


@pytest.mark.parametrize("change", ["extra_top", "missing_result_key", "extra_nested", "wrong_schema"])
def test_read_rejects_schema_changes(tmp_path: Path, change: str) -> None:
    data = record_to_json(_record())
    if change == "extra_top":
        data["chunk_id"] = 1
    elif change == "missing_result_key":
        del data["results"][0]["top5"]
    elif change == "extra_nested":
        data["results"][0]["top5"][0]["text"] = "x"
    else:
        data["schema"] = "qk-evl-001-run/v0"
    path = tmp_path / "run.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(RecordError):
        read_record(path)


def test_run_id_format() -> None:
    from datetime import UTC, datetime

    run_id = new_run_id(datetime(2026, 10, 31, 9, 5, 7, tzinfo=UTC), "0a1b2c3d")
    assert run_id == "evl-20261031T090507Z-0a1b2c3d"
    assert re.fullmatch(r"evl-\d{8}T\d{6}Z-[0-9a-f]{8}", new_run_id(datetime.now(UTC)))
