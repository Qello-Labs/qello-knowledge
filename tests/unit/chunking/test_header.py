import pytest

from qello_knowledge.chunking import chunk_markdown, chunk_screened
from qello_knowledge.domain.chunking import ChunkingSettings
from tests.unit.chunking.helpers import cases, kwargs, screened


@pytest.mark.parametrize(
    "source,body,title",
    [
        ("Origin", "---\ntitle: Metadata\n---\n# First", "Origin"),
        (None, "---\ntitle: Metadata\n---\n# First", "Metadata"),
        ("", '---\ntitle: ""\n---\n# First', "First"),
        (None, "## Second\n# First", "First"),
        (None, "plain", "sample.md"),
    ],
)
def test_title_priority(source, body, title):
    result = chunk_markdown(body, location="docs/sample.md", source_title=source, settings=ChunkingSettings())
    assert result.document_title == title


@pytest.mark.parametrize("content_title,item_title,expected", [("Content", "Item", "Content"), (None, "Item", "Item")])
def test_screened_title(content_title, item_title, expected):
    result = chunk_screened([screened("# A", title=content_title, item_title=item_title)], ChunkingSettings())
    assert result.results[0].document_title == expected


def test_all_headers_and_empty_parents():
    for _, body, case in cases():
        r = chunk_markdown(body, **kwargs(case))
        for d in r.drafts:
            assert d.embedding_text.startswith(d.search_header + "\n\n")
            assert d.chunk.search_text.startswith(d.search_header + "\n\n")
            assert r.document_title
    r = chunk_markdown("# A\n## B\n### C", location="a.md", source_title=None, settings=ChunkingSettings())
    assert [d.chunk.heading_path for d in r.drafts] == [("A",), ("A", "B"), ("A", "B", "C")]
