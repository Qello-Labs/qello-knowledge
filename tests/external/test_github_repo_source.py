"""사람이 활성화 절차를 마친 뒤에만 실행하는 실제 원본 측정."""

from pathlib import Path

import pytest

from qello_knowledge.adapters.http import HttpsTransport
from qello_knowledge.config.loader import SecretValue
from qello_knowledge.devtools.measure import PreparedSource, measure_source, prepare_source
from qello_knowledge.sources.clock import SystemClock
from qello_knowledge.sources.config import load_sources


@pytest.mark.external
def test_active_github_source_measurement(require_env):
    token = SecretValue(require_env("GITHUB_API_TOKEN"))
    sources = Path("config/sources.toml")
    configs, issues = load_sources(sources)
    assert not issues, [issue.code for issue in issues]
    config = next((c for c in configs if c.enabled and c.kind == "github_repo_files"), None)
    assert config is not None, "활성화 절차(research R-13) 뒤 실행"
    prepared = prepare_source(
        config.name, sources, Path("config/source_reviews"), Path("config/security_exceptions.toml")
    )
    assert isinstance(prepared, PreparedSource), [issue.code for issue in prepared]
    measurement = measure_source(prepared, HttpsTransport(config.allowed_hosts, token), SystemClock())
    data = measurement.to_dict()
    assert data["requests"] <= config.limits.max_requests_per_run
    assert data["listing_complete"] and data["by_verdict"].get("ERROR", 0) == 0 and data["stop"] is None
