"""입력 토큰 추정과 입력 한도 검사(QK-GEN-001 research R-08, spec FR-019)."""

from __future__ import annotations

import math

from qello_knowledge.domain.generation import GenerationSettings
from qello_knowledge.domain.retrieval import RetrievalSettings
from qello_knowledge.generation.prompts import prompt_spec

MAX_BYTES_PER_CHAR = 4  # UTF-8 한 글자의 최대 바이트. 질문 길이 상한(글자 수)을 바이트로 바꾼다


def estimate_tokens(text: str, settings: GenerationSettings) -> int:
    """예상 토큰. QK-RET-001과 같은 방식(UTF-8 바이트 ÷ 바이트당 토큰)이다."""
    return math.ceil(len(text.encode("utf-8")) / settings.bytes_per_token)


def _fixed_template(template: str) -> str:
    return template.replace("{context}", "").replace("{question}", "")


def worst_case_tokens(gen: GenerationSettings, retrieval: RetrievalSettings) -> int:
    """설정 검사 (1)의 합: 배율 × (시스템 + 템플릿 고정 문구 + 질문 상한 + Context 예산) + 출력 상한."""
    prompt = prompt_spec(gen.prompt_version)
    question = math.ceil(retrieval.question_max_chars * MAX_BYTES_PER_CHAR / gen.bytes_per_token)
    inputs = (
        estimate_tokens(prompt.system, gen)
        + estimate_tokens(_fixed_template(prompt.user_template), gen)
        + question
        + retrieval.context_budget
    )
    return math.ceil(gen.underestimate_factor * inputs) + gen.max_tokens


def check_settings(gen: GenerationSettings, retrieval: RetrievalSettings) -> list[str]:
    """spec FR-019 (1). 문제 문장 목록을 돌려준다(원문 없음). 비면 통과다."""
    total = worst_case_tokens(gen, retrieval)
    if total > gen.context_window:
        return [f"생성 입력 최대 예상 {total} > 모델 컨텍스트 {gen.context_window}"]
    return []


def within_input_limit(estimated_input_tokens: int, gen: GenerationSettings) -> bool:
    """spec FR-019 (2) 호출 직전 검사."""
    return math.ceil(gen.underestimate_factor * estimated_input_tokens) + gen.max_tokens <= gen.context_window
