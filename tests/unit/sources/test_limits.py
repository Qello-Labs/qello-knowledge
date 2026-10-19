from datetime import timedelta

import pytest

from qello_knowledge.domain.source import RateLimitHint, RunStopped, StopReason
from qello_knowledge.domain.source_config import RateLimits
from qello_knowledge.sources.limits import RequestGate


@pytest.mark.parametrize(("per_minute", "per_second"), [(60, None), (60, 3), (4, 2)])
def test_every_sliding_window_stays_within_limit(clock, per_minute, per_second):
    gate = RequestGate(RateLimits(max_requests_per_minute=per_minute, max_requests_per_second=per_second), clock)
    times = []
    for _ in range(200):
        gate.before_request()
        times.append(clock.monotonic())
    for end in times:
        assert sum(end - 60 < t <= end for t in times) <= per_minute
        if per_second is not None:
            assert sum(end - 1 < t <= end for t in times) <= per_second


@pytest.mark.parametrize(("origin_wait", "expected_wait"), [(30, 60), (90, 90)])
def test_stricter_origin_or_configured_limit_wins(clock, origin_wait, expected_wait):
    gate = RequestGate(RateLimits(max_requests_per_minute=1), clock)
    gate.before_request()
    gate.apply_hint(RateLimitHint(remaining=0, retry_at=clock.now() + timedelta(seconds=origin_wait)))
    gate.before_request()
    assert clock.sleeps == [expected_wait]


def test_wait_equal_to_maximum_is_allowed_and_expired_hint_is_not_repeated(clock):
    gate = RequestGate(RateLimits(max_wait_seconds=30), clock)
    gate.apply_hint(RateLimitHint(remaining=0, retry_at=clock.now() + timedelta(seconds=30)))
    gate.before_request()
    gate.before_request()
    assert clock.sleeps == [30]


def test_long_wait_stops_without_sleeping_and_preserves_retry_time(clock):
    gate = RequestGate(RateLimits(max_wait_seconds=30), clock)
    retry_at = clock.now() + timedelta(seconds=31)
    gate.apply_hint(RateLimitHint(remaining=0, retry_at=retry_at))
    with pytest.raises(RunStopped) as caught:
        gate.before_request()
    assert caught.value.stop.reason == StopReason.WAIT_TOO_LONG
    assert caught.value.stop.retry_at == retry_at
    assert not clock.sleeps


def test_configured_window_stop_reports_its_retry_time(clock):
    gate = RequestGate(RateLimits(max_requests_per_minute=1, max_wait_seconds=0), clock)
    gate.before_request()
    with pytest.raises(RunStopped) as caught:
        gate.before_request()
    assert caught.value.stop.reason == StopReason.WAIT_TOO_LONG
    assert caught.value.stop.retry_at == clock.now() + timedelta(seconds=60)


def test_request_budget_stops_before_any_additional_wait(clock):
    gate = RequestGate(RateLimits(max_requests_per_minute=1, max_requests_per_run=1), clock)
    gate.before_request()
    with pytest.raises(RunStopped) as caught:
        gate.before_request()
    assert caught.value.stop.reason == StopReason.REQUEST_BUDGET
    assert caught.value.stop.retry_at is None
    assert not clock.sleeps


def test_origin_remaining_budget_is_consumed_even_without_another_hint(clock):
    gate = RequestGate(RateLimits(), clock)
    gate.apply_hint(RateLimitHint(remaining=2, retry_at=clock.now() + timedelta(seconds=20)))
    gate.before_request()
    gate.before_request()
    assert not clock.sleeps
    gate.before_request()
    assert clock.sleeps == [20]


def test_sliding_window_does_not_reset_all_requests_at_a_minute_boundary(clock):
    gate = RequestGate(RateLimits(max_requests_per_minute=2), clock)
    times = []
    gate.before_request()
    times.append(clock.monotonic())
    clock.sleep(59)
    for _ in range(3):
        gate.before_request()
        times.append(clock.monotonic())
    assert times == [0, 59, 60, 119]
