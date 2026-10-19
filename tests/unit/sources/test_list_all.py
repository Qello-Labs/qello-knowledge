from pathlib import Path

from qello_knowledge.adapters.fake import FakeSourceAdapter
from qello_knowledge.adapters.replay import ReplayTransport
from qello_knowledge.domain.source_config import SourceConfig, SourceScope
from qello_knowledge.sources.collect import list_all
from qello_knowledge.sources.session import DefaultSourceSession


def test_all_pages_deduplicated_before_scope_filter(clock):
    adapter = FakeSourceAdapter()
    transport = ReplayTransport.from_file(Path("tests/fixtures/responses/fake/page_overlap.json"))
    config = SourceConfig(
        "docs", "fake", True, scope=SourceScope(("docs/**",), ("docs/2.md",)), allowed_hosts=("fake.invalid",)
    )
    session = DefaultSourceSession(transport, adapter, config, clock)
    listing = list_all(adapter, config, session)
    assert [item.source_id for item in listing.items] == ["1", "3", "4", "5"]
    assert listing.complete and listing.excluded == 1 and listing.duplicates_dropped == 1
    assert session.requests_made == 2


def test_items_outside_include_are_excluded(clock):
    adapter = FakeSourceAdapter()
    transport = ReplayTransport.from_file(Path("tests/fixtures/responses/fake/basic.json"))
    config = SourceConfig("docs", "fake", True, scope=SourceScope(("elsewhere/**",)), allowed_hosts=("fake.invalid",))
    listing = list_all(adapter, config, DefaultSourceSession(transport, adapter, config, clock))
    assert listing.items == () and listing.excluded == 5
