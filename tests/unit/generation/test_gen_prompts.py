"""프롬프트 원문·버전 식별자(QK-GEN-001 tasks T007, research R-02, spec FR-003·005, SC-010)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from qello_knowledge.domain.generation import NO_THINK, PROMPT_NAMES, PromptSpec
from qello_knowledge.generation.prompts import PROMPTS, prompt_spec

GOLDEN = Path(__file__).parent / "golden"


def _golden(name: str) -> str:
    # 저장소 줄바꿈 설정과 관계없이 LF로 비교한다. 고정 파일은 승인 원문 코드 블록의 글 그대로다.
    return (GOLDEN / name).read_text(encoding="utf-8").replace("\r\n", "\n")


@pytest.mark.parametrize("name", ["gen-p1", "gen-base"])
def test_prompt_text_matches_approved_original(name):
    spec = prompt_spec(name)
    assert spec.system == _golden(f"{name}-system.txt")
    assert spec.user_template == _golden(f"{name}-template.txt")


def test_render_rules_and_names():
    assert prompt_spec("gen-p1").render_rule == "render-v1"
    assert prompt_spec("gen-base").render_rule == "render-base"
    assert set(PROMPTS) == set(PROMPT_NAMES)
    with pytest.raises(KeyError):
        prompt_spec("gen-x")


@pytest.mark.parametrize("name", ["gen-p1", "gen-base"])
def test_templates_end_with_no_think(name):
    assert prompt_spec(name).user_template.endswith(NO_THINK)


def test_version_format_and_material():
    spec = prompt_spec("gen-p1")
    assert re.fullmatch(r"gen-p1-[0-9a-f]{12}", spec.version)
    import hashlib

    material = json.dumps(
        {"system": spec.system, "template": spec.user_template, "render_rule": spec.render_rule},
        ensure_ascii=False,
        sort_keys=True,
    )
    assert spec.version == "gen-p1-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:12]


def test_changing_any_part_changes_version():
    base = prompt_spec("gen-p1")
    variants = [
        PromptSpec(base.name, base.system + " ", base.user_template, base.render_rule),
        PromptSpec(base.name, base.system, "x" + base.user_template, base.render_rule),
        PromptSpec(base.name, base.system, base.user_template, "render-v2"),
    ]
    versions = {base.version, *(v.version for v in variants)}
    assert len(versions) == 4


def test_template_must_keep_slots_and_no_think():
    with pytest.raises(ValueError):
        PromptSpec("gen-p1", "s", "{context} {question}", "render-v1")
    with pytest.raises(ValueError):
        PromptSpec("gen-p1", "s", "{context}" + NO_THINK, "render-v1")
