"""자료원은 세션을 통해 읽기 전용 요청만 보낸다."""

from collections.abc import Mapping, Sequence
from typing import Protocol, runtime_checkable

from qello_knowledge.domain.source import (
    ListPage,
    MissingCheck,
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


@runtime_checkable
class MissingItemChecker(Protocol):
    """목록에서 사라진 자료를 단건으로 다시 확인하는 선택 동작(QK-ING-003 FR-030).

    구현하지 않는 종류는 지금처럼 일반 내림이다.
    """

    def check_missing(
        self, session: SourceSession, config: SourceConfig, source_ids: Sequence[str]
    ) -> Mapping[str, MissingCheck]: ...
