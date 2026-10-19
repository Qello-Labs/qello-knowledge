from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from qello_knowledge.adapters.fake import FakeSourceAdapter
from qello_knowledge.adapters.replay import ReplayTransport
from qello_knowledge.domain.source import RateLimitHint, ReadOnlyViolation, RunStopped, SourceRequest, StopReason
from qello_knowledge.domain.source_config import RateLimits, SourceConfig, SourceScope
from qello_knowledge.sources.collect import list_all
from qello_knowledge.sources.session import DefaultSourceSession


class TimedTransport:
    def __init__(self, replay, clock):
        self.replay = replay
        self.clock = clock
        self.times = []

    def send(self, request):
        self.times.append(self.clock.monotonic())
        return self.replay.send(request)


def config(**changes):
    original = SourceConfig("docs", "fake", True, scope=SourceScope(("**/*.md",)))
    return replace(original, **changes)


def test_two_hundred_items_respect_every_minute_window(clock):
    adapter = FakeSourceAdapter()
    replay = ReplayTransport.from_file(Path("tests/fixtures/responses/fake/many_items.json"))
    transport = TimedTransport(replay, clock)
    cfg = config()
    session = DefaultSourceSession(transport, adapter, cfg, clock)
    listing = list_all(adapter, cfg, session)
    contents = [session.finalize_content(adapter.fetch_content(session, cfg, item)) for item in listing.items]
    assert len(contents) == 200
    assert session.requests_made == len(replay.requests) == 201
    for end in transport.times:
        assert sum(end - 60 < t <= end for t in transport.times) <= 60
    assert clock.sleeps == [60, 60, 60]


@pytest.mark.parametrize(
    ("scenario", "wait", "stopped"), [("rate_limited", 30, False), ("rate_limited_long", 3600, True)]
)
def test_origin_hint_is_applied_before_any_next_request(clock, scenario, wait, stopped):
    adapter = FakeSourceAdapter()
    transport = ReplayTransport.from_file(Path(f"tests/fixtures/responses/fake/{scenario}.json"))
    session = DefaultSourceSession(transport, adapter, config(), clock)
    request = SourceRequest("GET", "https://fake.invalid/items/1")
    retry_at = clock.now() + timedelta(seconds=wait)
    if stopped:
        with pytest.raises(RunStopped) as caught:
            session.send(request)
        assert caught.value.stop.reason == StopReason.WAIT_TOO_LONG
        assert caught.value.stop.retry_at == retry_at
        assert session.requests_made == len(transport.requests) == 1
        assert not clock.sleeps
    else:
        assert session.send(request).status == 200
        assert clock.now() == retry_at
        assert clock.sleeps == [30]
        assert session.requests_made == len(transport.requests) == 2
        assert session.retries_made == 1


@pytest.mark.parametrize(("absolute_wait", "expected_wait"), [(10, 30), (50, 50)])
def test_session_resolves_relative_and_absolute_hint_using_injected_clock(clock, absolute_wait, expected_wait):
    class BothHints(FakeSourceAdapter):
        def rate_limit_hint(self, response):
            return RateLimitHint(
                remaining=0, retry_after_seconds=30, retry_at=clock.start + timedelta(seconds=absolute_wait)
            )

    transport = ReplayTransport(
        [
            dict(
                method="GET",
                url="https://fake.invalid/items/1",
                responses=[
                    dict(status=200, headers={}, body="one"),
                    dict(status=200, headers={}, body="two"),
                ],
            )
        ]
    )
    session = DefaultSourceSession(transport, BothHints(), config(), clock)
    request = SourceRequest("GET", "https://fake.invalid/items/1")
    session.send(request)
    session.send(request)
    assert clock.sleeps == [expected_wait]


def test_budget_counts_actual_requests_and_read_only_guard_runs_before_gate(clock):
    transport = ReplayTransport(
        [
            dict(
                method="GET",
                url="https://fake.invalid/a",
                responses=[
                    dict(status=200, headers={}, body="ok"),
                ],
            )
        ]
    )
    session = DefaultSourceSession(
        transport, FakeSourceAdapter(), config(limits=RateLimits(max_requests_per_run=1)), clock
    )
    session.send(SourceRequest("GET", "https://fake.invalid/a"))
    with pytest.raises(RunStopped) as caught:
        session.send(SourceRequest("GET", "https://fake.invalid/a"))
    assert caught.value.stop.reason == StopReason.REQUEST_BUDGET
    with pytest.raises(ReadOnlyViolation):
        session.send(SourceRequest("POST", "https://fake.invalid/a"))
    assert session.requests_made == len(transport.requests) == 1
