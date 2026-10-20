from copy import deepcopy
from dataclasses import replace
from urllib.parse import quote

import pytest

from qello_knowledge.adapters.github import GitHubRepoFilesAdapter, ListSnapshot
from qello_knowledge.domain.source import ChangeKeyKind, FailureType, InvalidResponse, SourceFailure
from qello_knowledge.sources.collect import list_all
from tests.unit.adapters.github_scenarios import COMMIT, Scenario, blob_sha, session

EXPECTED = ["README.md", "docs/a.md", "docs/b.md", "docs/d.md", "docs/deep/c.md", "docs/run.md"]


def test_basic_complete_sorted_and_only_three_requests(basic, config, clock, jitter):
    adapter = GitHubRepoFilesAdapter()
    transport = basic.transport()
    listing = list_all(adapter, config, session(adapter, transport, config, clock, jitter))
    assert listing.complete
    assert [item.source_id for item in listing.items] == EXPECTED
    assert [request.url for request in transport.requests] == [basic.repo_url, basic.commit_url, basic.tree_url]
    assert all(
        request.method == "GET" and request.headers["Accept"] == "application/vnd.github+json"
        for request in transport.requests
    )
    for item in listing.items:
        assert item.source_name == config.name and item.source_kind == "github_repo_files"
        assert item.location == item.source_id
        assert item.change_key_kind == ChangeKeyKind.VERSION and len(item.change_key) == 40
        assert item.version == COMMIT and item.modified_at is None
        assert item.item_type == "repo_file" and item.title is None
        assert item.url == f"https://github.com/octo/docs/blob/{COMMIT}/{item.location}"
        row = next(row for row in basic.exchanges[-1]["responses"][0]["body"]["tree"] if row["path"] == item.source_id)
        assert item.size_bytes == row["size"] and item.change_key == row["sha"]


def test_same_input_same_listing_and_slash_ref(config):
    scope = replace(config.scope, extra=(("repo", "octo/docs"), ("ref", "release/1")))
    config = replace(config, scope=scope)
    scenario = Scenario(ref="release/1", files=[{"path": "README.md"}])
    results = []
    for _ in range(2):
        adapter = GitHubRepoFilesAdapter()
        transport = scenario.transport()
        results.append(list_all(adapter, config, session(adapter, transport, config)))
        assert transport.requests[1].url.endswith("/commits/release%2F1")
    assert results[0] == results[1] and all(item.version == COMMIT for item in results[0].items)


def test_unicode_reserved_paths_and_case_are_preserved(config):
    paths = ["docs/공백 #?.md", "docs/A.md", "docs/a.md"]
    scenario = Scenario(files=[{"path": path} for path in paths])
    adapter = GitHubRepoFilesAdapter()
    result = list_all(adapter, config, session(adapter, scenario.transport(), config))
    assert [item.source_id for item in result.items] == sorted(paths)
    for item in result.items:
        assert item.url.endswith(quote(item.source_id, safe="/"))
        assert item.change_key == blob_sha(b"# Synthetic\n")


@pytest.mark.parametrize(
    "stage,status,failure",
    [
        ("repo", 404, FailureType.NOT_FOUND),
        ("commit", 404, FailureType.NOT_FOUND),
        ("commit", 422, FailureType.NOT_FOUND),
        ("commit", 409, FailureType.INVALID_RESPONSE),
    ],
)
def test_missing_ref_and_repo_do_not_retry(stage, status, failure, config):
    scenario = Scenario().override(getattr(Scenario(), stage + "_url"), status=status, body={})
    adapter = GitHubRepoFilesAdapter()
    run = session(adapter, scenario.transport(), config)
    with pytest.raises(SourceFailure) as raised:
        adapter.list_page(run, config, None)
    assert raised.value.failure == failure and raised.value.http_status == status
    assert run.retries_made == 0 and adapter.last_snapshot is None
    run = session(adapter, scenario.transport(), config)
    listing = list_all(adapter, config, run)
    assert not listing.complete and not listing.items and run.retries_made == 0


def test_truncation_and_empty_tree_and_no_matching_files(config):
    for files, truncated, count in [
        ([{"path": "README.md"}], True, 1),
        ([], False, 0),
        ([{"path": "a.java"}], False, 0),
    ]:
        scenario = Scenario(files=files, truncated=truncated)
        adapter = GitHubRepoFilesAdapter()
        listing = list_all(adapter, config, session(adapter, scenario.transport(), config))
        assert listing.complete == (not truncated) and len(listing.items) == count
        assert adapter.last_snapshot == ListSnapshot(COMMIT, "public", truncated)


@pytest.mark.parametrize(
    "mutation",
    [
        "no_sha",
        "truncated",
        "parent_path",
        "commit_sha",
        "tree_sha",
        "archived",
        "size_bool",
        "size_negative",
        "path_empty",
        "path_absolute",
        "tree_not_list",
        "mode_missing",
        "type_bad",
    ],
)
def test_invalid_shapes_are_safe_and_incomplete(mutation, config):
    scenario = Scenario(files=[{"path": "README.md"}])
    tree = deepcopy(scenario.exchanges[-1]["responses"][0]["body"])
    row = tree["tree"][0]
    if mutation == "no_sha":
        del row["sha"]
    elif mutation == "truncated":
        tree["truncated"] = "false"
    elif mutation == "parent_path":
        row["path"] = "docs/../a.md"
    elif mutation == "path_empty":
        row["path"] = ""
    elif mutation == "path_absolute":
        row["path"] = "/a.md"
    elif mutation == "size_bool":
        row["size"] = True
    elif mutation == "size_negative":
        row["size"] = -1
    elif mutation == "tree_not_list":
        tree["tree"] = {}
    elif mutation == "mode_missing":
        del row["mode"]
    elif mutation == "type_bad":
        row["type"] = None
    scenario.override(scenario.tree_url, body=tree)
    if mutation in {"commit_sha", "tree_sha"}:
        body = {"sha": COMMIT, "commit": {"tree": {"sha": "b" * 40}}}
        if mutation == "commit_sha":
            body["sha"] = "invalid"
        else:
            body["commit"]["tree"]["sha"] = "B" * 40
        scenario.override(scenario.commit_url, body=body)
    if mutation == "archived":
        scenario.override(scenario.repo_url, body={"visibility": "public", "archived": 0})
    adapter = GitHubRepoFilesAdapter()
    with pytest.raises(InvalidResponse):
        adapter.list_page(session(adapter, scenario.transport(), config), config, None)
    listing = list_all(adapter, config, session(adapter, scenario.transport(), config))
    assert not listing.complete and listing.items == ()


def test_snapshot_records_commit_before_tree_and_resets(config):
    scenario = Scenario()
    adapter = GitHubRepoFilesAdapter()
    list_all(adapter, config, session(adapter, scenario.transport(), config))
    assert adapter.last_snapshot == ListSnapshot(COMMIT, "public", False)
    scenario.override(scenario.tree_url, status=404, body={})
    listing = list_all(adapter, config, session(adapter, scenario.transport(), config))
    assert not listing.complete and adapter.last_snapshot == ListSnapshot(COMMIT, "public", None)
    scenario.override(scenario.repo_url, status=404, body={})
    list_all(adapter, config, session(adapter, scenario.transport(), config))
    assert adapter.last_snapshot is None


@pytest.mark.parametrize("repo,encoded", [("octo?/docs#", "octo%3F/docs%23"), ("octo#/docs?", "octo%23/docs%3F")])
def test_repo_owner_and_name_are_encoded_as_individual_url_segments(repo, encoded, tmp_path):
    from qello_knowledge.sources.collect import fetch_contents
    from qello_knowledge.sources.config import load_sources

    path = tmp_path / "sources.toml"
    path.write_text(
        '''[[source]]
name = "docs"
kind = "github_repo_files"
enabled = true
auth = "GITHUB_API_TOKEN"
[source.scope]
repo = "'''
        + repo
        + """"
ref = "main"
include = ["README.md"]
"""
    )
    configs, issues = load_sources(path)
    assert not issues
    config = configs[0]
    scenario = Scenario(files=[{"path": "README.md"}])
    expected_base = "https://api.github.com/repos/" + encoded
    for entry in scenario.exchanges:
        entry["url"] = expected_base + entry["url"].removeprefix(scenario.repo_url)
    transport = scenario.transport()
    adapter = GitHubRepoFilesAdapter()
    run = session(adapter, transport, config)
    listing = list_all(adapter, config, run)
    assert listing.complete and len(listing.items) == 1
    item = listing.items[0]
    assert item.url == f"https://github.com/{encoded}/blob/{COMMIT}/README.md"
    result = fetch_contents(adapter, config, run, listing)
    assert result.processed == 1 and result.failed == 0
    assert [request.url for request in transport.requests] == [
        expected_base,
        expected_base + "/commits/main",
        expected_base + "/git/trees/" + "b" * 40 + "?recursive=1",
        expected_base + "/git/blobs/" + item.change_key,
    ]
