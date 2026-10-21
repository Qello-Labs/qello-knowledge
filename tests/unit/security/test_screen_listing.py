from dataclasses import replace

import pytest

from qello_knowledge.adapters.fake import FakeSourceAdapter
from qello_knowledge.domain.source import SourceOrigin, StopInfo, StopReason
from qello_knowledge.domain.source_config import SourceScope
from qello_knowledge.security import screen
from qello_knowledge.sources.collect import list_all
from qello_knowledge.sources.session import DefaultSourceSession
from tests.unit.security.helpers import FakeClock, fake_config, load_transport, team_policy


@pytest.mark.parametrize("complete, stopped", [(True, False), (False, False), (False, True)])
def test_screen_preserves_exact_listing(monkeypatch, complete, stopped):
    config = fake_config()
    adapter = FakeSourceAdapter()
    transport = load_transport("basic")
    session = DefaultSourceSession(transport, adapter, config, FakeClock())
    listing = replace(
        list_all(adapter, config, session),
        complete=complete,
        stop=StopInfo(StopReason.REQUEST_BUDGET) if stopped else None,
        origin=SourceOrigin("1", "sample", "v1"),
    )
    monkeypatch.setattr(screen, "list_all", lambda *args: listing)
    result = screen.screen_source(adapter, config, session, team_policy())
    assert result.listing is listing
    assert result.fetch.listing_complete == complete
    assert "origin_id" not in repr(result)


@pytest.mark.parametrize(
    "location, pattern, want",
    [
        ("./Docs/X.md", "docs/*.md", True),
        ("docs/a.md", "other/**", False),
    ],
)
def test_public_exclusion_matches_existing_normalization(location, pattern, want):
    config = fake_config(scope=SourceScope(("**/*.md",), (pattern,)))
    assert screen.source_excluded(location, config) is want
    assert screen._source_excluded(location, config) is want
