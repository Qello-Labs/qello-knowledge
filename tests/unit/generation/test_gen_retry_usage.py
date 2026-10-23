"""재시도·마감·사용량 기록(QK-GEN-001 tasks T037, spec FR-020~024, US6, research R-06·R-07, SC-007)."""

from __future__ import annotations

import logging

import pytest

from qello_knowledge.domain.generation import GenerationFailure, GenerationSettings, GenerationStatus, ProviderReply
from qello_knowledge.generation.fake import MemoryLedger, ScriptedProvider
from qello_knowledge.generation.service import generate
from qello_knowledge.ports.generator import GenerationProviderFailure
from tests.unit.generation.gen_builders import Clock, deps, request

OK = ProviderReply("배포는 승인 뒤에 한다 [S1].", 1000, 50, neurons=6.2)


def _failure(kind, *, billable=True, **kw):
    return GenerationProviderFailure(kind, billable=billable, **kw)


def _run(script, *, ledger=None, clock=None, settings=None):
    provider = ScriptedProvider(script)
    ledger = ledger or MemoryLedger()
    clock = clock or Clock()
    result = generate(request(), deps(provider, ledger, clock=clock), settings)
    return result, provider, ledger, clock


@pytest.mark.parametrize("kind", [GenerationFailure.TRANSIENT, GenerationFailure.TIMEOUT])
def test_retryable_failure_then_success(kind):
    result, provider, ledger, clock = _run([_failure(kind, retry_after_seconds=1.0), OK])
    assert result.status is GenerationStatus.ANSWERED
    assert len(provider.calls) == 2 and [r.attempt for r in ledger.records] == [1, 2]
    assert [r.outcome for r in ledger.records] == [kind.value, "ok"]
    assert clock.slept == [1.0]
    assert result.summary.generation_calls == 4 and result.summary.attempts == 2


def test_two_transient_failures_end_as_transient():
    result, provider, ledger, _ = _run([_failure(GenerationFailure.TRANSIENT)] * 2)
    assert result.status is GenerationStatus.GENERATION_FAILED and result.summary.failure is GenerationFailure.TRANSIENT
    assert len(provider.calls) == 2 and len(ledger.records) == 2
    assert result.summary.generation_calls <= 4


@pytest.mark.parametrize(
    "kind", [GenerationFailure.PROVIDER_QUOTA, GenerationFailure.AUTH_CONFIG, GenerationFailure.BAD_RESPONSE]
)
def test_non_retryable_failure_is_returned_at_once(kind):
    result, provider, ledger, clock = _run([_failure(kind, billable=False), OK])
    assert result.summary.failure is kind and len(provider.calls) == 1 and clock.slept == []
    assert ledger.records[0].neurons == 0.0 and ledger.records[0].measured is False


def test_retry_is_skipped_when_deadline_would_pass():
    clock = Clock()

    class SlowProvider(ScriptedProvider):
        def complete(self, *args, **kwargs):
            clock.now += 30  # 첫 시도가 30초 걸렸다
            return super().complete(*args, **kwargs)

    provider = SlowProvider([_failure(GenerationFailure.TIMEOUT), OK])
    result = generate(request(), deps(provider, MemoryLedger(), clock=clock))
    assert result.summary.failure is GenerationFailure.TIMEOUT and len(provider.calls) == 1  # 30 + 0.5 + 20 > 45


def test_retry_delay_receives_provider_hint():
    seen = []
    clock = Clock()
    d = deps(ScriptedProvider([_failure(GenerationFailure.TRANSIENT, retry_after_seconds=7.0), OK]), clock=clock)
    d = type(d)(**{**d.__dict__, "retry_delay": lambda attempt, after: seen.append((attempt, after)) or 0.1})
    generate(request(), d)
    assert seen == [(0, 7.0)] and clock.slept == [0.1]


def test_neurons_measured_then_token_price_then_estimate():
    settings = GenerationSettings()
    measured, _, l1, _ = _run([OK])
    assert (l1.records[0].neurons, l1.records[0].measured) == (6.2, True) and measured.summary.measured
    tokens, _, l2, _ = _run([ProviderReply("답 [S1].", 1000, 50)])
    assert l2.records[0].neurons == pytest.approx(settings.estimated_neurons(1000, 50)) and not l2.records[0].measured
    assert not tokens.summary.measured
    timeout, _, l3, _ = _run([_failure(GenerationFailure.TIMEOUT)] * 2)
    estimated = settings.estimated_neurons(timeout.summary.estimated_input_tokens, settings.max_tokens)
    assert [r.neurons for r in l3.records] == [pytest.approx(estimated)] * 2
    header, _, l4, _ = _run([_failure(GenerationFailure.BAD_RESPONSE, neurons=4.4)])
    assert (l4.records[0].neurons, l4.records[0].measured) == (4.4, True)


def test_success_with_empty_post_processing_is_recorded_as_bad_response():
    result, _, ledger, _ = _run([ProviderReply("[S1]", 10, 1, neurons=1.0)])
    assert result.summary.failure is GenerationFailure.BAD_RESPONSE
    assert ledger.records[0].outcome == "bad_response" and ledger.records[0].neurons == 1.0


@pytest.mark.parametrize(
    ("reply", "truncated"),
    [
        (ProviderReply("답 [S1].", 10, 800, finish_reason="length"), True),
        (ProviderReply("답 [S1].", 10, 800), True),
        (ProviderReply("답 [S1].", 10, 799), False),
        (ProviderReply("답 [S1].", 10, 800, finish_reason="stop"), False),
    ],
)
def test_truncation_flag(reply, truncated):
    result, _, _, _ = _run([reply])
    assert result.summary.flags.truncated is truncated


def test_record_failure_keeps_answer(caplog):
    caplog.set_level(logging.WARNING)
    result, _, _, _ = _run([OK], ledger=MemoryLedger(fail_record=True))
    assert result.status is GenerationStatus.ANSWERED and result.summary.flags.usage_record_failed
    assert result.summary.usage_today is None
    assert "generation_usage_record_failed" in caplog.text


def test_reserve_exceeded_warns_but_answers(caplog):
    caplog.set_level(logging.WARNING)
    result, _, _, _ = _run([OK], ledger=MemoryLedger(query_embedding_used=2998.0))
    today = result.summary.usage_today
    assert result.status is GenerationStatus.ANSWERED
    assert today.query_reserve_exceeded and today.answer_total == pytest.approx(3004.2)
    assert "query_reserve_exceeded" in caplog.text


def test_usage_today_is_last_successful_record():
    result, _, ledger, _ = _run(
        [_failure(GenerationFailure.TRANSIENT), OK], ledger=MemoryLedger(query_embedding_used=1.0)
    )
    today = result.summary.usage_today
    assert today.generation_used == pytest.approx(sum(r.neurons for r in ledger.records))
    assert today.generation_used == pytest.approx(result.summary.neurons)  # 두 시도(추정 + 측정)의 합
    assert today.answer_total == pytest.approx(today.generation_used + 1.0)
