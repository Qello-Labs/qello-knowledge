"""읽기 전용·한도·재시도·리다이렉트·크기 상한을 적용하는 유일한 요청 창구."""

from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
from urllib.parse import urljoin, urlsplit

from qello_knowledge.domain.source import (
    FailureType,
    RateLimitHint,
    ReadOnlyViolation,
    ResponseOutcome,
    RunStopped,
    SourceContent,
    SourceFailure,
    SourceRequest,
    SourceResponse,
    StopInfo,
    StopReason,
    TransportError,
    default_classify,
)
from qello_knowledge.domain.source_config import SourceConfig
from qello_knowledge.ports.source import SourceAdapter, SourceTransport
from qello_knowledge.sources.clock import Clock
from qello_knowledge.sources.limits import RequestGate
from qello_knowledge.sources.retry import Jitter, RunClock, next_delay, system_jitter


class DefaultSourceSession:
    def __init__(
        self,
        transport: SourceTransport,
        adapter: SourceAdapter,
        config: SourceConfig,
        clock: Clock,
        *,
        jitter: Jitter = system_jitter,
    ):
        self.transport = transport
        self.adapter = adapter
        self.config = config
        self.clock = RunClock(clock, config.limits.max_run_seconds)
        self.jitter = jitter
        self.started_at = self.clock.now()
        self.requests_made = 0
        self.retries_made = 0
        self.last_http_status: int | None = None
        self.stop: StopInfo | None = None
        self.gate = RequestGate(config.limits, self.clock)

    def send(self, request: SourceRequest) -> SourceResponse:
        if request.method not in {"GET", "HEAD"}:
            raise ReadOnlyViolation("읽기 전용 요청만 허용한다")
        if self.stop is not None:
            raise RunStopped(self.stop)
        try:
            return self._send(request)
        except RunStopped as stopped:
            self.stop = stopped.stop
            raise

    def _hint(self, response: SourceResponse) -> RateLimitHint | None:
        hint = self.adapter.rate_limit_hint(response)
        if hint is not None:
            retry_at = hint.retry_at
            if hint.retry_after_seconds is not None:
                relative_at = self.clock.now() + timedelta(seconds=hint.retry_after_seconds)
                retry_at = max(retry_at, relative_at) if retry_at is not None else relative_at
            hint = replace(hint, retry_after_seconds=None, retry_at=retry_at)
            self.gate.apply_hint(hint)
        return hint

    def _send(self, request: SourceRequest) -> SourceResponse:
        request = replace(request, max_bytes=self.config.max_content_bytes)
        attempt = redirects = 0
        retry_pending = False
        while True:
            self.clock.check_available()
            self.gate.before_request()
            self.clock.check_available()
            self.requests_made += 1
            self.retries_made += retry_pending
            self.last_http_status = None
            hint = None
            try:
                response = self.transport.send(request)
            except TransportError as error:
                classification = default_classify(error)
            else:
                self.last_http_status = response.status
                hint = self._hint(response)
                if response.truncated:
                    raise SourceFailure(FailureType.SIZE_EXCEEDED, response.status)
                if 300 <= response.status < 400:
                    location = response.headers.get("location")
                    try:
                        target = urljoin(request.url, location) if location else ""
                        host = urlsplit(target).hostname
                    except ValueError:
                        host = None
                    if host not in self.config.allowed_hosts or redirects >= 3:
                        raise SourceFailure(FailureType.REDIRECT_BLOCKED, response.status)
                    request = replace(request, url=target)
                    redirects += 1
                    retry_pending = False
                    continue
                classification = self.adapter.classify(response)
                if classification.outcome == ResponseOutcome.OK:
                    return response
            if classification.outcome == ResponseOutcome.AUTH:
                raise RunStopped(StopInfo(StopReason.AUTH_FAILED))
            failure = classification.failure or FailureType.INVALID_RESPONSE
            if classification.outcome != ResponseOutcome.TRANSIENT or attempt >= self.config.retry.max_retries:
                raise SourceFailure(failure, self.last_http_status)
            if self.requests_made >= self.config.limits.max_requests_per_run:
                raise RunStopped(StopInfo(StopReason.REQUEST_BUDGET))
            retry_at = hint.retry_at if hint is not None else None
            delay = next_delay(self.config.retry, attempt, self.jitter, retry_at, self.clock)
            if delay > self.config.limits.max_wait_seconds:
                raise RunStopped(StopInfo(StopReason.WAIT_TOO_LONG, self.clock.now() + timedelta(seconds=delay)))
            if delay > 0:
                self.clock.sleep(delay)
            attempt += 1
            retry_pending = True

    def finalize_content(self, content: SourceContent) -> SourceContent:
        return replace(
            content,
            content_hash="sha256:" + sha256(content.body.encode("utf-8")).hexdigest(),
            fetched_at=self.clock.now(),
        )
