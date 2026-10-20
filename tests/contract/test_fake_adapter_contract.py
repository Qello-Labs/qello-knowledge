from pathlib import Path

import pytest

from qello_knowledge.adapters.fake import FakeSourceAdapter
from qello_knowledge.adapters.replay import ReplayTransport
from qello_knowledge.domain.source_config import SourceConfig, SourceScope
from tests.contract.source_adapter_contract import ContractExpectations, SourceAdapterContract


class TestFakeAdapterContract(SourceAdapterContract):
    @pytest.fixture
    def adapter(self):
        return FakeSourceAdapter()

    @pytest.fixture
    def transport(self, request):
        name = getattr(request, "param", "basic")
        return ReplayTransport.from_file(Path("tests/fixtures/responses/fake") / f"{name}.json")

    @pytest.fixture
    def config(self):
        return SourceConfig("docs", "fake", True, scope=SourceScope(("**/*.md",)), allowed_hosts=("fake.invalid",))

    @pytest.fixture
    def expected(self):
        return ContractExpectations(
            5,
            "v1",
            (("visibility", "public"),),
            "MARKDOWN",
            "https://fake.invalid/items",
            {
                name: Path("tests/fixtures/responses/fake") / f"{name}.json"
                for name in ("no_modified_at", "no_access", "page_overlap", "invalid_shape")
            },
            12,
        )
