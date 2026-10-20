from dataclasses import replace

import pytest

from qello_knowledge.chunking import chunk_markdown, service
from qello_knowledge.chunking.blocks import parse_document
from qello_knowledge.domain.chunking import ChunkingSettings, StructureWarning, StructureWarningKind
from tests.unit.chunking.helpers import FIXTURES


@pytest.mark.parametrize(
    "body,line",
    [
        ("```\nx\n```\n", None),
        ("```\n```\n", None),
        ("```\n\n```\n", None),
        ("> ```\n> x\n> ```\n", None),
        ("- ```\n  x\n  ```\n", None),
        ("```\nx\n```", None),
        ("```\nx\u2028y\n```", None),
        ("```\nx\vy\n```", None),
        ("~~~\nx\n~~~~", None),
        ("```", 1),
        ("```\nx\n", 1),
        ("```\nx", 1),
        ("```\nx\n\n", 1),
        ("```\nx\n    ```", 1),
        ("```\nx\n> ````", 1),
        ("> ```\n> x\n\noutside", 1),
    ],
)
def test_fence_closure(body, line):
    r = chunk_markdown(body, location="a.md", source_title="T", settings=ChunkingSettings())
    assert r.outcome == "CHUNKED"
    assert [(w.kind, w.line) for w in r.warnings] == ([] if line is None else [("UNCLOSED_FENCE", line)])


@pytest.mark.parametrize(
    "body,warnings",
    [
        ("| a | b |\n| - | - |\n| x | y |", []),
        ("> a | b\n> --- | ---\n> | x | y |", []),
        ("- a | b\n  --- | ---\n  x | y", []),
        ("- > a | b\n  > --- | ---\n  > | x | y |", []),
        ("1. a | b\n   --- | ---\n   x | y", []),
        ("a | b\n--- | ---\nonecell", [("TABLE_CELL_MISMATCH", 3)]),
        ("a | b\n- | -\nonecell", []),
        ("a | b\n--- | ---\nx \\| y | z", []),
    ],
)
def test_table_cells(body, warnings):
    r = chunk_markdown(body, location="a.md", source_title="T", settings=ChunkingSettings())
    assert r.outcome == "CHUNKED"
    if body != "a | b\n- | -\nonecell":
        assert len(parse_document(body.split("\n")).tables) == 1
    assert [(w.kind, w.line) for w in r.warnings] == warnings


def test_warning_rules_do_not_change_chunks_or_version(monkeypatch):
    body = "a | b\n- | -\nonecell\n\n```\nunclosed"
    kw = dict(location="a.md", source_title="T", settings=ChunkingSettings())
    a = chunk_markdown(body, **kw)
    monkeypatch.setattr(
        service, "structure_warnings", lambda *a: (StructureWarning(StructureWarningKind.UNCLOSED_FENCE, 99),)
    )
    b = chunk_markdown(body, **kw)
    assert a.warnings != b.warnings
    assert replace(a, warnings=b.warnings) == b


def test_language_independent_boundaries():
    results = []
    for name in ("lang_mermaid", "lang_css"):
        body = (FIXTURES / (name + ".md")).read_text()
        r = chunk_markdown(body, location="a.md", source_title=None, settings=ChunkingSettings())
        assert r.drafts[0].chunk.body == body
        results.append([(d.chunk.locator, d.chunk.heading_path) for d in r.drafts])
    assert results[0] == results[1]
