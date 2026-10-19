from hashlib import sha256

import pytest

from qello_knowledge.adapters.fake import FakeSourceAdapter
from qello_knowledge.adapters.replay import ReplayTransport
from qello_knowledge.domain.source import ContentFormat, ReadOnlyViolation, SourceContent, SourceRequest
from qello_knowledge.domain.source_config import SourceConfig
from qello_knowledge.sources.session import DefaultSourceSession


@pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE", "get"])
def test_write_is_blocked_before_transport(method, clock):
    transport = ReplayTransport([])
    session = DefaultSourceSession(transport, FakeSourceAdapter(), SourceConfig("docs", "fake", True), clock)
    with pytest.raises(ReadOnlyViolation):
        session.send(SourceRequest(method, "https://fake.invalid/items"))
    assert transport.requests == []
    assert session.requests_made == 0


def test_session_hashes_utf8_content_and_sets_injected_utc_time(clock):
    session = DefaultSourceSession(ReplayTransport([]), FakeSourceAdapter(), SourceConfig("docs", "fake", True), clock)
    original = SourceContent("a", "안녕", ContentFormat.TEXT, None, "a.md", None)
    first = session.finalize_content(original)
    assert first.content_hash == "sha256:" + sha256("안녕".encode()).hexdigest()
    assert first.fetched_at == clock.now()
    clock.sleep(1)
    assert session.finalize_content(original).content_hash == first.content_hash
    assert session.finalize_content(original).fetched_at > first.fetched_at
    assert original.content_hash == "" and original.fetched_at is None
