"""보안 필터 시험 fixture. 도우미 함수는 helpers.py에 있다."""

import pytest

from qello_knowledge.adapters.fake import FakeSourceAdapter
from qello_knowledge.sources.session import DefaultSourceSession
from tests.unit.security.helpers import FakeClock, fake_config, load_transport, team_policy


@pytest.fixture
def screen():
    def run(name, policy=None, config=None, secrets=None):
        from qello_knowledge.security.screen import screen_source

        transport = load_transport(name, secrets)
        config = config or fake_config()
        adapter = FakeSourceAdapter()
        session = DefaultSourceSession(transport, adapter, config, FakeClock(), jitter=lambda cap: cap / 2)
        result = screen_source(adapter, config, session, policy or team_policy())
        return result, transport

    return run
