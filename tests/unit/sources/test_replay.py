import json

import pytest

from qello_knowledge.adapters.replay import ReplayTransport
from qello_knowledge.domain.source import SourceRequest, TransportError


@pytest.fixture
def scenario(tmp_path):
    def write(responses, meta=True):
        data = {"body": {"exchanges": [{"method": "GET", "url": "https://fake.invalid/a", "responses": responses}]}}
        if meta:
            data["_meta"] = {"source_api": "fake", "saved_at": "2026-10-19", "redactions": []}
        path = tmp_path / "replay.json"
        path.write_text(json.dumps(data))
        return path

    return write


def test_replays_responses_in_order_and_records_every_request(scenario):
    replay = ReplayTransport.from_file(
        scenario(
            [
                {"status": 502, "headers": {}, "body": "busy"},
                {"status": 200, "headers": {}, "body": "안녕"},
            ]
        )
    )
    request = SourceRequest("GET", "https://fake.invalid/a")
    assert replay.send(request).status == 502
    assert replay.send(request).body == "안녕".encode()
    with pytest.raises(AssertionError):
        replay.send(request)
    with pytest.raises(AssertionError):
        replay.send(SourceRequest("HEAD", request.url))
    assert replay.requests == [request, request, request, SourceRequest("HEAD", request.url)]


def test_missing_metadata_rejected(scenario):
    with pytest.raises(ValueError):
        ReplayTransport.from_file(scenario([], meta=False))


@pytest.mark.parametrize("missing", ["source_api", "saved_at", "redactions"])
def test_incomplete_metadata_rejected(scenario, missing):
    path = scenario([])
    data = json.loads(path.read_text())
    del data["_meta"][missing]
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        ReplayTransport.from_file(path)


@pytest.mark.parametrize("kind", ["timeout", "connection"])
def test_transport_errors_are_replayed_and_recorded(scenario, kind):
    replay = ReplayTransport.from_file(scenario([{"error": kind}]))
    with pytest.raises(TransportError) as caught:
        replay.send(SourceRequest("GET", "https://fake.invalid/a"))
    assert caught.value.kind == kind
    assert len(replay.requests) == 1


def test_read_limit_truncates_bytes_and_marks_incomplete(scenario):
    replay = ReplayTransport.from_file(scenario([{"status": 200, "headers": {}, "body": "abcdef"}]))
    response = replay.send(SourceRequest("GET", "https://fake.invalid/a", max_bytes=3))
    assert response.body == b"abc"
    assert response.truncated
