"""`QK_GEN_*` 설정 등록과 생성 설정 검사(QK-GEN-001 tasks T045, research R-12, spec FR-019·FR-025)."""

from __future__ import annotations

import pytest

from qello_knowledge.config.check import GENERATION_CHECK, build_report, generation_settings
from qello_knowledge.config.loader import load
from qello_knowledge.config.registry import SETTINGS, Entrypoint, specs_for
from qello_knowledge.domain.generation import GenerationSettings

NAMES = ("QK_GEN_MODEL", "QK_GEN_MAX_TOKENS", "QK_GEN_TEMPERATURE", "QK_GEN_TIMEOUT_SECONDS", "QK_GEN_PROMPT_VERSION")
DEFAULTS = {
    "QK_GEN_MODEL": "@cf/qwen/qwen3-30b-a3b-fp8",
    "QK_GEN_MAX_TOKENS": "800",
    "QK_GEN_TEMPERATURE": "0.2",
    "QK_GEN_TIMEOUT_SECONDS": "20",
    "QK_GEN_PROMPT_VERSION": "gen-p1",
}


def _load(entrypoint=Entrypoint.QUERY, **environ):
    return load(entrypoint, environ=environ, env_file=None)


@pytest.mark.parametrize("entrypoint", [Entrypoint.QUERY, Entrypoint.INDEX])
def test_registered_for_both_entrypoints_with_defaults(entrypoint):
    specs = {s.name: s for s in specs_for(entrypoint)}
    for name in NAMES:
        spec = specs[name]
        assert spec.default == DEFAULTS[name] and not spec.required and not spec.secret


def test_defaults_become_generation_settings():
    assert generation_settings(_load()) == GenerationSettings()


@pytest.mark.parametrize(
    ("name", "good", "bad"),
    [
        ("QK_GEN_MODEL", "@cf/qwen/qwen3-8b", "@cf/meta/llama-3.1-8b-instruct"),
        ("QK_GEN_MAX_TOKENS", "4096", "4097"),
        ("QK_GEN_TEMPERATURE", "1.0", "1.5"),
        ("QK_GEN_TIMEOUT_SECONDS", "60", "61"),
        ("QK_GEN_PROMPT_VERSION", "gen-base", "gen-x"),
    ],
)
def test_format_rules(name, good, bad):
    spec = next(s for s in SETTINGS if s.name == name)
    assert spec.rule(good) and not spec.rule(bad)
    assert generation_settings(_load(**{name: good})) is not None
    assert generation_settings(_load(**{name: bad})) is None


def test_default_report_has_no_generation_check_entry():
    report = build_report(_load())
    assert all(check.name != GENERATION_CHECK for check in report.checks)


def test_largest_env_values_still_fit_the_window():
    # 환경값 범위의 최대(예산 8,000, 출력 4,096)도 2 × (624 + 15 + 2,286 + 8,000) + 4,096 = 25,946 ≤ 32,768이다.
    # 그래서 설정 검사 (1)은 코드 설정용 안전망이고, 요청별 덮어쓰기는 호출 직전 검사(2)가 막는다(tasks T038).
    report = build_report(_load(QK_RETRIEVAL_CONTEXT_BUDGET="8000", QK_GEN_MAX_TOKENS="4096"))
    assert all(check.name != GENERATION_CHECK for check in report.checks)  # 필수 접속 항목이 없어 ok 자체는 보지 않는다


def test_generation_problem_is_reported(monkeypatch):
    import qello_knowledge.generation.settings as gen_settings

    monkeypatch.setattr(
        gen_settings, "check_settings", lambda gen, retrieval: ["생성 입력 최대 예상 40000 > 모델 컨텍스트 32768"]
    )
    report = build_report(_load())
    failing = [c for c in report.checks if c.name == GENERATION_CHECK]
    assert len(failing) == 1 and not failing[0].ok
    assert "32768" in failing[0].detail
