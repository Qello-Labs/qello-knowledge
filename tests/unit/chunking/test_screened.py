from dataclasses import replace

import pytest

from qello_knowledge.chunking import chunk_screened, service
from qello_knowledge.domain.chunking import ChunkingSettings
from tests.unit.chunking.helpers import screened


@pytest.mark.parametrize("fmt", ["CODE", "JSON", "TEXT"])
def test_non_markdown(fmt):
    r = chunk_screened([screened("# A", content_format=fmt)], ChunkingSettings()).results[0]
    assert r.outcome == "NOT_MARKDOWN" and not r.drafts and r.document_title is None


@pytest.mark.parametrize("body", ["", " \n\t\n"])
def test_empty(body):
    r = chunk_screened([screened(body)], ChunkingSettings()).results[0]
    assert r.outcome == "EMPTY" and not r.drafts


def test_failure_isolation(monkeypatch):
    real = service.chunk_markdown

    def injected(body, **kw):
        if body == "fail":
            raise RuntimeError("sensitive error")
        return real(body, **kw)

    monkeypatch.setattr(service, "chunk_markdown", injected)
    rs = chunk_screened([screened("fail"), screened("# A")], ChunkingSettings()).results
    assert rs[0].outcome == "FAILED" and rs[0].failure == "PROCESSING_ERROR" and not rs[0].drafts
    assert rs[1].outcome == "CHUNKED"


def test_source_independence_and_content_location():
    a = screened("# A", kind="fake-one")
    b = screened("# A", kind="fake-two")
    rs = chunk_screened([a, b], ChunkingSettings()).results
    assert replace(rs[0], screened=b) == rs[1]
    assert rs[0].drafts[0].chunk.locator["path"] == a.content.location != a.item.location
