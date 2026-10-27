"""상한·나누기·대체 청킹·실패(QK-CHK-001 spec SC-004·SC-005, FR-016~019, US5, tasks T037).

T036 픽스처의 전체 비교는 `test_code_expected.py`가 한다. 여기서는 모든 픽스처에 걸친 크기 불변식을 본다.
"""

import itertools

import pytest

from qello_knowledge.domain.chunking import ChunkOutcomeKind
from qello_knowledge.domain.embedding import MODELS
from qello_knowledge.embedding.estimate import estimated_tokens
from tests.unit.chunking.code.helpers import cases, run, settings_of

CASES = list(cases())
IDS = [c[0] for c in CASES]


def source_runs(result):
    """같은 심볼 경로·종류가 이어지는 원문 청크 묶음."""
    sources = [d for d in result.drafts if not d.chunk.locator["code"]["summary"]]

    def key(d):
        return d.chunk.heading_path, d.chunk.locator["code"]["chunk_kind"]

    return [list(group) for _, group in itertools.groupby(sources, key=key)]


@pytest.mark.parametrize(("name", "body", "case"), CASES, ids=IDS)
def test_every_chunk_is_within_limit(name, body, case):
    result = run(body, case)
    _, code = settings_of(case)
    for draft in result.drafts:
        assert draft.estimated_tokens == estimated_tokens(draft.embedding_text, MODELS[code.model_version])
        assert draft.estimated_tokens <= code.limit_tokens, (name, draft.chunk.ordinal)


@pytest.mark.parametrize(("name", "body", "case"), CASES, ids=IDS)
def test_split_blocks_counts_split_source_chunks(name, body, case):
    result = run(body, case)
    runs = [r for r in source_runs(result) if r[0].chunk.locator["code"]["chunk_kind"] != "FALLBACK"]
    assert result.split_blocks == sum(len(r) > 1 for r in runs), name


def test_members_under_limit_are_not_split():
    for name, body, case in CASES:
        if case["input"].get("code_settings"):
            continue
        result = run(body, case)
        for group in source_runs(result):
            kind = group[0].chunk.locator["code"]["chunk_kind"]
            if kind in ("METHOD", "CONSTRUCTOR", "TOP_FUNCTION", "INITIALIZER"):
                assert len(group) == 1, (name, group[0].chunk.heading_path)


def test_big_method_pieces_repeat_signature_and_keep_closing_line():
    name, body, case = next(c for c in CASES if c[0] == "size_big_method")
    result = run(body, case)
    [pieces] = [g for g in source_runs(result) if len(g) > 1]
    assert len(pieces) >= 3 and result.split_blocks == 1
    assert pieces[0].chunk.body.startswith("    void run() {")
    assert pieces[-1].chunk.body.endswith("    }\n}")
    for piece in pieces[1:]:
        assert piece.embedding_text.split("\n\n", 1)[1].startswith("class Big {\n    void run() {\n")
        assert "void run()" not in piece.chunk.body


def test_fallback_chunks_have_no_symbols_and_no_summary():
    for name in ("fallback_unbalanced", "fallback_unbalanced_kotlin"):
        _, body, case = next(c for c in CASES if c[0] == name)
        result = run(body, case)
        assert result.outcome == ChunkOutcomeKind.CHUNKED and result.warnings[0].kind == "PARSE_FALLBACK"
        for draft in result.drafts:
            assert draft.chunk.heading_path == ()
            assert draft.chunk.locator["code"]["chunk_kind"] == "FALLBACK"
            assert draft.chunk.locator["code"]["summary"] is False


@pytest.mark.parametrize(
    ("name", "failure"), [("size_line_too_long", "LINE_TOO_LONG"), ("size_header_too_long", "HEADER_TOO_LONG")]
)
def test_failures_have_no_chunks(name, failure):
    _, body, case = next(c for c in CASES if c[0] == name)
    result = run(body, case)
    assert (result.outcome, result.failure, result.drafts, result.warnings) == ("FAILED", failure, (), ())


def test_context_omission_keeps_file():
    _, body, case = next(c for c in CASES if c[0] == "size_long_class_annotation")
    result = run(body, case)
    method = next(d for d in result.drafts if d.chunk.locator["code"]["chunk_kind"] == "METHOD")
    assert "@Schema" not in method.embedding_text and "static class Inner" in method.embedding_text
    assert [(w.kind, w.line) for w in result.warnings] == [("CONTEXT_OMITTED", method.chunk.locator["lines"][0])]
