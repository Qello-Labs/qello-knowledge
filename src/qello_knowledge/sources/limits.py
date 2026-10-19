"""미끄러지는 창과 실행당 상한, 원본 한도 중 가장 엄격한 것을 지킨다."""

from collections import deque
from datetime import timedelta

from qello_knowledge.domain.source import RateLimitHint, RunStopped, StopInfo, StopReason
from qello_knowledge.domain.source_config import RateLimits
from qello_knowledge.sources.clock import Clock


class RequestGate:
    def __init__(self, limits: RateLimits, clock: Clock):
        self.limits = limits
        self.clock = clock
        self._windows: list[tuple[float, int, deque[float]]] = [
            (60, limits.max_requests_per_minute, deque()),
        ]
        if limits.max_requests_per_second is not None:
            self._windows.append((1, limits.max_requests_per_second, deque()))
        self._requests = 0
        self._remaining: int | None = None
        self._retry_at = None

    def apply_hint(self, hint: RateLimitHint) -> None:
        """세션이 상대값을 변환한 절대 시각만 받는다."""
        self._remaining = hint.remaining
        self._retry_at = hint.retry_at

    def before_request(self) -> None:
        if self._requests >= self.limits.max_requests_per_run:
            raise RunStopped(StopInfo(StopReason.REQUEST_BUDGET))
        while True:
            now = self.clock.monotonic()
            wall_now = self.clock.now()
            if self._retry_at is not None and self._retry_at <= wall_now:
                self._remaining = None
                self._retry_at = None
            wait = 0.0
            for width, maximum, timestamps in self._windows:
                while timestamps and timestamps[0] <= now - width:
                    timestamps.popleft()
                if len(timestamps) >= maximum:
                    wait = max(wait, timestamps[-maximum] + width - now)
            if self._remaining == 0 and self._retry_at is not None:
                wait = max(wait, (self._retry_at - wall_now).total_seconds())
            if wait > self.limits.max_wait_seconds:
                raise RunStopped(StopInfo(StopReason.WAIT_TOO_LONG, wall_now + timedelta(seconds=wait)))
            if wait <= 0:
                break
            self.clock.sleep(wait)
        for _, _, timestamps in self._windows:
            timestamps.append(now)
        self._requests += 1
        if self._remaining is not None:
            self._remaining = max(0, self._remaining - 1)
