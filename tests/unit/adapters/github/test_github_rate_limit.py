from dataclasses import replace

from qello_knowledge.adapters.github import GitHubRepoFilesAdapter
from qello_knowledge.domain.source import FailureType, ItemStatus, StopReason
from qello_knowledge.sources.collect import fetch_contents, list_all
from tests.unit.adapters.github_scenarios import Scenario, session


def prepared(config, clock, headers, *, status=403, repeats=1):
    scenario = Scenario(files=[{"path": "docs/a.md", "body": b"# One"}, {"path": "docs/b.md", "body": b"# Two"}])
    adapter = GitHubRepoFilesAdapter()
    transport = scenario.transport()
    run = session(adapter, transport, config, clock)
    listing = list_all(adapter, config, run)
    url = scenario.repo_url + "/git/blobs/" + listing.items[0].change_key
    scenario.override(url, status=status, headers=headers)
    for _ in range(repeats - 1):
        scenario.queue(url, status=status, headers=headers)
    scenario.queue(url, body="# One")
    transport = scenario.transport()
    run.transport = transport
    return adapter, transport, run, listing


def test_primary_waits_then_succeeds(config, clock):
    reset = int(clock.now().timestamp()) + 30
    adapter, transport, run, listing = prepared(
        config, clock, {"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(reset)}
    )
    result = fetch_contents(adapter, config, run, listing)
    assert result.processed == 2 and result.items[0].retries == 1
    assert sum(clock.sleeps) >= 30


def test_wait_too_long_stops_rest(config, clock):
    reset = int(clock.now().timestamp()) + int(config.limits.max_wait_seconds) + 10
    adapter, transport, run, listing = prepared(
        config, clock, {"x-ratelimit-remaining": "0", "x-ratelimit-reset": str(reset)}
    )
    result = fetch_contents(adapter, config, run, listing)
    assert result.stop.reason == StopReason.WAIT_TOO_LONG
    assert all(item.status == ItemStatus.SKIPPED for item in result.items)
    assert len(transport.requests) == 1


def test_denied_is_permanent_without_retry(config, clock):
    adapter, transport, run, listing = prepared(config, clock, {})
    result = fetch_contents(adapter, config, run, listing)
    assert result.items[0].status == ItemStatus.PERMANENT_FAILED
    assert result.items[0].failure == FailureType.ACCESS_DENIED and result.items[0].retries == 0
    assert result.items[1].status == ItemStatus.SUCCEEDED and len(transport.requests) == 2


def test_secondary_exhaustion_holds_next_file_until_last_retry_after(config, clock):
    config = replace(config, retry=replace(config.retry, max_retries=1))
    adapter, transport, run, listing = prepared(
        config, clock, {"retry-after": "60", "x-ratelimit-remaining": "100"}, repeats=2
    )
    sent = []
    original = transport.send

    def send(request):
        sent.append((request.url, clock.now()))
        return original(request)

    transport.send = send
    result = fetch_contents(adapter, config, run, listing)
    assert result.items[0].status == ItemStatus.TRANSIENT_EXHAUSTED
    assert result.items[1].status == ItemStatus.SUCCEEDED
    assert (sent[-1][1] - sent[-2][1]).total_seconds() >= 60
    assert sent[-1][0].endswith(listing.items[1].change_key)


def test_auth_stops_without_more_requests(config, clock):
    adapter, transport, run, listing = prepared(config, clock, {}, status=401)
    result = fetch_contents(adapter, config, run, listing)
    assert result.stop.reason == StopReason.AUTH_FAILED
    assert result.remaining == 2 and len(transport.requests) == 1
