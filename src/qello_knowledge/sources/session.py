"""어댑터가 쓰는 유일한 요청 창구. 읽기 전용과 본문 확정을 공통으로 수행한다."""

from dataclasses import replace
from hashlib import sha256

from qello_knowledge.domain.source import ReadOnlyViolation, SourceContent, SourceRequest, SourceResponse
from qello_knowledge.domain.source_config import SourceConfig
from qello_knowledge.ports.source import SourceAdapter, SourceTransport
from qello_knowledge.sources.clock import Clock


class DefaultSourceSession:
    def __init__(self, transport: SourceTransport, adapter: SourceAdapter, config: SourceConfig, clock: Clock):
        self.transport = transport
        self.adapter = adapter
        self.config = config
        self.clock = clock
        self.requests_made = 0

    def send(self, request: SourceRequest) -> SourceResponse:
        if request.method not in {"GET", "HEAD"}:
            raise ReadOnlyViolation("읽기 전용 요청만 허용한다")
        self.requests_made += 1
        return self.transport.send(request)

    def finalize_content(self, content: SourceContent) -> SourceContent:
        return replace(
            content,
            content_hash="sha256:" + sha256(content.body.encode("utf-8")).hexdigest(),
            fetched_at=self.clock.now(),
        )
