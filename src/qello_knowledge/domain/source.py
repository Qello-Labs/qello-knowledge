"""자료원 경계의 불변 값 객체. 원본 본문과 헤더는 요약 결과에 넣지 않는다."""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from enum import StrEnum
from types import MappingProxyType
from urllib.parse import urlsplit


class AccessStatus(StrEnum):
    PROVIDED = "PROVIDED"
    UNKNOWN = "UNKNOWN"


class OriginState(StrEnum):
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"
    DELETED = "DELETED"


class ChangeKeyKind(StrEnum):
    VERSION = "VERSION"
    MODIFIED_AT = "MODIFIED_AT"
    CONTENT_HASH = "CONTENT_HASH"


class ContentFormat(StrEnum):
    MARKDOWN = "MARKDOWN"
    CODE = "CODE"
    JSON = "JSON"
    TEXT = "TEXT"


class FailureType(StrEnum):
    RATE_LIMITED = "RATE_LIMITED"
    SERVER_ERROR = "SERVER_ERROR"
    TIMEOUT = "TIMEOUT"
    CONNECTION = "CONNECTION"
    NOT_FOUND = "NOT_FOUND"
    ACCESS_DENIED = "ACCESS_DENIED"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    SIZE_EXCEEDED = "SIZE_EXCEEDED"
    REDIRECT_BLOCKED = "REDIRECT_BLOCKED"
    AUTH_FAILED = "AUTH_FAILED"


class ItemStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    TRANSIENT_EXHAUSTED = "TRANSIENT_EXHAUSTED"
    PERMANENT_FAILED = "PERMANENT_FAILED"
    SKIPPED = "SKIPPED"


class StopReason(StrEnum):
    AUTH_FAILED = "AUTH_FAILED"
    WAIT_TOO_LONG = "WAIT_TOO_LONG"
    REQUEST_BUDGET = "REQUEST_BUDGET"
    RUN_TIME = "RUN_TIME"


class ResponseOutcome(StrEnum):
    OK = "OK"
    TRANSIENT = "TRANSIENT"
    PERMANENT = "PERMANENT"
    AUTH = "AUTH"


def _aware(value: datetime | None) -> None:
    if value is not None and (value.tzinfo is None or value.utcoffset() is None):
        raise ValueError("시간대 있는 시각이 필요하다")


@dataclass(frozen=True)
class AccessInfo:
    status: AccessStatus
    raw: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if self.status == AccessStatus.UNKNOWN and self.raw:
            raise ValueError("미확인 권한에는 원본 권한 값이 없어야 한다")


@dataclass(frozen=True)
class SourceItem:
    source_name: str
    source_kind: str
    source_id: str
    url: str
    change_key: str
    change_key_kind: ChangeKeyKind
    version: str | None
    modified_at: datetime | None
    item_type: str
    title: str | None
    location: str
    size_bytes: int | None
    access: AccessInfo
    origin_state: OriginState | None

    def __post_init__(self) -> None:
        if not self.source_id.strip() or not self.change_key.strip():
            raise ValueError("원본 식별자와 변경 판별값이 필요하다")
        parts = urlsplit(self.url)
        if parts.scheme != "https" or not parts.hostname:
            raise ValueError("원본 링크는 HTTPS여야 한다")
        _aware(self.modified_at)


@dataclass(frozen=True)
class SourceContent:
    source_id: str
    body: str = field(repr=False)
    content_format: ContentFormat
    version: str | None
    location: str
    title: str | None
    content_hash: str = ""
    fetched_at: datetime | None = None

    def __post_init__(self) -> None:
        _aware(self.fetched_at)


@dataclass(frozen=True)
class ListPage:
    items: tuple[SourceItem, ...]
    next_cursor: str | None


@dataclass(frozen=True)
class StopInfo:
    reason: StopReason
    retry_at: datetime | None = None

    def __post_init__(self) -> None:
        _aware(self.retry_at)


@dataclass(frozen=True)
class Listing:
    items: tuple[SourceItem, ...]
    duplicates_dropped: int = 0
    complete: bool = True
    excluded: int = 0
    stop: StopInfo | None = None


@dataclass(frozen=True)
class SourceRequest:
    method: str
    url: str = field(repr=False)
    headers: Mapping[str, str] = field(default_factory=dict, repr=False)
    max_bytes: int | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "headers", MappingProxyType(dict(self.headers)))


@dataclass(frozen=True)
class SourceResponse:
    status: int
    headers: Mapping[str, str] = field(default_factory=dict, repr=False)
    body: bytes = field(default=b"", repr=False)
    truncated: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "headers", MappingProxyType({k.lower(): v for k, v in self.headers.items()}))


@dataclass(frozen=True)
class ResponseClass:
    outcome: ResponseOutcome
    failure: FailureType | None = None


@dataclass(frozen=True)
class RateLimitHint:
    remaining: int | None = None
    retry_after_seconds: float | None = None
    retry_at: datetime | None = None

    def __post_init__(self) -> None:
        _aware(self.retry_at)


@dataclass(frozen=True)
class ItemOutcome:
    source_id: str
    status: ItemStatus
    retries: int = 0
    failure: FailureType | None = None
    http_status: int | None = None


@dataclass(frozen=True)
class FetchResult:
    source_name: str
    started_at: datetime
    finished_at: datetime
    requests_made: int
    listing_complete: bool
    processed: int
    failed: int
    remaining: int
    stop: StopInfo | None
    items: tuple[ItemOutcome, ...]
    contents: tuple[SourceContent, ...] = field(default=(), repr=False)

    def __post_init__(self) -> None:
        _aware(self.started_at)
        _aware(self.finished_at)

    def to_dict(self) -> dict:
        """본문·헤더·원본 URL을 제외한 JSON 요약만 만든다."""
        return {
            "source_name": self.source_name,
            "started_at": self.started_at.isoformat(),
            "finished_at": self.finished_at.isoformat(),
            "requests_made": self.requests_made,
            "listing_complete": self.listing_complete,
            "processed": self.processed,
            "failed": self.failed,
            "remaining": self.remaining,
            "stop": None
            if self.stop is None
            else {
                "reason": self.stop.reason.value,
                "retry_at": self.stop.retry_at.isoformat() if self.stop.retry_at is not None else None,
            },
            "items": [
                {
                    "source_id": item.source_id,
                    "status": item.status.value,
                    "retries": item.retries,
                    "failure": item.failure.value if item.failure is not None else None,
                    "http_status": item.http_status,
                }
                for item in self.items
            ],
        }


class TransportError(Exception):
    def __init__(self, kind: str):
        if kind not in {"timeout", "connection"}:
            raise ValueError("지원하지 않는 전송 오류")
        self.kind = kind
        super().__init__(kind)


class SourceFailure(Exception):
    def __init__(self, failure: FailureType, http_status: int | None = None):
        self.failure = failure
        self.http_status = http_status
        super().__init__(failure.value)


class InvalidResponse(SourceFailure):
    def __init__(self):
        super().__init__(FailureType.INVALID_RESPONSE)


class RunStopped(Exception):
    def __init__(self, stop: StopInfo):
        self.stop = stop
        super().__init__(stop.reason.value)


class ReadOnlyViolation(Exception):
    """어댑터가 원본에 쓰려고 한 결함. 자료별 실패로 삼키지 않는다."""


class HostNotAllowed(Exception):
    """어댑터가 설정 밖 주소를 만든 결함. 자료별 실패로 삼키지 않는다."""


def default_rate_limit_hint(response: SourceResponse) -> RateLimitHint | None:
    """Retry-After 원본 값만 읽는다. 현재 시각은 세션에서만 계산한다."""
    value = response.headers.get("retry-after")
    if value is None:
        return None
    value = value.strip()
    if re.fullmatch(r"[0-9]+", value):
        seconds = float(value)
        if math.isfinite(seconds):
            return RateLimitHint(remaining=0, retry_after_seconds=seconds)
        return None
    try:
        absolute = parsedate_to_datetime(value)
        if absolute.tzinfo is None:
            absolute = absolute.replace(tzinfo=UTC)
        return RateLimitHint(remaining=0, retry_at=absolute.astimezone(UTC))
    except (ValueError, TypeError, OverflowError):
        return None


def default_classify(response_or_error: SourceResponse | TransportError) -> ResponseClass:
    """원본 고유 규칙이 없을 때의 실패 분류(research R-07)."""
    if isinstance(response_or_error, TransportError):
        failure = FailureType.TIMEOUT if response_or_error.kind == "timeout" else FailureType.CONNECTION
        return ResponseClass(ResponseOutcome.TRANSIENT, failure)
    status = response_or_error.status
    if 200 <= status < 300:
        return ResponseClass(ResponseOutcome.OK)
    if status == 429:
        return ResponseClass(ResponseOutcome.TRANSIENT, FailureType.RATE_LIMITED)
    if status in {500, 502, 503, 504}:
        return ResponseClass(ResponseOutcome.TRANSIENT, FailureType.SERVER_ERROR)
    if status == 401:
        return ResponseClass(ResponseOutcome.AUTH, FailureType.AUTH_FAILED)
    failure = {403: FailureType.ACCESS_DENIED, 404: FailureType.NOT_FOUND, 410: FailureType.NOT_FOUND}.get(
        status, FailureType.INVALID_RESPONSE
    )
    return ResponseClass(ResponseOutcome.PERMANENT, failure)
