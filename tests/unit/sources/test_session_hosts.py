from dataclasses import replace
from pathlib import Path

import pytest

from qello_knowledge.adapters.fake import FakeSourceAdapter
from qello_knowledge.adapters.replay import ReplayTransport
from qello_knowledge.domain.source import FailureType, HostNotAllowed, SourceFailure, SourceRequest
from qello_knowledge.domain.source_config import SourceConfig, SourceScope
from qello_knowledge.sources.collect import fetch_contents, list_all
from qello_knowledge.sources.session import DefaultSourceSession


@pytest.fixture
def config():
    return SourceConfig("docs", "fake", True, scope=SourceScope(("**/*.md",)), allowed_hosts=("fake.invalid",))


@pytest.mark.parametrize(
    ("scenario", "blocked_url"),
    [
        ("redirect_http_downgrade", "http://fake.invalid/moved/1"),
        ("redirect_port_change", "https://fake.invalid:8443/moved/1"),
    ],
)
def test_redirect_rejects_downgrade_and_port_change_before_transmission(clock, config, scenario, blocked_url):
    transport = ReplayTransport.from_file(Path(f"tests/fixtures/responses/fake/{scenario}.json"))
    session = DefaultSourceSession(transport, FakeSourceAdapter(), config, clock)
    with pytest.raises(SourceFailure) as caught:
        session.send(SourceRequest("GET", "https://fake.invalid/items/1"))
    assert caught.value.failure == FailureType.REDIRECT_BLOCKED
    assert session.requests_made == len(transport.requests) == 1
    assert not any(request.url == blocked_url for request in transport.requests)


@pytest.mark.parametrize(
    "url",
    [
        "http://fake.invalid/items/1",
        "https://other.invalid/items/1",
        "//fake.invalid/items/1",
        "https://fake.invalid:bad/items/1",
        "https:///items/1",
    ],
)
def test_initial_address_violation_never_reaches_transport(clock, config, url):
    transport = ReplayTransport([])
    session = DefaultSourceSession(transport, FakeSourceAdapter(), config, clock)
    with pytest.raises(HostNotAllowed) as caught:
        session.send(SourceRequest("GET", url))
    assert url not in str(caught.value)
    assert session.requests_made == 0 and not transport.requests
    assert clock.sleeps == []


@pytest.mark.parametrize(
    ("initial", "target"),
    [
        ("https://fake.invalid/items/1", "https://fake.invalid:443/moved/1"),
        ("https://fake.invalid:8443/items/1", "/moved/1"),
        ("https://fake.invalid:8443/items/1", "https://fake.invalid:8443/moved/1"),
    ],
)
def test_https_redirect_preserves_effective_port(clock, config, initial, target):
    from urllib.parse import urljoin

    final = urljoin(initial, target)
    transport = ReplayTransport(
        [
            dict(method="GET", url=initial, responses=[dict(status=302, headers={"Location": target}, body="")]),
            dict(method="GET", url=final, responses=[dict(status=200, headers={}, body="ok")]),
        ]
    )
    session = DefaultSourceSession(transport, FakeSourceAdapter(), config, clock)
    assert session.send(SourceRequest("GET", initial)).body == b"ok"
    assert [request.url for request in transport.requests] == [initial, final]


def test_redirect_cannot_change_custom_original_port_to_default(clock, config):
    transport = ReplayTransport(
        [
            dict(
                method="GET",
                url="https://fake.invalid:8443/items/1",
                responses=[
                    dict(status=302, headers={"Location": "https://fake.invalid/moved/1"}, body=""),
                ],
            )
        ]
    )
    session = DefaultSourceSession(transport, FakeSourceAdapter(), config, clock)
    with pytest.raises(SourceFailure) as caught:
        session.send(SourceRequest("GET", "https://fake.invalid:8443/items/1"))
    assert caught.value.failure == FailureType.REDIRECT_BLOCKED and len(transport.requests) == 1


def test_fetch_contents_does_not_swallow_host_contract_violation(clock, config):
    class WrongHostAdapter(FakeSourceAdapter):
        def fetch_content(self, session, config, item):
            session.send(SourceRequest("GET", "https://other.invalid/documents"))

    adapter = WrongHostAdapter()
    transport = ReplayTransport.from_file(Path("tests/fixtures/responses/fake/basic.json"))
    session = DefaultSourceSession(transport, adapter, config, clock)
    listing = list_all(adapter, config, session)
    before = len(transport.requests)
    with pytest.raises(HostNotAllowed):
        fetch_contents(adapter, config, session, listing)
    assert len(transport.requests) == before


def test_list_all_does_not_swallow_host_contract_violation(clock, config):
    transport = ReplayTransport([])
    session = DefaultSourceSession(transport, FakeSourceAdapter(), replace(config, allowed_hosts=()), clock)
    with pytest.raises(HostNotAllowed):
        list_all(FakeSourceAdapter(), config, session)
    assert not transport.requests
