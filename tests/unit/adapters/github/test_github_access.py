import pytest

from qello_knowledge.adapters.github import GitHubRepoFilesAdapter
from qello_knowledge.domain.security import Verdict
from qello_knowledge.domain.source import AccessInfo, AccessStatus, OriginState
from qello_knowledge.security.policy import SecurityPolicy
from qello_knowledge.security.screen import screen_source
from qello_knowledge.sources.collect import list_all
from tests.unit.adapters.github_scenarios import Scenario, session


@pytest.mark.parametrize("visibility", ["public", "private", "internal", None, 42])
@pytest.mark.parametrize("archived", [False, True])
def test_visibility_passes_unchanged_to_security(visibility, archived, config):
    scenario = Scenario(visibility=visibility, archived=archived, files=[{"path": "README.md"}])
    adapter = GitHubRepoFilesAdapter()
    item = list_all(adapter, config, session(adapter, scenario.transport(), config)).items[0]
    assert item.access == (
        AccessInfo(AccessStatus.PROVIDED, (("visibility", visibility),))
        if isinstance(visibility, str)
        else AccessInfo(AccessStatus.UNKNOWN)
    )
    assert item.origin_state == (OriginState.ARCHIVED if archived else OriginState.ACTIVE)
    transport = scenario.transport()
    policy = SecurityPolicy()
    result = screen_source(adapter, config, session(adapter, transport, config), policy)
    verdict = result.verdicts[0]
    if visibility == "public":
        assert verdict.verdict == Verdict.PASSED
        record = verdict.to_dict(policy.output_context(config.kind))
        assert record["source_id"] == item.source_id and record["url"] == item.url
        assert len(result.passed) == 1
    else:
        assert verdict.verdict == Verdict.ACCESS_HELD and not result.passed
        assert not any("/git/blobs/" in request.url for request in transport.requests)
