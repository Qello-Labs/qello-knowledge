"""게이트 기록 형식(QK-STO-002 contracts/gate-record.md 1~3절, SC-007, FR-018)."""

import json
from datetime import UTC, datetime

import pytest

from qello_knowledge.gate.judge import judge
from qello_knowledge.gate.record import TOP_KEYS, outcome_json, read_gate_record, write_gate_record
from tests.unit.gate.gate_builders import golden, policy, request

NOW = datetime(2026, 11, 5, 1, 2, 3, tzinfo=UTC)
SET_KEYS = {
    "id",
    "version",
    "judged",
    "excluded",
    "metrics",
    "guardrails",
    "new_failures",
    "regressions",
    "improvements",
}
METRIC_KEYS = {"baseline", "candidate", "diff", "baseline_fraction", "candidate_fraction", "max_drop", "ok"}
TARGET_KEYS = {"target", "index_version", "expected_index_version", "embedding_model", "tokenizer", "index_rule"}
SYNTHETIC_TEXT = "합성 질문 문장은 기록에 나오면 안 된다"
SYNTHETIC_BODY = "synthetic chunk body must not leak"


def _record(**kw):
    req = request(golden([1, 2, 6, None], [1, 3, 4, None]), pol=policy(min_judged=4, drop_mrr="0.05", **kw))
    return outcome_json(judge(req), req, gate_id="gate-20261105T010203Z-0000abcd", judged_at=NOW)


def test_keys_match_contract():
    data = _record()
    assert set(data) == TOP_KEYS
    assert set(data["policy"]) == {"id", "version", "path", "sha256", "merge_commit", "main_ref"}
    assert set(data["baseline"]) == TARGET_KEYS == set(data["candidate"])
    assert all(set(r) == {"run_id", "path", "sha256", "code_commit", "set"} for r in data["runs"])
    (s,) = data["sets"]
    assert set(s) == SET_KEYS and set(s["metrics"]) == {"recall_at_5", "mrr"}
    assert set(s["metrics"]["mrr"]) == METRIC_KEYS
    assert (
        s["metrics"]["mrr"]["baseline_fraction"] == "1.6667/4" and s["metrics"]["recall_at_5"]["candidate"] == "0.7500"
    )
    assert data["judged_at"] == "2026-11-05T01:02:03Z" and data["verdict"] == "pass"
    assert data["limits"] == ["evaluates the index version settings on a local eval target, not production data"]


def test_write_sorted_two_space_and_refuse_existing(tmp_path):
    path = tmp_path / "gate.json"
    digest = write_gate_record(_record(), path)
    text = path.read_text(encoding="utf-8")
    assert text.startswith('{\n  "baseline"') and text.endswith("}\n")
    assert list(json.loads(text)) == sorted(json.loads(text))
    data, read_digest = read_gate_record(path)
    assert read_digest == digest and data["gate_id"] == "gate-20261105T010203Z-0000abcd"
    with pytest.raises(FileExistsError):
        write_gate_record(_record(), path)
    assert not (tmp_path / "gate.json.partial").exists()


def test_undecidable_record_keeps_judged_counts(tmp_path):
    req = request(golden([1, 1], [1, 1]), pol=policy(min_judged=5))
    data = outcome_json(judge(req), req, gate_id="gate-x", judged_at=NOW)
    assert data["verdict"] == "undecidable" and data["sets"] == [] and data["judged_counts"] == {"golden-syn": 2}
    assert data["undecidable_reasons"] == ["too_few_judged"]


def test_record_has_no_question_text_or_body():
    text = json.dumps(_record(), ensure_ascii=False)
    assert SYNTHETIC_TEXT not in text and SYNTHETIC_BODY not in text and "postgresql://" not in text
