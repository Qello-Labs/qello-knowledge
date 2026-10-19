from datetime import timedelta

import pytest

from qello_knowledge.domain.source import RunStopped, StopReason
from qello_knowledge.domain.source_config import RetryPolicy
from qello_knowledge.sources.retry import RunClock, next_delay, system_jitter


def test_full_jitter_uses_exponential_caps_then_maximum(clock, jitter):
    policy = RetryPolicy(max_backoff_seconds=3)
    assert [next_delay(policy, n, jitter, None, clock) for n in range(5)] == [0.5, 1, 1.5, 1.5, 1.5]
    assert clock.sleeps == []


def test_origin_retry_time_overrides_jitter(clock):
    def unexpected_jitter(cap):
        pytest.fail("원본이 지정한 시각에는 jitter를 더하지 않는다")

    retry_at = clock.now() + timedelta(seconds=30)
    assert next_delay(RetryPolicy(), 0, unexpected_jitter, retry_at, clock) == 30
    clock.sleep(31)
    assert next_delay(RetryPolicy(), 0, unexpected_jitter, retry_at, clock) == 0


def test_runtime_budget_checks_cumulative_wait_before_sleep(clock):
    run_clock = RunClock(clock, 3)
    run_clock.sleep(1)
    run_clock.sleep(2)
    with pytest.raises(RunStopped) as caught:
        run_clock.sleep(0.1)
    assert caught.value.stop.reason == StopReason.RUN_TIME
    assert clock.sleeps == [1, 2]


def test_system_jitter_respects_supplied_range():
    assert system_jitter(0) == 0
    assert all(0 <= system_jitter(2) <= 2 for _ in range(20))
