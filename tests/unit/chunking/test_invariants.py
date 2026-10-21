import pytest

from qello_knowledge.chunking import chunk_markdown, chunking_version
from qello_knowledge.chunking.blocks import parse_document
from qello_knowledge.chunking.sections import split_sections
from qello_knowledge.domain.embedding import MODELS
from qello_knowledge.domain.store import validate_chunks
from qello_knowledge.embedding.estimate import estimated_tokens
from tests.unit.chunking.helpers import cases, kwargs


@pytest.mark.parametrize("name,body,case", list(cases()))
def test_invariants(name, body, case):
    inputs = kwargs(case)
    result = chunk_markdown(body, **inputs)
    if result.outcome != "CHUNKED":
        assert not result.drafts
        return
    lines = body.replace("\r\n", "\n").replace("\r", "\n").removeprefix("\ufeff").split("\n")
    covered = []
    for i, draft in enumerate(result.drafts):
        chunk = draft.chunk
        start, end = chunk.locator["lines"]
        assert chunk.ordinal == i
        assert chunk.locator["path"] == inputs["location"]
        assert chunk.body == "\n".join(lines[start - 1 : end])
        assert lines[start - 1].strip() and lines[end - 1].strip()
        covered.extend(range(start, end + 1))
        assert chunk.chunking_version == chunking_version(inputs["settings"])
        assert draft.estimated_tokens == estimated_tokens(
            draft.embedding_text, MODELS[inputs["settings"].model_version]
        )
    assert all(covered.count(i + 1) == 1 for i, line in enumerate(lines) if line.strip())
    validate_chunks("v1", [d.chunk for d in result.drafts])
    for section in split_sections(parse_document(lines).blocks):
        assert any(
            d.chunk.heading_path == section.heading_path and d.chunk.locator["lines"][0] == section.blocks[0].start + 1
            for d in result.drafts
        )
