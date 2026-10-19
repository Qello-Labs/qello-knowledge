from dataclasses import FrozenInstanceError, is_dataclass, replace
from datetime import UTC, datetime

import pytest

from qello_knowledge.domain import source, source_config
from qello_knowledge.domain.source import (
    AccessInfo,
    AccessStatus,
    ChangeKeyKind,
    ContentFormat,
    SourceContent,
    SourceItem,
    SourceRequest,
)


def item(**changes):
    values = dict(
        source_name="docs",
        source_kind="fake",
        source_id="a",
        url="https://fake.invalid/a",
        change_key="v1",
        change_key_kind=ChangeKeyKind.VERSION,
        version="v1",
        modified_at=None,
        item_type="markdown_file",
        title=None,
        location="a.md",
        size_bytes=None,
        access=AccessInfo(AccessStatus.UNKNOWN),
        origin_state=None,
    )
    return SourceItem(**(values | changes))


@pytest.mark.parametrize(
    "changes",
    [
        dict(source_id=""),
        dict(change_key=""),
        dict(url="http://fake.invalid/a"),
        dict(url="https:///a"),
        dict(modified_at=datetime(2026, 1, 1)),
    ],
)
def test_invalid_identity_location_or_naive_time_rejected(changes):
    with pytest.raises(ValueError):
        item(**changes)


def test_unknown_access_cannot_claim_raw_permissions():
    with pytest.raises(ValueError):
        AccessInfo(AccessStatus.UNKNOWN, (("visibility", "public"),))


def test_content_accepts_unfinalized_time_but_rejects_naive_time():
    content = SourceContent("a", "hello", ContentFormat.TEXT, "v1", "a.md", None)
    with pytest.raises(ValueError):
        replace(content, fetched_at=datetime(2026, 1, 1))
    assert replace(content, fetched_at=datetime(2026, 1, 1, tzinfo=UTC)).fetched_at.tzinfo is UTC


def test_values_are_frozen_and_method_is_preserved_for_session_guard():
    request = SourceRequest("POST", "https://fake.invalid/items")
    assert request.method == "POST"
    with pytest.raises(FrozenInstanceError):
        request.method = "GET"
    with pytest.raises(FrozenInstanceError):
        item().source_id = "b"
    for module in (source, source_config):
        for value in vars(module).values():
            if isinstance(value, type) and is_dataclass(value):
                assert value.__dataclass_params__.frozen


def test_response_headers_are_normalized_and_owned():
    headers = {"Retry-After": "30"}
    response = source.SourceResponse(429, headers, b"body")
    headers["Retry-After"] = "60"
    assert response.headers["retry-after"] == "30"
    with pytest.raises(TypeError):
        response.headers["retry-after"] = "90"
