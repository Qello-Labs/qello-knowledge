from urllib.parse import urlsplit

import pytest

from qello_knowledge.adapters.github import GitHubRepoFilesAdapter
from qello_knowledge.domain.source import ContentFormat
from qello_knowledge.domain.source_config import SourceConfig, SourceScope
from tests.contract.source_adapter_contract import ContractExpectations, SourceAdapterContract
from tests.unit.adapters.github_scenarios import COMMIT, Scenario


def scenario(**kwargs):
    return Scenario(files=[{"path": f"docs/{i}.md", "body": f"# Synthetic {i}\n".encode()} for i in range(5)], **kwargs)


class TestGitHubAdapterContract(SourceAdapterContract):
    @pytest.fixture
    def adapter(self):
        return GitHubRepoFilesAdapter()

    @pytest.fixture
    def transport(self):
        return scenario().transport()

    @pytest.fixture
    def config(self):
        return SourceConfig(
            "docs",
            "github_repo_files",
            True,
            scope=SourceScope(("**/*.md",), (), (("repo", "octo/docs"), ("ref", "main"))),
            allowed_hosts=("api.github.com",),
        )

    @pytest.fixture
    def expected(self):
        invalid = scenario()
        url = next(
            entry["url"]
            for entry in invalid.exchanges
            if "/git/blobs/" in entry["url"] and entry["responses"][0]["body"] == "# Synthetic 1\n"
        )
        invalid.override(url, body="wrong blob")
        return ContractExpectations(
            5,
            COMMIT,
            (("visibility", "public"),),
            ContentFormat.MARKDOWN,
            "https://api.github.com/repos/octo/docs",
            {
                "no_modified_at": None,
                "page_overlap": None,
                "no_access": scenario(visibility=None),
                "invalid_shape": invalid,
            },
            None,
        )

    def test_all_requests_use_get_and_allowed_host(self, adapter, transport, config):
        from qello_knowledge.sources.collect import fetch_contents, list_all

        run = self.session(adapter, transport, config)
        fetch_contents(adapter, config, run, list_all(adapter, config, run))
        assert all(
            request.method == "GET" and urlsplit(request.url).hostname == "api.github.com"
            for request in transport.requests
        )
