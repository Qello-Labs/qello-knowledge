"""구현 독립 검토 지적의 회귀 시험(QK-GEN-001, 2026-10-23 독립 검토 M1~M4·L1~L7·L9). 합성 자료만 쓴다."""

from __future__ import annotations

import pytest

from qello_knowledge.domain.generation import GenerationFailure, GenerationSettings, GenerationStatus, ProviderReply
from qello_knowledge.generation import service as service_module
from qello_knowledge.generation.fake import MemoryLedger, ScriptedProvider
from qello_knowledge.generation.postprocess import postprocess
from qello_knowledge.generation.prompts import prompt_spec
from qello_knowledge.generation.render import render
from qello_knowledge.generation.service import generate
from qello_knowledge.ports.generator import GenerationProviderFailure
from tests.unit.generation.gen_builders import Clock, block, chunk, deps, request

SETTINGS = GenerationSettings()
P1 = prompt_spec("gen-p1")


def _rendered(body: str = "본문"):
    return render("q", [block("S1", [chunk(1, 0, body)])], P1, SETTINGS)


def test_m1_citation_glued_to_url_is_kept_with_url():
    out = postprocess("주소는 https://ex.test/deploy[S1].", _rendered("주소 https://ex.test/deploy 이다"))
    assert out.answer == "주소는 https://ex.test/deploy[S1]." and out.citation_ids == ("S1",) and out.removed_urls == 0


@pytest.mark.parametrize(
    "answer",
    [
        "태그는 `<think>` 를 쓴다 [S1].",
        "닫는 태그는 `</think>`다 [S1].",
        "예시:\n```\n<think>생각</think>\n```\n끝이다 [S1].",
    ],
)
def test_m2_think_tags_inside_code_are_kept(answer):
    out = postprocess(answer, _rendered())
    assert out.answer == answer and out.citation_ids == ("S1",) and not out.thinking_detected


def test_m2_real_thinking_outside_code_is_still_removed():
    out = postprocess("<think>생각</think>설정은 `<think>`다 [S1].", _rendered())
    assert out.answer == "설정은 `<think>`다 [S1]." and out.thinking_detected


@pytest.mark.parametrize(
    ("reply", "row"), [(ProviderReply("답 [S1].", 100, 800), True), (ProviderReply("답 [S1].", 100, 10), False)]
)
def test_m3_usage_row_truncation_matches_summary(reply, row):
    ledger = MemoryLedger()
    result = generate(request(), deps(ScriptedProvider([reply]), ledger))
    assert result.summary.flags.truncated is row and ledger.records[0].truncated is row


def test_l1_nul_placeholder_in_reply_does_not_crash():
    out = postprocess("배포 \x00C3\x00 승인 뒤 [S1].", _rendered())
    assert "\x00" not in out.answer and out.citation_ids == ("S1",)


def test_l1_postprocess_error_is_recorded_as_bad_response(monkeypatch):
    def boom(text, rendered):
        raise RuntimeError("synthetic")

    monkeypatch.setattr(service_module, "postprocess", boom)
    ledger = MemoryLedger()
    result = generate(request(), deps(ScriptedProvider([ProviderReply("답 [S1].", 10, 2, neurons=0.5)]), ledger))
    assert (
        result.status is GenerationStatus.GENERATION_FAILED and result.summary.failure is GenerationFailure.BAD_RESPONSE
    )
    assert [(r.outcome, r.neurons) for r in ledger.records] == [("bad_response", 0.5)]


@pytest.mark.parametrize(
    ("answer", "expected"),
    [
        ("배포 일정은 제공된 자료만으로 확인할 수 없습니다 [S1].", "배포 일정은 제공된 자료만으로 확인할 수 없습니다."),
        ("배포는 승인 뒤에 한다 [S9]. 재시도는 3회다 [S1].", "배포는 승인 뒤에 한다. 재시도는 3회다 [S1]."),
    ],
)
def test_l2_no_space_left_before_punctuation(answer, expected):
    assert postprocess(answer, _rendered()).answer == expected


def test_l3_citation_moves_only_after_sentence_mark():
    out = postprocess(
        "A다 [S1]\n[S2] B다.",
        render("q", [block("S1", [chunk(1, 0, "x")]), block("S2", [chunk(2, 0, "y")])], P1, SETTINGS),
    )
    assert out.uncited_sentences == 0 and out.fact_sentences == 2


@pytest.mark.parametrize(
    ("answer", "kept"),
    [
        ("문서는 https://wiki.test/배포에서 본다 [S1].", True),
        ("문서는 https://wiki.test/배포로 간다 [S1].", True),
        ("문서는 https://wiki.test/배포안 이다 [S1].", False),
        ("문서는 https://wiki.test/배포판 이다 [S1].", False),
    ],
)
def test_l4_only_listed_particles_are_allowed(answer, kept):
    out = postprocess(answer, _rendered("문서 https://wiki.test/배포 참고"))
    assert ("https://wiki.test/배포" in out.answer) is kept and out.removed_urls == (0 if kept else 1)


def test_l5_retry_survives_attempt_slightly_over_timeout():
    clock = Clock()

    class Slow(ScriptedProvider):
        def complete(self, *args, **kwargs):
            clock.now += 20.01
            return super().complete(*args, **kwargs)

    provider = Slow([GenerationProviderFailure(GenerationFailure.TIMEOUT, billable=True, retry_after_seconds=2.0),
                     ProviderReply("답 [S1].", 1, 1)])  # fmt: skip
    result = generate(request(), deps(provider, MemoryLedger(), clock=clock))
    assert result.status is GenerationStatus.ANSWERED and len(provider.calls) == 2  # 20.01 + 2 + 20 ≤ 45


@pytest.mark.parametrize(
    "answer",
    ["설정은 .env 파일에 둔다 [S1].", "확장자 .py 파일만 읽는다 [S1].", "숨김 파일 .gitignore도 본다 [S1]."],
)
def test_n1_dot_names_keep_preceding_space(answer):
    # 재검토 N1: 문장부호 앞 공백 정리는 뒤가 공백·줄 끝인 문장부호에만 한다
    assert postprocess(answer, _rendered()).answer == answer


def test_n2_postprocess_error_keeps_truncation_flag(monkeypatch):
    def boom(text, rendered):
        raise RuntimeError("synthetic")

    monkeypatch.setattr(service_module, "postprocess", boom)
    ledger = MemoryLedger()
    result = generate(request(), deps(ScriptedProvider([ProviderReply("a", 10, 800)]), ledger))
    assert result.summary.flags.truncated is True and ledger.records[0].truncated is True
