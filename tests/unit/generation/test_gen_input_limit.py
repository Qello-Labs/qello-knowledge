"""호출 직전 입력 한도(QK-GEN-001 tasks T038, spec FR-019 (2), SC-009)."""

from __future__ import annotations

from qello_knowledge.domain.generation import GenerationFailure, GenerationStatus
from qello_knowledge.generation.fake import MemoryLedger, ScriptedProvider
from qello_knowledge.generation.service import generate
from tests.unit.generation.gen_builders import block, chunk, deps, request


def test_oversized_input_is_rejected_without_call_or_record():
    # 검색 요청별 덮어쓰기(예산 8,000)로 커진 Context와 최대 길이 질문을 흉내 낸다(research R-08 계산 36,364 > 32,768).
    big = "가" * 9000  # 27,000바이트 ≈ 예상 7,715토큰
    context = tuple(block(f"S{i}", [chunk(i, 0, big)]) for i in range(1, 4))
    provider, ledger = ScriptedProvider(), MemoryLedger()
    result = generate(request("질" * 8000, context=context), deps(provider, ledger))
    assert result.status is GenerationStatus.GENERATION_FAILED
    assert result.summary.failure is GenerationFailure.INPUT_TOO_LONG
    assert provider.calls == [] and ledger.records == []
    assert result.summary.estimated_input_tokens * 2 + 800 > 32768


def test_default_sized_input_passes():
    provider = ScriptedProvider()
    result = generate(request(context=(block("S1", [chunk(1, 0, "가" * 2000)]),)), deps(provider))
    assert result.status is not GenerationStatus.GENERATION_FAILED and len(provider.calls) == 1
