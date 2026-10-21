import pytest

from qello_knowledge.chunking import chunk_markdown, chunk_screened
from qello_knowledge.chunking.blocks import parse_document
from qello_knowledge.chunking.header import embedding_text
from qello_knowledge.domain.chunking import ChunkingSettings
from qello_knowledge.domain.embedding import MODELS
from qello_knowledge.embedding.estimate import estimated_tokens
from tests.unit.chunking.helpers import cases, kwargs, screened


def descendants(block):
    yield block
    for child in block.children:
        yield from descendants(child)


@pytest.mark.parametrize("name,body,case", list(cases()))
def test_size_and_intact_blocks(name, body, case):
    settings = kwargs(case)["settings"]
    r = chunk_markdown(body, **kwargs(case))
    assert r.outcome == case["expected"]["outcome"]
    if r.outcome != "CHUNKED":
        assert not r.drafts and r.split_blocks == 0
        return
    for draft in r.drafts:
        assert draft.estimated_tokens == estimated_tokens(draft.embedding_text, MODELS[settings.model_version])
        assert draft.estimated_tokens <= settings.limit_tokens
    split_count = 0
    lines = body.split("\n")
    for top in parse_document(lines).blocks:
        owners = [
            d for d in r.drafts if d.chunk.locator["lines"][0] <= top.end and d.chunk.locator["lines"][1] > top.start
        ]
        split_count += len(owners) > 1
        for block in descendants(top):
            text = "\n".join(lines[block.start : block.end]).strip("\n")
            # The block is indivisible when its complete embedding input fits the hard limit.
            size = estimated_tokens(embedding_text(owners[0].search_header, "", text), MODELS[settings.model_version])
            if size <= settings.limit_tokens:
                assert (
                    sum(
                        d.chunk.locator["lines"][0] <= block.end and d.chunk.locator["lines"][1] > block.start
                        for d in r.drafts
                    )
                    == 1
                )
    assert r.split_blocks == split_count


@pytest.mark.parametrize(
    "body",
    [
        "x" * 280,
        "```" + "x" * 120 + "\n" + "x" * 155 + "\n```",
        "| " + "a" * 95 + " | b |\n| - | - |\n| " + "x" * 170 + " | y |",
    ],
)
def test_line_and_repeat_prefix_overflow(body):
    # Body row alone fits; adding the required search/repeat header causes the failure.
    r = chunk_markdown(
        body, location="a.md", source_title="T", settings=ChunkingSettings(target_tokens=40, limit_tokens=80)
    )
    assert r.outcome == "FAILED" and r.failure == "LINE_TOO_LONG" and not r.drafts and r.split_blocks == 0


def test_header_limit_and_failure_isolation():
    settings = ChunkingSettings(target_tokens=40, limit_tokens=80)
    rs = chunk_screened(
        [screened("x", location="a" * 280), screened("x" * 280, location="a.md", title="T"), screened("# A")], settings
    ).results
    assert [r.outcome for r in rs] == ["FAILED", "FAILED", "CHUNKED"]
    assert rs[0].failure == "HEADER_TOO_LONG" and rs[1].failure == "LINE_TOO_LONG"


def test_one_section_keeps_its_heading_path():
    r = chunk_markdown(
        "# A\n\n" + "\n\n".join(["x" * 100] * 5),
        location="a.md",
        source_title=None,
        settings=ChunkingSettings(target_tokens=40, limit_tokens=80),
    )
    assert len(r.drafts) > 1
    assert {d.chunk.heading_path for d in r.drafts} == {("A",)}
