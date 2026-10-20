import io
import logging

import pytest

from qello_knowledge.adapters.github import GitHubRepoFilesAdapter
from qello_knowledge.adapters.http import HttpsTransport
from qello_knowledge.config.loader import SecretValue
from qello_knowledge.domain.source import SourceRequest
from qello_knowledge.sources.collect import fetch_contents, list_all
from tests.unit.adapters.github_scenarios import Scenario, session

TOKEN = "gh" + "p_" + "B" * 36


class Response(io.BytesIO):
    def __init__(self, source):
        super().__init__(source.body)
        self.status = source.status
        self.headers = source.headers


class ReplayOpener:
    def __init__(self, replay):
        self.replay = replay

    def open(self, request, timeout):
        headers = dict(request.header_items())
        assert headers.get("Authorization") == "Bearer " + TOKEN
        response = self.replay.send(SourceRequest(request.method, request.full_url, headers))
        return Response(response)


@pytest.mark.parametrize("case", ["normal", "failure", "rate_limit"])
def test_transport_adapter_results_logs_and_snapshot_do_not_leak(case, config, clock, caplog):
    scenario = Scenario(files=[{"path": "README.md", "body": b"# Synthetic"}])
    url = next(entry["url"] for entry in scenario.exchanges if "/git/blobs/" in entry["url"])
    if case == "failure":
        scenario.override(url, status=403, body=TOKEN)
    elif case == "rate_limit":
        scenario.override(url, status=403, headers={"retry-after": "1", "x-ratelimit-remaining": "100"}, body=TOKEN)
        scenario.queue(url, body="# Synthetic")
    transport = HttpsTransport(("api.github.com",), SecretValue(TOKEN), opener=ReplayOpener(scenario.transport()))
    adapter = GitHubRepoFilesAdapter()
    run = session(adapter, transport, config, clock)
    with caplog.at_level(logging.INFO):
        result = fetch_contents(adapter, config, run, list_all(adapter, config, run))
    output = repr(result.to_dict()) + caplog.text + repr(adapter.last_snapshot) + repr(transport)
    assert TOKEN not in output and "Authorization" not in output
    assert result.processed == (0 if case == "failure" else 1)
    assert not any(record.name == "qello_knowledge.adapters.http" for record in caplog.records)


def test_snapshot_repr_does_not_expose_unrecognized_visibility(config):
    scenario = Scenario(visibility=TOKEN, files=[])
    adapter = GitHubRepoFilesAdapter()
    list_all(adapter, config, session(adapter, scenario.transport(), config))
    assert adapter.last_snapshot.visibility == TOKEN
    assert TOKEN not in repr(adapter.last_snapshot)
