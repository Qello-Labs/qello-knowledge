"""사람이 확인 기록을 쓴 뒤에만 실행하는 실제 Confluence 측정(QK-ING-003 FR-027, SC-010). 기본 실행에서 빠진다."""

from pathlib import Path

import pytest

from qello_knowledge.config.loader import load
from qello_knowledge.config.registry import Entrypoint
from qello_knowledge.devtools.measure import PreparedSource, measure_confluence, prepare_source
from qello_knowledge.indexer.sync_cli import TARGET_PARTS
from qello_knowledge.sources.clock import SystemClock

FR_027_KEYS = {
    "requests",
    "elapsed_seconds",
    "pages",
    "total_bytes",
    "max_page_bytes",
    "by_verdict",
    "conversion_warnings",
}


@pytest.mark.external
def test_confluence_source_measurement(require_env):
    for name in ("ATLASSIAN_API_TOKEN", "ATLASSIAN_EMAIL", "ATLASSIAN_CLOUD_ID"):
        require_env(name)
    prepared = prepare_source(
        "confluence-scrum",
        Path("config/sources.toml"),
        Path("config/source_reviews"),
        Path("config/security_exceptions.toml"),
    )
    assert isinstance(prepared, PreparedSource), [issue.code for issue in prepared]
    settings = load(Entrypoint.INDEX)
    adapter, transport = TARGET_PARTS["confluence_pages"](prepared.config, settings, prepared.context)
    data = measure_confluence(prepared, adapter, transport, SystemClock(), chunk=True).to_dict()
    assert FR_027_KEYS <= data.keys() and "estimated_neurons" in data["chunking"]
    assert data["requests"] <= prepared.config.limits.max_requests_per_run
    assert data["listing_complete"] and data["stop"] is None
