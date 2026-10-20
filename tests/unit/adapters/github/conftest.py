import pytest

from qello_knowledge.domain.source_config import SourceConfig, SourceScope
from tests.unit.adapters.github_scenarios import basic_scenario
from tests.unit.sources.conftest import FakeClock


@pytest.fixture
def config():
    return SourceConfig(
        "docs",
        "github_repo_files",
        True,
        auth="GITHUB_API_TOKEN",
        scope=SourceScope(
            ("docs/**/*.md", "README.md"), ("docs/private/**",), (("repo", "octo/docs"), ("ref", "main"))
        ),
        allowed_hosts=("api.github.com",),
    )


@pytest.fixture
def clock():
    return FakeClock()


@pytest.fixture
def jitter():
    return lambda cap: cap / 2


@pytest.fixture
def basic():
    return basic_scenario()
