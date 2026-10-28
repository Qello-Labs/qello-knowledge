"""Confluence 어댑터 공통 계약(QK-ING-003 FR-029, SC-009). 재생 응답만 쓴다."""

from urllib.parse import urlsplit

import pytest

from qello_knowledge.domain.source import ContentFormat
from tests.contract.source_adapter_contract import ContractExpectations, SourceAdapterContract
from tests.unit.adapters import confluence_scenarios as cf


def scenario(*, restriction="OPEN", invalid=None):
    # 홈("1")이 목록에 없어 모든 항목의 상위 사슬이 같은 모양이다. 원값이 항목마다 같게 하려는 것이다.
    pages = [
        {
            "id": str(n),
            "title": f"문서 {n}",
            "parent_id": "1",
            "restriction": restriction,
            "body": {"type": "paragraph"} if str(n) == invalid else cf.doc(cf.paragraph(f"본문 {n}")),
        }
        for n in range(2, 7)
    ]
    built = cf.Scenario(pages=pages)
    if restriction == "FAIL":
        for page in pages:
            built.override(f"{cf.BASE}/pages/{page['id']}/restriction-state", status=403)
    return built


class TestConfluenceAdapterContract(SourceAdapterContract):
    @pytest.fixture
    def adapter(self):
        return cf.adapter()

    @pytest.fixture
    def transport(self):
        return scenario().transport()

    @pytest.fixture
    def config(self):
        return cf.config()

    @pytest.fixture
    def expected(self):
        return ContractExpectations(
            5,
            "1",
            (
                ("judge_mode", "site_users"),
                ("space_type", "global"),
                ("space_status", "current"),
                ("site_review_valid", "true"),
                ("read_restricted", "unknown"),
                ("ancestor_count", "0"),
            ),
            ContentFormat.MARKDOWN,
            f"{cf.BASE}/spaces",
            {
                "no_modified_at": None,
                "page_overlap": None,
                "no_access": scenario(restriction="FAIL"),
                "invalid_shape": scenario(invalid="3"),
            },
            None,
        )

    def test_all_requests_use_get_and_the_gateway_host(self, adapter, transport, config):
        from qello_knowledge.sources.collect import fetch_contents, list_all

        run = self.session(adapter, transport, config)
        fetch_contents(adapter, config, run, list_all(adapter, config, run).items)
        assert all(
            request.method == "GET" and urlsplit(request.url).hostname == "api.atlassian.com"
            for request in transport.requests
        )
