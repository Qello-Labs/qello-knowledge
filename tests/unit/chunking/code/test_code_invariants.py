"""모든 코드 픽스처의 불변식(QK-CHK-001 spec SC-001·SC-002, contracts 5절, tasks T014)."""

from collections import Counter

import pytest

from qello_knowledge.chunking import chunk_screened
from qello_knowledge.chunking.code.version import code_chunking_version
from qello_knowledge.domain.chunking import ChunkOutcomeKind
from qello_knowledge.domain.store import validate_chunks
from tests.unit.chunking.code.helpers import cases, run, settings_of
from tests.unit.chunking.helpers import screened

CASES = list(cases())
IDS = [c[0] for c in CASES]


@pytest.mark.parametrize(("name", "body", "case"), CASES, ids=IDS)
def test_source_chunks_cover_lines_once(name, body, case):
    result = run(body, case)
    settings, code = settings_of(case)
    assert result.chunking_version == code_chunking_version(code, settings)
    if result.outcome != ChunkOutcomeKind.CHUNKED:
        assert result.drafts == ()
        return
    lines = body.replace("\r\n", "\n").removeprefix("﻿").split("\n")
    covered = Counter()
    assert [d.chunk.ordinal for d in result.drafts] == list(range(len(result.drafts)))
    validate_chunks("v1", [d.chunk for d in result.drafts])
    for draft in result.drafts:
        chunk = draft.chunk
        start, end = chunk.locator["lines"]
        assert chunk.chunking_version == result.chunking_version
        assert draft.embedding_text.startswith(draft.search_header)
        assert chunk.search_text.startswith(draft.search_header)
        assert chunk.locator["path"] == case["input"]["location"]
        if chunk.locator["code"]["summary"]:
            continue
        assert chunk.body == "\n".join(lines[start - 1 : end]), (name, chunk.ordinal)
        assert lines[start - 1].strip() and lines[end - 1].strip()
        covered.update(range(start, end + 1))
    filled = {n for n, line in enumerate(lines, 1) if line.strip()}
    assert {n for n in covered if n in filled} == filled, name
    assert all(covered[n] == 1 for n in filled), name


@pytest.mark.parametrize(("name", "body", "case"), CASES, ids=IDS)
def test_line_endings_and_bom_do_not_change_result(name, body, case):
    lf = run(body, case)
    assert run(body, case) == lf
    assert run(body.replace("\n", "\r\n"), case) == lf
    assert run("﻿" + body, case) == lf


def test_batch_order_does_not_change_results():
    groups = {}
    for name, body, case in CASES:
        settings, code = settings_of(case)
        groups.setdefault((settings, code), []).append((name, body, case))
    for (settings, code), members in groups.items():
        batch = [screened(b, content_format="CODE", location=c["input"]["location"]) for _, b, c in members]
        forward = chunk_screened(batch, settings, code=code).results
        backward = chunk_screened(list(reversed(batch)), settings, code=code).results
        for a, b in zip(forward, reversed(backward), strict=True):
            assert a.drafts == b.drafts and a.warnings == b.warnings and a.outcome == b.outcome


def test_empty_versions():
    _, _, case = CASES[0]
    settings, code = settings_of(case)
    for body in ("", "  \n\t\n"):
        result = run(body, case)
        assert result.outcome == ChunkOutcomeKind.EMPTY
        assert result.chunking_version == code_chunking_version(code, settings)
