from hashlib import sha256

import pytest

from qello_knowledge.domain.source import ContentFormat, SourceContent, content_hash
from qello_knowledge.domain.source_config import SourceConfig
from qello_knowledge.sources.session import DefaultSourceSession
from tests.unit.sources.conftest import FakeClock


@pytest.mark.parametrize("body", ["", "# 제목\n"])
def test_shared_hash_and_session_finalization(body):
    expected = "sha256:" + sha256(body.encode("utf-8")).hexdigest()
    assert content_hash(body) == expected
    run = DefaultSourceSession(None, None, SourceConfig("docs", "fake", True), FakeClock())
    content = run.finalize_content(SourceContent("1", body, ContentFormat.MARKDOWN, None, "a.md", None))
    assert content.content_hash == expected and content.fetched_at == run.clock.now()
