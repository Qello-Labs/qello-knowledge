"""활성화 쪽 게이트 확인(QK-STO-002 contracts/gate-record.md 5절, research R-11)."""

import json
from datetime import UTC, datetime
from pathlib import Path

from qello_knowledge.devtools.gate_cli import run_gate
from qello_knowledge.gate.verify import verify_for_activation
from tests.unit.devtools.test_gate_cli import _args
from tests.unit.gate.gate_builders import POLICY_PATH, V1, V2, FakeHistory, golden, policy_text, write_repo

NOW = datetime(2026, 11, 5, 3, 4, 5, tzinfo=UTC)


def _gate(root, record, *, raw=None):
    raw, runs = write_repo(root, record, policy_raw=raw)
    history = FakeHistory(files={("origin/main", POLICY_PATH): raw})
    run_gate(_args(root, runs, out="gate.json"), repo_root=root, history_factory=lambda r: history, now=lambda: NOW)
    return root / "gate.json", history


def _verify(path, history, root, *, active=V1, target=V2):
    return verify_for_activation(path, active=active, target=target, history=history, repo_root=root)


def test_pass_record_verifies(tmp_path, capsys):
    path, history = _gate(tmp_path, golden([1, 1], [1, 1]))
    verified, failed = _verify(path, history, tmp_path)
    assert failed == () and verified.candidate_tokenizer == "TokenBigramSplitSymbol"
    assert verified.search == {"query_rule": "kw-query-v1", "candidates": 20, "rrf_k": 60}
    assert verified.summary["sets"][0]["judged"] == 2 and len(verified.sha256) == 64


def test_each_gate_condition(tmp_path, capsys):
    path, history = _gate(tmp_path / "fail", golden([1, 1], [6, 1]))
    assert "gate_verdict" in _verify(path, history, tmp_path / "fail")[1]
    path, history = _gate(tmp_path / "ok", golden([1, 1], [1, 1]))
    root = tmp_path / "ok"
    assert "gate_candidate" in _verify(path, history, root, target="iv-other")[1]
    assert "gate_baseline" in _verify(path, history, root, active="iv-other")[1]
    for bad in (
        FakeHistory(files={("origin/main", POLICY_PATH): b"changed"}),
        FakeHistory(files={}),
        FakeHistory(
            files={("origin/main", POLICY_PATH): (root / POLICY_PATH).read_bytes()}, listing=("v1.toml", "v2.toml")
        ),
    ):
        assert "gate_policy" in _verify(path, bad, root)[1]


def test_integrity_checks(tmp_path, capsys):
    path, history = _gate(tmp_path, golden([1, 1], [1, 1]))
    run = tmp_path / "specs/runs/run-0.json"
    original = run.read_bytes()
    run.write_bytes(original.replace(b'"complete": true', b'"complete": true '))
    assert _verify(path, history, tmp_path)[1] == ("gate_integrity",)
    run.write_bytes(original)
    data = json.loads(path.read_text())
    data["sets"][0]["metrics"]["recall_at_5"]["candidate"] = "1.0001"
    path.write_text(json.dumps(data))
    assert _verify(path, history, tmp_path)[1] == ("gate_integrity",)
    Path(tmp_path / POLICY_PATH).write_text(policy_text(min_judged=1))
    assert "gate_integrity" in _verify(path, history, tmp_path)[1]
    assert _verify(tmp_path / "missing.json", history, tmp_path) == (None, ("gate_integrity",))
