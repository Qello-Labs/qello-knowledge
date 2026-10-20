"""어댑터·재생 전송·설정 fixture 세 개만 제공해 재사용한다."""

from dataclasses import dataclass
from pathlib import Path

import pytest

from qello_knowledge.adapters.replay import ReplayTransport
from qello_knowledge.domain.source import (
    AccessStatus,
    ChangeKeyKind,
    ContentFormat,
    InvalidResponse,
    ReadOnlyViolation,
    SourceRequest,
)
from qello_knowledge.sources.collect import list_all
from qello_knowledge.sources.session import DefaultSourceSession
from tests.unit.sources.conftest import FakeClock


@dataclass(frozen=True)
class ContractExpectations:
    item_count: int
    content_version: str
    access_raw: tuple[tuple[str, str], ...]
    content_format: ContentFormat
    write_probe_url: str
    scenarios: dict
    content_hash_requests: int | None


def scenario_transport(expected, name, basic):
    scenario = expected.scenarios[name]
    if scenario is None:
        return basic
    if isinstance(scenario, Path):
        return ReplayTransport.from_file(scenario)
    return scenario.transport()


class SourceAdapterContract:
    def session(self, adapter, transport, config):
        return DefaultSourceSession(transport, adapter, config, FakeClock())

    def test_common_item_and_content_types(self, adapter, transport, config, expected):
        session = self.session(adapter, transport, config)
        listing = list_all(adapter, config, session)
        assert listing.complete
        assert len(listing.items) == expected.item_count
        for item in listing.items:
            assert item.source_id and item.change_key and item.item_type and item.location
            assert item.source_name == config.name
            assert item.source_kind == adapter.kind
            assert item.url.startswith("https://")
            assert item.access.status == AccessStatus.PROVIDED
            assert item.access.raw == expected.access_raw
            assert type(item).__module__.startswith("qello_knowledge.domain.")
            content = adapter.fetch_content(session, config, item)
            content = session.finalize_content(content)
            assert content.body and content.version == expected.content_version and content.location == item.location
            assert content.content_format == expected.content_format
            assert content.content_hash.startswith("sha256:") and content.fetched_at is not None
            assert type(content).__module__.startswith("qello_knowledge.domain.")
        assert type(listing).__module__.startswith("qello_knowledge.domain.")

    def test_missing_version_and_modified_time_use_content_hash(self, adapter, transport, config, expected):
        transport = scenario_transport(expected, "no_modified_at", transport)
        session = self.session(adapter, transport, config)
        listing = list_all(adapter, config, session)
        assert len(listing.items) == expected.item_count
        for item in listing.items:
            if expected.scenarios["no_modified_at"] is None:
                assert item.change_key_kind == ChangeKeyKind.VERSION and item.change_key
                continue
            assert item.change_key_kind == ChangeKeyKind.CONTENT_HASH
            content = session.finalize_content(adapter.fetch_content(session, config, item))
            assert item.change_key == content.content_hash
        if expected.content_hash_requests is not None:
            assert len(transport.requests) == expected.content_hash_requests

    def test_missing_permissions_remain_unknown(self, adapter, transport, config, expected):
        transport = scenario_transport(expected, "no_access", transport)
        listing = list_all(adapter, config, self.session(adapter, transport, config))
        assert len(listing.items) == expected.item_count
        assert all(item.access.status == AccessStatus.UNKNOWN and item.access.raw == () for item in listing.items)

    def test_page_overlap_keeps_first_item(self, adapter, transport, config, expected):
        transport = scenario_transport(expected, "page_overlap", transport)
        listing = list_all(adapter, config, self.session(adapter, transport, config))
        assert len(listing.items) == len({item.source_id for item in listing.items}) == expected.item_count
        assert listing.duplicates_dropped == (0 if expected.scenarios["page_overlap"] is None else 1)
        assert listing.complete

    def test_no_write_requests(self, adapter, transport, config, expected):
        session = self.session(adapter, transport, config)
        listing = list_all(adapter, config, session)
        for item in listing.items:
            adapter.fetch_content(session, config, item)
        assert transport.requests
        assert {request.method for request in transport.requests} <= {"GET", "HEAD"}
        count = len(transport.requests)
        for method in ("POST", "PATCH", "PUT", "DELETE"):
            with pytest.raises(ReadOnlyViolation):
                session.send(SourceRequest(method, expected.write_probe_url))
        assert len(transport.requests) == count

    def test_invalid_shape_does_not_prevent_next_item(self, adapter, transport, config, expected):
        transport = scenario_transport(expected, "invalid_shape", transport)
        session = self.session(adapter, transport, config)
        listing = list_all(adapter, config, session)
        with pytest.raises(InvalidResponse):
            adapter.fetch_content(session, config, listing.items[1])
        assert adapter.fetch_content(session, config, listing.items[2]).source_id == listing.items[2].source_id
