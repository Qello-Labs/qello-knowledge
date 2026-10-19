"""재시도 지연과 실행 시간 예산. 시각·대기·jitter는 주입한다."""

from collections.abc import Callable
from datetime import datetime
from random import SystemRandom

from qello_knowledge.domain.source import RunStopped, StopInfo, StopReason
from qello_knowledge.domain.source_config import RetryPolicy
from qello_knowledge.sources.clock import Clock

Jitter = Callable[[float], float]


def system_jitter(cap: float) -> float:
    return SystemRandom().uniform(0, cap)


def next_delay(policy: RetryPolicy, attempt: int, jitter: Jitter, retry_at: datetime | None, clock: Clock) -> float:
    if retry_at is not None:
        return max(0.0, (retry_at - clock.now()).total_seconds())
    cap = policy.initial_backoff_seconds
    for _ in range(attempt):
        cap = min(policy.max_backoff_seconds, cap * 2)
        if cap >= policy.max_backoff_seconds:
            break
    return jitter(min(policy.max_backoff_seconds, cap))


class RunClock:
    """게이트 대기와 재시도 대기 모두 실행 예산을 넘기기 전에 멈춘다."""

    def __init__(self, clock: Clock, max_run_seconds: float):
        self._clock = clock
        self._started = clock.monotonic()
        self._maximum = max_run_seconds

    def now(self) -> datetime:
        return self._clock.now()

    def monotonic(self) -> float:
        return self._clock.monotonic()

    def check_available(self, delay: float = 0) -> None:
        if self.monotonic() - self._started + delay > self._maximum:
            raise RunStopped(StopInfo(StopReason.RUN_TIME))

    def sleep(self, seconds: float) -> None:
        self.check_available(seconds)
        self._clock.sleep(seconds)
