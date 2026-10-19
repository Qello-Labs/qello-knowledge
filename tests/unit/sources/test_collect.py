from dataclasses import replace
from datetime import timedelta
from pathlib import Path

import pytest

from qello_knowledge.adapters.fake import FakeSourceAdapter
from qello_knowledge.adapters.replay import ReplayTransport
from qello_knowledge.domain.source import FailureType, ItemStatus, ReadOnlyViolation, SourceRequest, StopReason
from qello_knowledge.domain.source_config import RateLimits, RetryPolicy, SourceConfig, SourceScope
from qello_knowledge.sources.collect import fetch_contents, list_all
from qello_knowledge.sources.session import DefaultSourceSession


@pytest.fixture
def run_scenario(clock, jitter):
    def run(name, **changes):
        config = SourceConfig("docs", "fake", True, scope=SourceScope(("**/*.md",)), allowed_hosts=("fake.invalid",))
        config = replace(config, **changes)
        adapter = FakeSourceAdapter()
        transport = ReplayTransport.from_file(Path(f"tests/fixtures/responses/fake/{name}.json"))
        session = DefaultSourceSession(transport, adapter, config, clock, jitter=jitter)
        listing = list_all(adapter, config, session)
        result = fetch_contents(adapter, config, session, listing)
        return result, transport

    return run


def test_retry_transient_twice_then_success(run_scenario, clock):
    result, transport = run_scenario("flaky")
    assert result.items[0].status == ItemStatus.SUCCEEDED and result.items[0].retries == 2
    assert result.processed == 3 and result.failed == result.remaining == 0
    assert result.requests_made == len(transport.requests) == 6
    assert clock.sleeps == [0.5, 1]
    assert result.contents[0].content_hash.startswith("sha256:")
    assert result.contents[0].fetched_at == clock.now()
    assert result.started_at == clock.start and result.finished_at == clock.now()


def test_retry_exhaustion_isolated_to_one_item(run_scenario):
    result, transport = run_scenario("exhausted")
    assert result.items[0].status == ItemStatus.TRANSIENT_EXHAUSTED
    assert result.items[0].failure == FailureType.SERVER_ERROR and result.items[0].retries == 3
    assert result.processed == 2 and result.failed == 1 and result.remaining == 0
    assert [item.status for item in result.items[1:]] == [ItemStatus.SUCCEEDED] * 2
    assert len(transport.requests) == 7


def test_retry_permanent_failure_is_never_retried(run_scenario, clock):
    result, transport = run_scenario("not_found")
    assert result.items[0].status == ItemStatus.PERMANENT_FAILED
    assert result.items[0].failure == FailureType.NOT_FOUND and result.items[0].retries == 0
    assert result.items[0].http_status == 404
    assert clock.sleeps == [] and len(transport.requests) == 4


def test_auth_failure_stops_and_skips_current_and_remaining_items(run_scenario):
    result, transport = run_scenario("auth_failed")
    assert result.stop.reason == StopReason.AUTH_FAILED
    assert result.processed == result.failed == 0 and result.remaining == 3
    assert [item.status for item in result.items] == [ItemStatus.SKIPPED] * 3
    assert result.items[0].failure == FailureType.AUTH_FAILED and result.items[0].http_status == 401
    assert len(transport.requests) == 2  # 목록과 첫 본문. 첫 401 뒤에는 요청 없음.


def test_isolation_permanent_failure_leaves_all_other_items_successful(run_scenario):
    result, _ = run_scenario("mixed")
    assert [item.status for item in result.items] == ["SUCCEEDED", "PERMANENT_FAILED", "SUCCEEDED"]
    assert result.processed == 2 and result.failed == 1 and result.remaining == 0
    assert [content.source_id for content in result.contents] == ["1", "3"]


def test_long_rate_limit_reports_processed_remaining_and_retry_at(run_scenario, clock):
    result, transport = run_scenario("rate_limited_long")
    assert result.processed == result.failed == 0 and result.remaining == 5
    assert result.stop.reason == StopReason.WAIT_TOO_LONG
    assert result.stop.retry_at == clock.start + timedelta(seconds=3600)
    assert [item.status for item in result.items] == [ItemStatus.SKIPPED] * 5
    assert len(transport.requests) == 3 and clock.sleeps == []


def test_retry_origin_hint_succeeds_after_wait(run_scenario, clock):
    result, _ = run_scenario("rate_limited")
    assert result.processed == 5 and result.items[0].retries == 1
    assert clock.sleeps == [30]


def test_redirect_only_follows_allowed_host_and_counts_each_request(run_scenario):
    result, transport = run_scenario("redirect_ok")
    assert result.processed == 3 and result.items[0].retries == 0
    assert result.requests_made == len(transport.requests) == 5
    assert [r.url for r in transport.requests[1:3]] == ["https://fake.invalid/items/1", "https://fake.invalid/moved/1"]
    blocked, transport = run_scenario("redirect_blocked")
    assert blocked.items[0].failure == FailureType.REDIRECT_BLOCKED
    assert blocked.items[0].status == ItemStatus.PERMANENT_FAILED
    assert all("other.invalid" not in r.url for r in transport.requests)


@pytest.mark.parametrize("scenario", ["too_large", "too_large_unknown"])
def test_size_limit_is_permanent_and_remaining_items_continue(run_scenario, scenario):
    result, transport = run_scenario(scenario, max_content_bytes=1000)
    assert result.items[0].status == ItemStatus.PERMANENT_FAILED
    assert result.items[0].failure == FailureType.SIZE_EXCEEDED
    assert result.processed == 2 and result.failed == 1
    assert all(c.source_id != "1" for c in result.contents)
    assert all(r.max_bytes == 1000 for r in transport.requests)
    if scenario == "too_large":
        assert not any(r.url.endswith("/items/1") for r in transport.requests)


def test_runtime_limit_stops_before_wait_that_would_exceed_budget(run_scenario, clock):
    result, _ = run_scenario("exhausted", limits=RateLimits(max_run_seconds=1))
    assert result.stop.reason == StopReason.RUN_TIME
    assert result.remaining == 3 and result.processed == result.failed == 0
    assert clock.sleeps == [0.5]
    assert result.items[0].retries == 1


def test_request_budget_preserves_success_and_marks_unattempted_items(run_scenario):
    result, transport = run_scenario("mixed", limits=RateLimits(max_requests_per_run=2))
    assert result.processed == 1 and result.remaining == 2 and result.failed == 0
    assert result.stop.reason == StopReason.REQUEST_BUDGET
    assert [item.status for item in result.items] == ["SUCCEEDED", "SKIPPED", "SKIPPED"]
    assert len(transport.requests) == 2


def test_incomplete_listing_retains_known_items_and_is_reported(clock, jitter):
    import json

    data = json.loads(Path("tests/fixtures/responses/fake/basic.json").read_text())
    data["body"]["exchanges"][1]["responses"] = [dict(status=503, headers={}, body="busy")] * 4
    transport = ReplayTransport(data["body"]["exchanges"])
    adapter = FakeSourceAdapter()
    config = SourceConfig("docs", "fake", True, scope=SourceScope(("**/*.md",)))
    session = DefaultSourceSession(transport, adapter, config, clock, jitter=jitter)
    listing = list_all(adapter, config, session)
    assert not listing.complete and len(listing.items) == 3
    result = fetch_contents(adapter, config, session, listing)
    assert not result.listing_complete and result.processed == 3


def test_read_only_adapter_defect_is_not_swallowed(clock, jitter):
    class WritingAdapter(FakeSourceAdapter):
        def fetch_content(self, session, config, item):
            session.send(SourceRequest("POST", "https://fake.invalid/items"))

    adapter = WritingAdapter()
    transport = ReplayTransport.from_file(Path("tests/fixtures/responses/fake/basic.json"))
    config = SourceConfig("docs", "fake", True, scope=SourceScope(("**/*.md",)))
    session = DefaultSourceSession(transport, adapter, config, clock, jitter=jitter)
    listing = list_all(adapter, config, session)
    before = len(transport.requests)
    with pytest.raises(ReadOnlyViolation):
        fetch_contents(adapter, config, session, listing)
    assert len(transport.requests) == before


def test_invalid_response_isolated_and_other_items_are_preserved(run_scenario):
    result, _ = run_scenario("invalid_shape")
    assert result.processed == 4 and result.failed == 1 and result.remaining == 0
    assert result.items[1].failure == FailureType.INVALID_RESPONSE
    assert result.items[1].status == ItemStatus.PERMANENT_FAILED and result.items[1].retries == 0
    assert result.items[1].http_status == 200


def test_runtime_budget_also_rejects_rate_gate_wait_before_sleep(run_scenario, clock):
    result, transport = run_scenario("basic", limits=RateLimits(max_requests_per_minute=1, max_run_seconds=10))
    assert not result.listing_complete and result.stop.reason == StopReason.RUN_TIME
    assert result.processed == result.failed == 0 and result.remaining == 3
    assert len(transport.requests) == 1 and clock.sleeps == []


@pytest.mark.parametrize("kind", ["timeout", "connection"])
def test_retry_transport_error_counts_attempts_and_recovers(clock, jitter, kind):
    import json

    data = json.loads(Path("tests/fixtures/responses/fake/flaky.json").read_text())
    data["body"]["exchanges"][1]["responses"][0:2] = [{"error": kind}] * 2
    transport = ReplayTransport(data["body"]["exchanges"])
    adapter = FakeSourceAdapter()
    config = SourceConfig("docs", "fake", True, scope=SourceScope(("**/*.md",)))
    session = DefaultSourceSession(transport, adapter, config, clock, jitter=jitter)
    result = fetch_contents(adapter, config, session, list_all(adapter, config, session))
    assert result.processed == 3 and result.items[0].retries == 2
    assert result.requests_made == len(transport.requests) == 6


def test_redirect_chain_is_bounded_to_three_followups(clock, jitter):
    import json

    data = json.loads(Path("tests/fixtures/responses/fake/basic.json").read_text())
    data["body"]["exchanges"][2]["responses"] = [
        dict(status=302, headers={"Location": "/items/1"}, body=""),
    ] * 4
    transport = ReplayTransport(data["body"]["exchanges"])
    adapter = FakeSourceAdapter()
    config = SourceConfig("docs", "fake", True, scope=SourceScope(("**/*.md",)), allowed_hosts=("fake.invalid",))
    session = DefaultSourceSession(transport, adapter, config, clock, jitter=jitter)
    result = fetch_contents(adapter, config, session, list_all(adapter, config, session))
    assert result.items[0].failure == FailureType.REDIRECT_BLOCKED and result.items[0].retries == 0
    assert result.processed == 4 and result.failed == 1
    assert sum(r.url.endswith("/items/1") for r in transport.requests) == 4


def test_auth_stop_prevents_subsequent_sends_even_if_caller_retries(clock, jitter):
    from qello_knowledge.domain.source import RunStopped

    transport = ReplayTransport.from_file(Path("tests/fixtures/responses/fake/auth_failed.json"))
    config = SourceConfig("docs", "fake", True)
    session = DefaultSourceSession(transport, FakeSourceAdapter(), config, clock, jitter=jitter)
    request = SourceRequest("GET", "https://fake.invalid/items/1")
    for _ in range(2):
        with pytest.raises(RunStopped) as caught:
            session.send(request)
        assert caught.value.stop.reason == StopReason.AUTH_FAILED
    assert len(transport.requests) == session.requests_made == 1


def test_retry_zero_cap_exhausts_after_first_attempt(run_scenario, clock):
    result, transport = run_scenario("exhausted", retry=RetryPolicy(max_retries=0))
    assert result.items[0].status == ItemStatus.TRANSIENT_EXHAUSTED and result.items[0].retries == 0
    assert result.processed == 2 and result.failed == 1
    assert len(transport.requests) == 4 and clock.sleeps == []


def test_unattempted_item_does_not_inherit_previous_http_status(run_scenario):
    result, _ = run_scenario("mixed", limits=RateLimits(max_requests_per_run=2))
    assert result.items[0].http_status == 200
    assert all(item.http_status is None for item in result.items[1:])


def test_retry_does_not_wait_after_last_allowed_request(run_scenario, clock):
    result, _ = run_scenario("exhausted", limits=RateLimits(max_requests_per_run=2))
    assert result.stop.reason == StopReason.REQUEST_BUDGET
    assert result.requests_made == 2 and result.items[0].retries == 0
    assert clock.sleeps == []
