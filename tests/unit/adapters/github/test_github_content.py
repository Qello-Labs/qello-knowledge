from dataclasses import replace

import pytest

from qello_knowledge.adapters.github import GitHubRepoFilesAdapter
from qello_knowledge.domain.source import ContentFormat, FailureType, ItemStatus, SourceResponse
from qello_knowledge.sources.collect import fetch_contents, list_all
from tests.unit.adapters.github_scenarios import COMMIT, Scenario, blob_sha, session


@pytest.mark.parametrize(
    "extension,expected",
    [
        ("md", ContentFormat.MARKDOWN),
        ("mdx", ContentFormat.MARKDOWN),
        ("markdown", ContentFormat.MARKDOWN),
        ("json", ContentFormat.JSON),
        ("py", ContentFormat.CODE),
        ("java", ContentFormat.CODE),
        ("kt", ContentFormat.CODE),
        ("txt", ContentFormat.TEXT),
    ],
)
def test_blob_content_and_version_are_pinned(extension, expected, config):
    path = "docs/file." + extension
    body = "# 합성 본문\n"
    scenario = Scenario(files=[{"path": path, "body": body.encode()}])
    config = replace(config, scope=replace(config.scope, include=("docs/**",)))
    adapter = GitHubRepoFilesAdapter()
    transport = scenario.transport()
    run = session(adapter, transport, config)
    item = list_all(adapter, config, run).items[0]
    # A ref moving after the commit lookup cannot affect the blob request.
    scenario.override(scenario.commit_url, body={"sha": "c" * 40})
    content = adapter.fetch_content(run, config, item)
    assert content.body == body and content.content_format == expected
    assert content.version == item.version == COMMIT and content.location == path
    assert content.title is None and content.source_id == path
    assert transport.requests[-1].url == scenario.repo_url + "/git/blobs/" + item.change_key
    assert transport.requests[-1].headers["Accept"] == "application/vnd.github.raw+json"
    assert "ref=" not in transport.requests[-1].url and "/commits/" not in transport.requests[-1].url


@pytest.mark.parametrize("invalid_utf8", [False, True])
def test_bad_blob_is_isolated_and_remaining_files_succeed(invalid_utf8, basic, config):
    adapter = GitHubRepoFilesAdapter()
    transport = basic.transport()
    run = session(adapter, transport, config)
    listing = list_all(adapter, config, run)
    bad = listing.items[1]
    raw = b"\xff" if invalid_utf8 else b"different"
    if invalid_utf8:
        bad = replace(bad, change_key=blob_sha(raw))
        listing = replace(listing, items=(listing.items[0], bad, *listing.items[2:]))
    original_send = transport.send

    def send(request):
        if request.url.endswith("/git/blobs/" + bad.change_key):
            transport.requests.append(request)
            return SourceResponse(200, {}, raw)
        return original_send(request)

    transport.send = send
    result = fetch_contents(adapter, config, run, listing)
    assert result.items[1].status == ItemStatus.PERMANENT_FAILED
    assert result.items[1].failure == FailureType.INVALID_RESPONSE
    assert result.processed == len(listing.items) - 1 and result.failed == 1
    assert all(item.status == ItemStatus.SUCCEEDED for i, item in enumerate(result.items) if i != 1)


def test_oversized_item_makes_no_blob_request(basic, config):
    adapter = GitHubRepoFilesAdapter()
    transport = basic.transport()
    run = session(adapter, transport, config)
    listing = list_all(adapter, config, run)
    item = replace(listing.items[0], size_bytes=config.max_content_bytes + 1)
    before = len(transport.requests)
    result = fetch_contents(adapter, config, run, [item])
    assert len(transport.requests) == before
    assert result.items[0].status == ItemStatus.PERMANENT_FAILED
    assert result.items[0].failure == FailureType.SIZE_EXCEEDED


def test_identical_blobs_at_distinct_paths_are_both_fetched(config):
    scenario = Scenario(files=[{"path": "docs/a.md"}, {"path": "docs/b.md"}])
    adapter = GitHubRepoFilesAdapter()
    transport = scenario.transport()
    run = session(adapter, transport, config)
    listing = list_all(adapter, config, run)
    result = fetch_contents(adapter, config, run, listing)
    assert result.processed == 2 and len(result.contents) == 2
    assert [content.location for content in result.contents] == ["docs/a.md", "docs/b.md"]
