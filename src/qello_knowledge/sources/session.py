"""어댑터가 쓰는 유일한 요청 창구. 읽기 전용과 본문 확정을 공통으로 수행한다."""

from dataclasses import replace
from datetime import timedelta
from hashlib import sha256

from qello_knowledge.domain.source import ReadOnlyViolation, SourceContent, SourceRequest, SourceResponse
from qello_knowledge.domain.source_config import SourceConfig
from qello_knowledge.ports.source import SourceAdapter, SourceTransport
from qello_knowledge.sources.clock import Clock
from qello_knowledge.sources.limits import RequestGate


class DefaultSourceSession:
    def __init__(self, transport: SourceTransport, adapter: SourceAdapter, config: SourceConfig, clock: Clock):
        self.transport = transport
        self.adapter = adapter
        self.config = config
        self.clock = clock
        self.requests_made = 0
        self.gate = RequestGate(config.limits, clock)

    def send(self, request: SourceRequest) -> SourceResponse:
        if request.method not in {"GET", "HEAD"}:
            raise ReadOnlyViolation("읽기 전용 요청만 허용한다")
        self.gate.before_request()
        self.requests_made += 1
        response = self.transport.send(request)
        hint = self.adapter.rate_limit_hint(response)
        if hint is not None:
            retry_at = hint.retry_at
            if hint.retry_after_seconds is not None:
                relative_at = self.clock.now() + timedelta(seconds=hint.retry_after_seconds)
                retry_at = max(retry_at, relative_at) if retry_at is not None else relative_at
            self.gate.apply_hint(replace(hint, retry_after_seconds=None, retry_at=retry_at))
        return response

    def finalize_content(self, content: SourceContent) -> SourceContent:
        return replace(
            content,
            content_hash="sha256:" + sha256(content.body.encode("utf-8")).hexdigest(),
            fetched_at=self.clock.now(),
        )
