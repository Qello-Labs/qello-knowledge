"""offset 페이지와 별도 문서 봉투를 쓰는 시험 전용 자료원. 등록 목록에 추가하지 않는다."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
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
    SourceRequest,
    SourceResponse,
    default_classify,
    default_rate_limit_hint,
)
from qello_knowledge.domain.source_config import SourceConfig
from qello_knowledge.ports.source import SourceSession


def _object(response: SourceResponse) -> dict:
    try:
        result = json.loads(response.body.decode("utf-8"))
        if not isinstance(result, dict):
            raise ValueError
        return result
    except (ValueError, UnicodeError):
        raise InvalidResponse() from None


def _text(data: dict, key: str) -> str:
    value = data[key]
    if not isinstance(value, str) or not value.strip():
        raise ValueError
    return value


def _optional_text(data: dict, key: str) -> str | None:
    value = data.get(key)
    if value is not None and not isinstance(value, str):
        raise ValueError
    return value


class SecondFakeSourceAdapter:
    kind = "second_fake"

    def list_page(self, session: SourceSession, config: SourceConfig, cursor: str | None) -> ListPage:
        try:
            offset = int(cursor) if cursor is not None else 0
            data = _object(
                session.send(SourceRequest("GET", f"https://second.invalid/records?offset={offset}&limit=3"))
            )
            following = data["next_offset"]
            if following is not None and (type(following) is not int or following <= offset):
                raise ValueError
            if not isinstance(data["records"], list):
                raise ValueError
            items = tuple(self._item(session, config, row) for row in data["records"])
            return ListPage(items, str(following) if following is not None else None)
        except (KeyError, TypeError, ValueError):
            raise InvalidResponse() from None

    def _item(self, session: SourceSession, config: SourceConfig, row: dict) -> SourceItem:
        identity = _text(row, "key")
        version = _optional_text(row, "revision")
        changed = _optional_text(row, "changed")
        modified_at = datetime.fromisoformat(changed) if changed is not None else None
        if modified_at is not None:
            if modified_at.utcoffset() is None:
                raise ValueError
            modified_at = modified_at.astimezone(UTC)
        if version:
            change_key, change_kind = version, ChangeKeyKind.VERSION
        elif modified_at is not None:
            change_key, change_kind = modified_at.isoformat(), ChangeKeyKind.MODIFIED_AT
        else:
            content = self._document(session, identity)
            change_key = "sha256:" + sha256(content.body.encode("utf-8")).hexdigest()
            change_kind = ChangeKeyKind.CONTENT_HASH
        permissions = row.get("permissions")
        if permissions is None:
            access = AccessInfo(AccessStatus.UNKNOWN)
        else:
            if not isinstance(permissions, list) or any(
                not isinstance(pair, list) or len(pair) != 2 or any(not isinstance(v, str) for v in pair)
                for pair in permissions
            ):
                raise ValueError
            access = AccessInfo(AccessStatus.PROVIDED, tuple((pair[0], pair[1]) for pair in permissions))
        size = row.get("bytes")
        if size is not None and (type(size) is not int or size < 0):
            raise ValueError
        state = _optional_text(row, "state")
        return SourceItem(
            source_name=config.name,
            source_kind=self.kind,
            source_id=identity,
            url=_text(row, "web"),
            change_key=change_key,
            change_key_kind=change_kind,
            version=version,
            modified_at=modified_at,
            item_type=_text(row, "category"),
            title=_optional_text(row, "heading"),
            location=_text(row, "path"),
            size_bytes=size,
            access=access,
            origin_state=OriginState(state) if state is not None else None,
        )

    def _document(self, session: SourceSession, identity: str) -> SourceContent:
        response = session.send(SourceRequest("GET", "https://second.invalid/documents/" + quote(identity, safe="")))
        try:
            data = _object(response)["document"]
            if not isinstance(data, dict) or not isinstance(data["text"], str):
                raise ValueError
            content_format = {
                "md": ContentFormat.MARKDOWN,
                "plain": ContentFormat.TEXT,
                "code": ContentFormat.CODE,
                "json": ContentFormat.JSON,
            }[_text(data, "syntax")]
            return SourceContent(
                source_id=identity,
                body=data["text"],
                content_format=content_format,
                version=_optional_text(data, "revision"),
                location=_text(data, "path"),
                title=_optional_text(data, "heading"),
            )
        except (KeyError, TypeError, ValueError):
            raise InvalidResponse() from None

    def fetch_content(self, session: SourceSession, config: SourceConfig, item: SourceItem) -> SourceContent:
        return self._document(session, item.source_id)

    def classify(self, response: SourceResponse) -> ResponseClass:
        return default_classify(response)

    def rate_limit_hint(self, response: SourceResponse) -> RateLimitHint | None:
        return default_rate_limit_hint(response)
