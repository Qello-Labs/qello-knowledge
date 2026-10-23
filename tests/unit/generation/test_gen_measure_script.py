"""실측 스크립트(QK-GEN-001 tasks T033, research R-11, spec SC-008). 가짜 제공자만 쓴다."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

from qello_knowledge.domain.generation import ProviderReply
from qello_knowledge.generation.fake import ScriptedProvider

SCRIPT = Path(__file__).resolve().parents[3] / "specs/QK-GEN-001-answer-generation/measurement/measure_generation.py"


@pytest.fixture(scope="module")
def measure():
    spec = importlib.util.spec_from_file_location("measure_generation", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclass가 모듈을 찾을 수 있게
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop(spec.name, None)


def _run(measure, capsys, argv, factory=None):
    code = measure.main(argv, provider_factory=factory)
    captured = capsys.readouterr()
    return code, captured


def test_question_set_shape(measure):
    assert measure.QUESTION_SET == "gen-ko-v1"
    kinds = [item.kind for item in measure.ITEMS]
    assert len(kinds) == 12
    assert kinds[:5] == ["fact", "procedure", "synthesis", "identifier", "cannot"]
    assert sorted(kinds[5:]) == sorted(["conflict"] * 2 + ["current"] * 2 + ["partial", "injection", "unrelated"])
    assert {i.id for i in measure.ITEMS if i.expect_cannot} == {"G5", "U1"}
    assert all(
        url.startswith("https://docs.example.test/")
        for url in (b.source_url for i in measure.ITEMS for b in measure.context_for(i))
    )


def test_only_one_with_candidate_prompt(measure, capsys, tmp_path_factory):
    out = Path(measure.tempfile.gettempdir()) / "qk-gen-measure-test-only"
    code, captured = _run(measure, capsys, ["--only", "1", "--prompt", "gen-p1", "--out", str(out)])
    data = json.loads(captured.out)
    assert code == 0 and len(data["rows"]) == 1
    row = data["rows"][0]
    assert row["id"] == "G1" and row["prompt"].startswith("gen-p1-")
    for key in ("status", "removed_citations", "unrecognized_citations", "uncited_sentences", "sentence_citation_ratio",
                "response_shape", "latency_ms", "neurons"):  # fmt: skip
        assert key in row
    summary = data["summary"]
    assert (summary["question_set"], summary["samples"]) == ("gen-ko-v1", 1)
    assert summary["model"] == "@cf/qwen/qwen3-30b-a3b-fp8" and summary["date"]
    assert {"latency_p50_ms", "latency_p95_ms"} <= set(next(iter(summary["prompts"].values())))
    assert "프로필 이미지" not in captured.out  # 질문·답 원문은 표준 출력에 없다
    answers = json.loads((out / "answers.json").read_text(encoding="utf-8"))
    assert answers[0]["question"].startswith("프로필 이미지")


def test_both_prompts_run_all_items(measure, capsys):
    out = Path(measure.tempfile.gettempdir()) / "qk-gen-measure-test-both"
    code, captured = _run(measure, capsys, ["--out", str(out)])
    data = json.loads(captured.out)
    assert code == 0 and len(data["rows"]) == 24
    assert {r["prompt"].split("-")[1] for r in data["rows"]} == {"p1", "base"}


def test_out_inside_repository_is_rejected(measure, capsys):
    code, captured = _run(measure, capsys, ["--out", str(SCRIPT.parent / "out")])
    assert code == 2 and "out_inside_repository" in captured.err


def test_real_provider_path_prints_estimate_first(measure, capsys):
    made = []

    def factory(settings):
        made.append(settings.prompt_version)
        return ScriptedProvider([ProviderReply("제공된 자료만으로 확인할 수 없습니다.", 10, 5)])

    out = Path(measure.tempfile.gettempdir()) / "qk-gen-measure-test-real"
    code, captured = _run(measure, capsys, ["--provider", "workers-ai", "--only", "2", "--out", str(out)], factory)
    estimate = json.loads(captured.err)
    assert code == 0 and estimate["calls"] == 4
    assert estimate["with_retry_max"] == pytest.approx(estimate["estimated_neurons_max_output"] * 2, abs=0.2)
    assert made == ["gen-p1", "gen-p1", "gen-base", "gen-base"]


def test_default_out_is_outside_repository(measure):
    assert not measure._inside_repo(Path(measure.tempfile.gettempdir()))
