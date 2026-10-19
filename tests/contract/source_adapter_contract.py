"""어댑터·재생 전송·설정 fixture 세 개만 제공해 재사용한다."""

import pytest

from qello_knowledge.domain.source import AccessStatus, ChangeKeyKind, InvalidResponse, ReadOnlyViolation, SourceRequest
from qello_knowledge.sources.collect import list_all
from qello_knowledge.sources.session import DefaultSourceSession
from tests.unit.sources.conftest import FakeClock


class SourceAdapterContract:
    def session(self, adapter, transport, config):
        return DefaultSourceSession(transport, adapter, config, FakeClock())

    def test_common_item_and_content_types(self, adapter, transport, config):
        session = self.session(adapter, transport, config)
        listing = list_all(adapter, config, session)
        assert listing.complete
        assert len(listing.items) == 5
        for item in listing.items:
            assert item.source_id and item.change_key and item.item_type and item.location
            assert item.source_name == config.name
            assert item.source_kind == adapter.kind
            assert item.url.startswith("https://")
            assert item.access.status == AccessStatus.PROVIDED
            assert item.access.raw == (("visibility", "public"),)
            assert type(item).__module__.startswith("qello_knowledge.domain.")
            content = adapter.fetch_content(session, config, item)
            content = session.finalize_content(content)
            assert content.body and content.version == "v1" and content.location == item.location
            assert content.content_format == "MARKDOWN"
            assert content.content_hash.startswith("sha256:") and content.fetched_at is not None
            assert type(content).__module__.startswith("qello_knowledge.domain.")
        assert type(listing).__module__.startswith("qello_knowledge.domain.")

    @pytest.mark.parametrize("transport", ["no_modified_at"], indirect=True)
    def test_missing_version_and_modified_time_use_content_hash(self, adapter, transport, config):
        session = self.session(adapter, transport, config)
        listing = list_all(adapter, config, session)
        assert len(listing.items) == 5
        for item in listing.items:
            assert item.change_key_kind == ChangeKeyKind.CONTENT_HASH
            content = session.finalize_content(adapter.fetch_content(session, config, item))
            assert item.change_key == content.content_hash
        assert len(transport.requests) == 12

    @pytest.mark.parametrize("transport", ["no_access"], indirect=True)
    def test_missing_permissions_remain_unknown(self, adapter, transport, config):
        listing = list_all(adapter, config, self.session(adapter, transport, config))
        assert len(listing.items) == 5
        assert all(item.access.status == AccessStatus.UNKNOWN and item.access.raw == () for item in listing.items)

    @pytest.mark.parametrize("transport", ["page_overlap"], indirect=True)
    def test_page_overlap_keeps_first_item(self, adapter, transport, config):
        listing = list_all(adapter, config, self.session(adapter, transport, config))
        assert len(listing.items) == len({item.source_id for item in listing.items}) == 5
        assert listing.duplicates_dropped == 1
        assert listing.complete

    def test_no_write_requests(self, adapter, transport, config):
        session = self.session(adapter, transport, config)
        listing = list_all(adapter, config, session)
        for item in listing.items:
            adapter.fetch_content(session, config, item)
        assert transport.requests
        assert {request.method for request in transport.requests} <= {"GET", "HEAD"}
        count = len(transport.requests)
        for method in ("POST", "PATCH", "PUT", "DELETE"):
            with pytest.raises(ReadOnlyViolation):
                session.send(SourceRequest(method, "https://fake.invalid/items"))
        assert len(transport.requests) == count

    @pytest.mark.parametrize("transport", ["invalid_shape"], indirect=True)
    def test_invalid_shape_does_not_prevent_next_item(self, adapter, transport, config):
        session = self.session(adapter, transport, config)
        listing = list_all(adapter, config, session)
        with pytest.raises(InvalidResponse):
            adapter.fetch_content(session, config, listing.items[1])
        assert adapter.fetch_content(session, config, listing.items[2]).source_id == listing.items[2].source_id
