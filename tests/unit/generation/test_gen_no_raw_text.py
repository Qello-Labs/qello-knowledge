"""원문 비기록(QK-GEN-001 tasks T030·T039a, spec FR-012, SC-006).

질문·청크 본문·모델 답에 서로 다른 합성 표식을 넣고, 요약·사용량 기록·로그·예외 문구에 표식이 하나도 없는지 본다.
"""

from __future__ import annotations

import logging

import pytest

from qello_knowledge.domain.generation import GenerationFailure, ProviderReply
from qello_knowledge.generation.fake import MemoryLedger, ScriptedProvider
from qello_knowledge.generation.service import generate
from qello_knowledge.ports.generator import GenerationProviderFailure
from tests.unit.generation.gen_builders import block, chunk, deps, request, retrieval

Q_MARK = "질문표식-a1b2"
C_MARK = "본문표식-c3d4"
A_MARK = "답표식-e5f6"


def _context():
    return (block("S1", [chunk(1, 0, f"배포 규칙 {C_MARK}.")]),)


def _assert_clean(result, ledger, caplog, error=None):
    texts = [repr(result.summary), repr(result.retrieval), *(repr(r) for r in ledger.records), caplog.text]
    if error is not None:
        texts.append(str(error))
    for text in texts:
        for mark in (Q_MARK, C_MARK, A_MARK):
            assert mark not in text


@pytest.mark.parametrize(
    "script",
    [
        [ProviderReply(f"{A_MARK} 배포는 승인 뒤에 한다 [S1].", 10, 5)],
        [ProviderReply("제공된 자료만으로 확인할 수 없습니다.", 10, 5)],
        [ProviderReply("", 10, 5)],
        [GenerationProviderFailure(GenerationFailure.AUTH_CONFIG, billable=False)],
        [GenerationProviderFailure(GenerationFailure.BAD_RESPONSE, billable=True)],
    ],
)
def test_paths_without_retry_leave_no_raw_text(script, caplog):
    caplog.set_level(logging.DEBUG)
    ledger = MemoryLedger()
    result = generate(request(f"{Q_MARK} 배포?", context=_context()), deps(ScriptedProvider(script), ledger))
    _assert_clean(result, ledger, caplog)


@pytest.mark.parametrize("status", ["no_results", "store_unavailable", "outgoing_blocked"])
def test_no_call_paths_leave_no_raw_text(status, caplog):
    caplog.set_level(logging.DEBUG)
    ledger = MemoryLedger()
    result = generate(request(f"{Q_MARK} 배포?", result=retrieval(_context(), status=status)), deps(ledger=ledger))
    _assert_clean(result, ledger, caplog)


@pytest.mark.parametrize(
    "script",
    [
        [GenerationProviderFailure(GenerationFailure.TRANSIENT, billable=True), ProviderReply(f"{A_MARK} [S1].", 1, 1)],
        [GenerationProviderFailure(GenerationFailure.TIMEOUT, billable=True)] * 2,
        [GenerationProviderFailure(GenerationFailure.PROVIDER_QUOTA, billable=False)],
    ],
)
def test_retry_and_failure_paths_leave_no_raw_text(script, caplog):
    caplog.set_level(logging.DEBUG)
    ledger = MemoryLedger()
    result = generate(request(f"{Q_MARK} 배포?", context=_context()), deps(ScriptedProvider(script), ledger))
    _assert_clean(result, ledger, caplog)
    for raised in (item for item in script if isinstance(item, GenerationProviderFailure)):
        # 생성 경계가 실제로 받은 예외 객체의 문구에도 표식이 없다(독립 검토 L7)
        for mark in (Q_MARK, C_MARK, A_MARK):
            assert mark not in str(raised) and mark not in repr(raised.shape)


def test_record_failure_and_reserve_warning_leave_no_raw_text(caplog):
    caplog.set_level(logging.DEBUG)
    for ledger in (MemoryLedger(fail_record=True), MemoryLedger(query_embedding_used=5000)):
        result = generate(
            request(f"{Q_MARK} 배포?", context=_context()),
            deps(ScriptedProvider([ProviderReply(f"{A_MARK} [S1].", 1, 1)]), ledger),
        )
        _assert_clean(result, ledger, caplog)
    assert "generation_usage_record_failed" in caplog.text and "query_reserve_exceeded" in caplog.text
