"""자료원은 세션을 통해 읽기 전용 요청만 보낸다."""

from typing import Protocol

from qello_knowledge.domain.source import (
    ListPage,
    RateLimitHint,
    ResponseClass,
    SourceContent,
    SourceItem,
    SourceRequest,
    SourceResponse,
)
from qello_knowledge.domain.source_config import SourceConfig


class SourceSession(Protocol):
    def send(self, request: SourceRequest) -> SourceResponse: ...


class SourceTransport(Protocol):
    def send(self, request: SourceRequest) -> SourceResponse: ...


class SourceAdapter(Protocol):
    kind: str

    def list_page(self, session: SourceSession, config: SourceConfig, cursor: str | None) -> ListPage: ...
    def fetch_content(self, session: SourceSession, config: SourceConfig, item: SourceItem) -> SourceContent: ...
    def classify(self, response: SourceResponse) -> ResponseClass: ...
    def rate_limit_hint(self, response: SourceResponse) -> RateLimitHint | None: ...
