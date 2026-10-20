from qello_knowledge.chunking import chunk_markdown
from qello_knowledge.domain.chunking import ChunkingSettings


def run(body):
    return chunk_markdown(body, location="a.md", source_title=None, settings=ChunkingSettings())


def test_section_title_locality():
    body = "# A\nalpha\n## B\nbeta\n### Child\nchild\n## C\ngamma"
    a, b = run(body), run(body.replace("## B", "## New"))
    changed = [x != y for x, y in zip(a.drafts, b.drafts, strict=True)]
    assert changed == [False, True, True, False]
    assert a.drafts[1].search_header == "a.md\nA > B"
    assert b.drafts[1].search_header == "a.md\nA > New"


def test_document_title_changes_every_header():
    a, b = run("# A\n## B\nbody"), run("# New\n## B\nbody")
    assert all(x.search_header != y.search_header for x, y in zip(a.drafts, b.drafts, strict=True))
    assert all("New" in x.search_header for x in b.drafts)
