from datetime import UTC, datetime, timedelta

import pytest


class FakeClock:
    def __init__(self):
        self.start = datetime(2026, 1, 1, tzinfo=UTC)
        self.elapsed = 0.0
        self.sleeps = []

    def now(self):
        return self.start + timedelta(seconds=self.elapsed)

    def monotonic(self):
        return self.elapsed

    def sleep(self, seconds):
        assert seconds >= 0
        self.sleeps.append(seconds)
        self.elapsed += seconds


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def jitter():
    return lambda cap: cap / 2
