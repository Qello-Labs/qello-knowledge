"""자료원 설정 값 객체. 읽기와 검증은 sources.config가 맡는다."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class SourceScope:
    include: tuple[str, ...]
    exclude: tuple[str, ...] = ()
    extra: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class RateLimits:
    max_requests_per_minute: int = 60
    max_requests_per_second: int | None = None
    max_requests_per_run: int = 2000
    max_wait_seconds: float = 300
    max_run_seconds: float = 1800


@dataclass(frozen=True)
class RetryPolicy:
    max_retries: int = 3
    initial_backoff_seconds: float = 1
    max_backoff_seconds: float = 60


@dataclass(frozen=True)
class SourceConfig:
    name: str
    kind: str
    enabled: bool
    auth: str | None = None
    scope: SourceScope = field(default_factory=lambda: SourceScope(()))
    limits: RateLimits = field(default_factory=RateLimits)
    retry: RetryPolicy = field(default_factory=RetryPolicy)
    max_content_bytes: int = 1_000_000
    allowed_hosts: tuple[str, ...] = ()
