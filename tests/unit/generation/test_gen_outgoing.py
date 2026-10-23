"""전송 직전 검사(QK-GEN-001 tasks T026, spec FR-010, US4 1~3, research R-05, SC-003)."""

from __future__ import annotations

from qello_knowledge.domain.embedding import SendBlock
from qello_knowledge.domain.generation import CannotConfirmReason, GenerationStatus, ProviderReply
from qello_knowledge.domain.retrieval import OmitReason, Omitted
from qello_knowledge.generation.fake import ScriptedProvider
from qello_knowledge.generation.service import generate
from tests.unit.generation.gen_builders import block, chunk, deps, request, retrieval, three_blocks

MARK = "SECRETLIKE-0000"  # 합성 표식. 가짜 검사가 이 글자를 비밀값으로 본다


class Checker:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def __call__(self, text: str, origin) -> tuple[SendBlock, ...]:
        self.calls.append((text, origin))
        return (SendBlock("synthetic-rule", 1),) if MARK in text else ()


def _run(question="배포 절차?", *, result=None, context=None):
    provider = ScriptedProvider([ProviderReply("배포는 승인 뒤에 한다 [S1]. 알림은 FCM이다 [S3].", 1, 1)])
    check = Checker()
    out = generate(request(question, context=context, result=result), deps(provider, check=check))
    return out, provider, check


def test_blocked_question_sends_nothing():
    out, provider, _ = _run(f"키는 {MARK} 이다")
    assert provider.calls == [] and out.status is GenerationStatus.OUTGOING_BLOCKED
    assert MARK not in repr(out) and MARK not in repr(out.summary)


def test_retrieval_reported_block_is_respected():
    status_blocked = retrieval(three_blocks(), status="outgoing_blocked")
    omitted_blocked = retrieval(three_blocks(), omitted=[Omitted("vector", OmitReason.OUTGOING_BLOCKED)])
    for result in (status_blocked, omitted_blocked):
        out, provider, _ = _run(result=result)
        assert provider.calls == [] and out.status is GenerationStatus.OUTGOING_BLOCKED


def test_question_check_comes_before_no_results():
    out, provider, _ = _run(f"키 {MARK}", result=retrieval(status="no_results"))
    assert out.status is GenerationStatus.OUTGOING_BLOCKED and provider.calls == []


def test_blocked_block_is_dropped_and_others_keep_ids():
    context = (
        block("S1", [chunk(1, 0, "배포는 승인 뒤에 한다.")]),
        block("S2", [chunk(2, 0, f"설정 {MARK}")]),
        block("S3", [chunk(3, 0, "알림은 FCM이다.")]),
    )
    out, provider, check = _run(context=context)
    sent = provider.calls[0].user
    assert MARK not in sent and "[S2]" not in sent and "[S1]" in sent and "[S3]" in sent
    assert [d.source_id for d in out.summary.dropped] == ["S2"]
    assert out.summary.dropped[0].rules == ("synthetic-rule",)
    assert out.summary.blocks_sent == 2
    assert [c.source_id for c in out.citations] == ["S1", "S3"]
    assert len(check.calls) == 4 and all(origin is None for _, origin in check.calls)  # 질문 1 + 묶음 3
    assert check.calls[1][0].startswith("[S1] A > B | 수정 ")  # 머리줄을 포함한 실제로 보낼 글


def test_all_blocks_blocked_is_cannot_confirm_without_call():
    context = (block("S1", [chunk(1, 0, MARK)]), block("S2", [chunk(2, 0, f"{MARK} 둘")]))
    out, provider, _ = _run(context=context)
    assert provider.calls == []
    assert out.summary.cannot_confirm_reason is CannotConfirmReason.ALL_BLOCKS_BLOCKED


def test_partial_retrieval_still_generates_with_reasons_kept():
    for reason in (
        OmitReason.QUERY_EMBEDDING_FAILED,
        OmitReason.VECTOR_SEARCH_FAILED,
        OmitReason.KEYWORD_SEARCH_FAILED,
    ):
        search = "keyword" if reason is OmitReason.KEYWORD_SEARCH_FAILED else "vector"
        result = retrieval(three_blocks(), omitted=[Omitted(search, reason)])
        out, provider, _ = _run(result=result)
        assert out.status is GenerationStatus.ANSWERED and len(provider.calls) == 1
        assert out.retrieval.omitted == (Omitted(search, reason),)
