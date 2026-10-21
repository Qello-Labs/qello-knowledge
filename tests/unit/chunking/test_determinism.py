from qello_knowledge.chunking import chunk_markdown, chunk_screened
from qello_knowledge.domain.chunking import ChunkingSettings
from qello_knowledge.domain.store import chunk_set_hash
from tests.unit.chunking.helpers import cases, kwargs, screened


def test_repeat_and_shuffle():
    values = list(cases())
    for _, body, case in values:
        a = chunk_markdown(body, **kwargs(case))
        b = chunk_markdown(body, **kwargs(case))
        assert a == b
        assert chunk_set_hash("v1", "v1", [d.chunk for d in a.drafts]) == chunk_set_hash(
            "v1", "v1", [d.chunk for d in b.drafts]
        )
    items = [screened(body, location=name + ".md") for name, body, _ in values]
    settings = ChunkingSettings()
    first = chunk_screened(items, settings)
    items = items[1::2] + items[::2]
    second = chunk_screened(items, settings)
    assert {r.screened.content.location: r for r in first.results} == {
        r.screened.content.location: r for r in second.results
    }


def test_normalization_and_whitespace():
    text = "# A\n\n\tcode  \n\n## B\nbody  "
    variants = [text, text.replace("\n", "\r\n"), text.replace("\n", "\r"), "\ufeff" + text]
    results = [chunk_markdown(t, location="a.md", source_title=None, settings=ChunkingSettings()) for t in variants]
    assert all(r == results[0] for r in results)
    assert "\tcode  " in results[0].drafts[0].chunk.body
    assert results[0].drafts[1].chunk.body.endswith("body  ")


def test_local_body_edit():
    body = "# A\nalpha\n## B\nbeta\n## C\ngamma"
    a = chunk_markdown(body, location="a.md", source_title=None, settings=ChunkingSettings())
    b = chunk_markdown(body.replace("beta", "changed"), location="a.md", source_title=None, settings=ChunkingSettings())
    for i in (0, 2):
        assert a.drafts[i] == b.drafts[i]
