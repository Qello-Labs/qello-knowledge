"""정상 경로(QK-GEN-001 tasks T013, spec US1 1~5, FR-016·026, SC-010)."""

from __future__ import annotations

from qello_knowledge.domain.generation import GenerationStatus, ProviderReply
from qello_knowledge.generation.fake import MemoryLedger, ScriptedProvider
from qello_knowledge.generation.service import generate
from tests.unit.generation.gen_builders import COLLECTED, MODIFIED, deps, request


def _run(answer: str, **reply):
    provider = ScriptedProvider([ProviderReply(answer, 900, 40, neurons=5.4, **reply)])
    ledger = MemoryLedger()
    result = generate(request(), deps(provider, ledger))
    return result, provider, ledger


def test_cited_answer_lists_sources_in_number_order_with_original_values():
    result, provider, _ = _run("재시도는 3회다 [S2]. 배포는 승인 뒤에 한다 [S1].")
    assert result.status is GenerationStatus.ANSWERED
    assert [c.source_id for c in result.citations] == ["S1", "S2"]
    first = result.citations[0]
    assert (first.title, first.source_version, first.source_modified_at, first.collected_at) == (
        "A > B", "sha1", MODIFIED, COLLECTED,
    )  # fmt: skip
    assert first.source_url == "https://github.example.test/o/r/blob/main/docs/doc1.md"
    assert len(provider.calls) == 1


def test_uncited_blocks_are_not_listed():
    result, _, _ = _run("배포는 승인 뒤에 한다 [S1].")
    assert [c.source_id for c in result.citations] == ["S1"]


def test_summary_has_conditions_and_no_raw_text():
    result, provider, ledger = _run("배포는 승인 뒤에 한다 [S1].")
    s = result.summary
    assert s.prompt_version.startswith("gen-p1-") and s.model_id == "@cf/qwen/qwen3-30b-a3b-fp8"
    assert (s.max_tokens, s.temperature, s.no_think, s.blocks_sent) == (800, 0.2, True, 3)
    assert (s.input_tokens, s.output_tokens, s.neurons, s.measured, s.attempts) == (900, 40, 5.4, True, 1)
    assert s.estimated_input_tokens > 0 and s.latency_ms == 0
    assert (s.generation_calls, s.total_calls) == (2, 7)  # 생성 1 + 기록 1, 검색 5
    assert s.usage_today is not None and s.usage_today.generation_used == 5.4
    assert len(ledger.records) == 1 and ledger.records[0].outcome == "ok"
    call = provider.calls[0]
    assert (call.max_tokens, call.temperature, call.timeout_seconds) == (800, 0.2, 20)
    assert "배포 절차가 뭐야?" not in repr(result) and "배포 절차가 뭐야?" not in repr(s)


def test_same_input_twice_gives_same_input_and_result():
    first, p1, _ = _run("배포는 승인 뒤에 한다 [S1].")
    second, p2, _ = _run("배포는 승인 뒤에 한다 [S1].")
    assert p1.calls[0] == p2.calls[0] and p1.calls[0].user == p2.calls[0].user
    assert (first.answer, first.citations, first.summary) == (second.answer, second.citations, second.summary)
