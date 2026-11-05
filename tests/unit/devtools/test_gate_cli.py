"""`qk-dev eval gate`(QK-STO-002 contracts/cli.md 6절). 가짜 `RepoHistory`만 쓴다(DB·네트워크 0)."""

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from qello_knowledge.devtools import db
from qello_knowledge.devtools.gate_cli import run_gate
from tests.unit.gate.gate_builders import BASE, CAND, POLICY_PATH, V1, V2, FakeHistory, golden, policy_text, write_repo

NOW = datetime(2026, 11, 5, 3, 4, 5, tzinfo=UTC)


def _args(root, runs, *, out="eval/gate_records/{gate_id}.json", main_ref="origin/main", policy=POLICY_PATH):
    return argparse.Namespace(
        policy=root / policy,
        run=[root / r for r in runs],
        baseline_target=BASE,
        candidate_target=CAND,
        baseline_version=V1,
        candidate_version=V2,
        out=str(root / out),
        main_ref=main_ref,
        json=True,
    )


def _history(raw, ref="origin/main"):
    return lambda root: FakeHistory(files={(ref, POLICY_PATH): raw})


def _run(tmp_path, capsys, record, *, raw=None, history=None, **kw):
    raw_written, runs = write_repo(tmp_path, record, policy_raw=raw)
    code = run_gate(
        _args(tmp_path, runs, **kw),
        repo_root=tmp_path,
        history_factory=history or _history(raw_written),
        now=lambda: NOW,
    )
    return code, json.loads(capsys.readouterr().out)


def test_pass_writes_record_with_gate_id_placeholder(tmp_path, capsys):
    code, out = _run(tmp_path, capsys, golden([1, 1], [1, 1]))
    assert code == 0 and out["verdict"] == "pass"
    path = Path(out["gate_record"])
    assert path.name == f"{out['gate_id']}.json" and out["gate_id"].startswith("gate-20261105T030405Z-")
    data = json.loads(path.read_text())
    assert data["policy"]["main_ref"] == "origin/main" and data["policy"]["merge_commit"] == "m" * 40
    assert [r["path"] for r in data["runs"]] == ["specs/runs/run-0.json"]


def test_fail_and_undecidable_both_write_records(tmp_path, capsys):
    code, out = _run(tmp_path, capsys, golden([1, 1], [6, 1]))
    assert code == 1 and out["verdict"] == "fail" and Path(out["gate_record"]).exists()
    other = tmp_path / "other"
    other.mkdir()
    raw, runs = write_repo(other, golden([1, 1], [1, 1]))
    code = run_gate(
        _args(other, runs, main_ref="origin/elsewhere"),
        repo_root=other,
        history_factory=lambda root: FakeHistory(files={}),
        now=lambda: NOW,
    )
    out = json.loads(capsys.readouterr().out)
    assert code == 3 and "policy_unmerged" in out["undecidable_reasons"]
    assert json.loads(Path(out["gate_record"]).read_text())["policy"]["main_ref"] == "origin/elsewhere"


def test_argument_errors_write_nothing(tmp_path, capsys):
    raw, runs = write_repo(tmp_path, golden([1, 1], [1, 1]), policy_raw=policy_text(min_judged=0))
    assert run_gate(_args(tmp_path, runs), repo_root=tmp_path, history_factory=_history(raw)) == 2
    assert json.loads(capsys.readouterr().out)["error"] == "policy_invalid"
    assert not (tmp_path / "eval/gate_records").exists()
    (tmp_path / POLICY_PATH).write_text(policy_text(), encoding="utf-8")
    raw = (tmp_path / POLICY_PATH).read_bytes()
    existing = tmp_path / "fixed.json"
    existing.write_text("{}")
    assert run_gate(_args(tmp_path, runs, out="fixed.json"), repo_root=tmp_path, history_factory=_history(raw)) == 2
    assert json.loads(capsys.readouterr().out)["error"] == "out_exists" and existing.read_text() == "{}"


def test_output_has_no_question_text(tmp_path, capsys):
    code, out = _run(tmp_path, capsys, golden([1, 1], [1, 1]))
    text = json.dumps(out) + Path(out["gate_record"]).read_text()
    assert "합성 질문" not in text and "postgresql://" not in text


def test_registered_under_qk_dev_eval(tmp_path):
    with pytest.raises(SystemExit) as raised:
        db.main(["eval", "gate", "--policy", "x.toml"])
    assert raised.value.code == 2
