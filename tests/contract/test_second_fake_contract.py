from datetime import UTC, datetime
from pathlib import Path

import pytest

from qello_knowledge.adapters.replay import ReplayTransport
from qello_knowledge.domain.source import ChangeKeyKind, OriginState
from qello_knowledge.domain.source_config import SourceConfig, SourceScope
from tests.contract.second_fake import SecondFakeSourceAdapter
from tests.contract.source_adapter_contract import SourceAdapterContract


class TestSecondFakeContract(SourceAdapterContract):
    @pytest.fixture
    def adapter(self):
        return SecondFakeSourceAdapter()

    @pytest.fixture
    def transport(self, request):
        scenario = getattr(request, "param", "basic")
        return ReplayTransport.from_file(Path("tests/fixtures/responses/fake") / f"second_{scenario}.json")

    @pytest.fixture
    def config(self):
        return SourceConfig(
            "second-docs", "second_fake", True, scope=SourceScope(("**/*.md",)), allowed_hosts=("second.invalid",)
        )

    def test_second_payload_preserves_metadata_and_uses_offset_api(self, adapter, transport, config):
        session = self.session(adapter, transport, config)
        page = adapter.list_page(session, config, None)
        first = page.items[0]
        assert page.next_cursor == "3"
        assert first.source_id == "doc-1" and first.location == "guides/1.md"
        assert first.change_key == first.version == "v1" and first.change_key_kind == ChangeKeyKind.VERSION
        assert first.modified_at == datetime(2026, 1, 1, tzinfo=UTC)
        assert first.title == "Guide 1" and first.origin_state == OriginState.ACTIVE
        content = adapter.fetch_content(session, config, first)
        assert content.title == "Guide 1" and content.body == "# Guide 1"
        assert [request.url for request in transport.requests] == [
            "https://second.invalid/records?offset=0&limit=3",
            "https://second.invalid/documents/doc-1",
        ]
