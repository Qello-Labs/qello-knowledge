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


def test_incomplete_page_keeps_filtered_deduplicated_items_and_stops(clock):
    from dataclasses import replace

    from qello_knowledge.domain.source import ListPage

    adapter = FakeSourceAdapter()
    transport = ReplayTransport.from_file(Path("tests/fixtures/responses/fake/basic.json"))
    config = SourceConfig(
        "docs", "fake", True, scope=SourceScope(("docs/**",), ("docs/2.md",)), allowed_hosts=("fake.invalid",)
    )
    run = DefaultSourceSession(transport, adapter, config, clock)
    rows = list_all(adapter, config, run).items
    for first_incomplete in (False, True):

        class Pages:
            calls = 0

            def __init__(self, incomplete):
                self.incomplete = incomplete

            def list_page(self, session, config, cursor):
                self.calls += 1
                if self.calls == 1:
                    return ListPage(
                        (rows[0], replace(rows[0], source_id="excluded", location="docs/2.md")),
                        "2",
                        complete=not self.incomplete,
                    )
                assert self.calls == 2
                return ListPage((rows[0], rows[1]), None, complete=False)

        pages = Pages(first_incomplete)
        listing = list_all(pages, config, run)
        assert not listing.complete
        assert listing.items == rows[: 1 if first_incomplete else 2]
        assert listing.excluded == 1
        assert listing.duplicates_dropped == (0 if first_incomplete else 1)
        assert pages.calls == (1 if first_incomplete else 2)


def test_first_origin_survives_empty_incomplete_and_stopped_listing(clock):
    from qello_knowledge.domain.source import ListPage, RunStopped, SourceOrigin, StopInfo, StopReason

    config = SourceConfig("docs", "fake", True, scope=SourceScope(("**/*.md",)), allowed_hosts=("fake.invalid",))
    origin = SourceOrigin("repo-1", "owner/docs", "commit-1")
    for ending in ("empty", "incomplete", "stopped"):

        class Pages:
            def list_page(self, session, config, cursor, ending=ending):
                if cursor is None:
                    return ListPage((), None if ending == "empty" else "next", ending != "incomplete", origin)
                raise RunStopped(StopInfo(StopReason.REQUEST_BUDGET))

        result = list_all(Pages(), config, None)
        assert result.origin == origin
        assert result.complete == (ending == "empty")
        assert (result.stop is not None) == (ending == "stopped")


def test_source_origin_requires_nonempty_identity():
    import pytest

    from qello_knowledge.domain.source import SourceOrigin

    for identity, name in (("", "name"), ("id", ""), (" ", "name"), (None, "name")):
        with pytest.raises(ValueError):
            SourceOrigin(identity, name, None)
