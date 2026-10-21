"""후속 명세 시험용, 실제 원본 없음. 모든 요청은 주입된 세션을 거친다."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from urllib.parse import quote

from qello_knowledge.domain.source import (
    AccessInfo,
    AccessStatus,
    ChangeKeyKind,
    ContentFormat,
    InvalidResponse,
    ListPage,
    OriginState,
    RateLimitHint,
    ResponseClass,
    SourceContent,
    SourceItem,
    SourceOrigin,
    SourceRequest,
    SourceResponse,
    content_hash,
    default_classify,
    default_rate_limit_hint,
)
from qello_knowledge.domain.source_config import SourceConfig
from qello_knowledge.ports.source import SourceSession


def _object(response: SourceResponse) -> dict:
    try:
        data = json.loads(response.body.decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError
        return data
    except (ValueError, UnicodeError):
        raise InvalidResponse() from None


def _required_string(data: dict, key: str) -> str:
    value = data[key]
    if not isinstance(value, str) or not value.strip():
        raise ValueError
    return value


class FakeSourceAdapter:
    kind = "fake"

    def list_page(self, session: SourceSession, config: SourceConfig, cursor: str | None) -> ListPage:
        data = _object(session.send(SourceRequest("GET", "https://fake.invalid/items?cursor=" + quote(cursor or ""))))
        try:
            if not isinstance(data["items"], list) or not (
                data["next_cursor"] is None or isinstance(data["next_cursor"], str)
            ):
                raise ValueError
            items = tuple(self._item(session, config, row) for row in data["items"])
            raw = data.get("origin")
            origin = SourceOrigin(raw["origin_id"], raw["origin_name"], raw.get("version")) if raw else None
            return ListPage(items, data["next_cursor"], origin=origin)
        except (KeyError, TypeError, ValueError):
            raise InvalidResponse() from None

    def _item(self, session: SourceSession, config: SourceConfig, row: dict) -> SourceItem:
        identity = _required_string(row, "id")
        version = row.get("version")
        if version is not None and (not isinstance(version, str) or not version):
            raise ValueError
        modified = row.get("modified_at")
        if modified is not None:
            modified = datetime.fromisoformat(modified)
            if modified.utcoffset() is None:
                raise ValueError
            modified = modified.astimezone(UTC)
        raw_access = row.get("access")
        if raw_access is None:
            access = AccessInfo(AccessStatus.UNKNOWN)
        elif isinstance(raw_access, dict) and all(
            isinstance(k, str) and isinstance(v, str) for k, v in raw_access.items()
        ):
            access = AccessInfo(AccessStatus.PROVIDED, tuple(raw_access.items()))
        else:
            raise ValueError
        location = _required_string(row, "location")
        if version:
            change_key, key_kind = version, ChangeKeyKind.VERSION
        elif modified:
            change_key, key_kind = modified.isoformat(), ChangeKeyKind.MODIFIED_AT
        else:
            content = self._fetch(session, identity)
            change_key = content_hash(content.body)
            key_kind = ChangeKeyKind.CONTENT_HASH
        size = row.get("size_bytes")
        if size is not None and (type(size) is not int or size < 0):
            raise ValueError
        title = row.get("title")
        if title is not None and not isinstance(title, str):
            raise ValueError
        state = row.get("origin_state")
        return SourceItem(
            config.name,
            self.kind,
            identity,
            _required_string(row, "url"),
            change_key,
            key_kind,
            version,
            modified,
            _required_string(row, "item_type"),
            title,
            location,
            size,
            access,
            OriginState(state) if state is not None else None,
        )

    def _fetch(self, session: SourceSession, identity: str) -> SourceContent:
        data = _object(session.send(SourceRequest("GET", "https://fake.invalid/items/" + quote(identity, safe=""))))
        try:
            if not isinstance(data["body"], str):
                raise ValueError
            version, title = data["version"], data.get("title")
            if any(value is not None and not isinstance(value, str) for value in (version, title)):
                raise ValueError
            return SourceContent(
                identity,
                data["body"],
                ContentFormat(data["content_format"]),
                version,
                _required_string(data, "location"),
                title,
            )
        except (KeyError, TypeError, ValueError):
            raise InvalidResponse() from None

    def fetch_content(self, session: SourceSession, config: SourceConfig, item: SourceItem) -> SourceContent:
        return self._fetch(session, item.source_id)

    def classify(self, response: SourceResponse) -> ResponseClass:
        return default_classify(response)

    def rate_limit_hint(self, response: SourceResponse) -> RateLimitHint | None:
        return default_rate_limit_hint(response)
