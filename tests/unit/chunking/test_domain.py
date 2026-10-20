from dataclasses import FrozenInstanceError, replace

import pytest

from qello_knowledge.domain.chunking import (
    ChunkDraft,
    ChunkedContent,
    ChunkFailureKind,
    ChunkingSettings,
    ChunkingSummary,
    ChunkOutcome,
    ChunkOutcomeKind,
    StructureWarning,
    StructureWarningKind,
)
from qello_knowledge.domain.store import ChunkInput


def draft(tokens=10):
    return ChunkDraft(
        ChunkInput(0, {"path": "a", "lines": [1, 1]}, "BODY-MARKER", "SEARCH-MARKER", "v"),
        "HEADER-MARKER",
        "EMBED-MARKER",
        tokens,
    )


def outcome(**kwargs):
    return ChunkOutcome(
        outcome=ChunkOutcomeKind.CHUNKED,
        document_title="title",
        drafts=(draft(),),
        warnings=(),
        failure=None,
        split_blocks=0,
        chunking_version="v",
        **kwargs,
    )


def test_settings():
    assert ChunkingSettings().limit_tokens == 2800
    with pytest.raises(FrozenInstanceError):
        ChunkingSettings().target_tokens = 1


@pytest.mark.parametrize(
    "kw",
    [
        {"target_tokens": 0},
        {"target_tokens": 81, "limit_tokens": 80},
        {"limit_tokens": 2900},
        {"model_version": "missing"},
    ],
)
def test_invalid_settings(kw):
    with pytest.raises(ValueError):
        ChunkingSettings(**kw)


def test_repr_hides_payloads():
    for value in (draft(), outcome()):
        assert all(
            marker not in repr(value) for marker in ("BODY-MARKER", "SEARCH-MARKER", "HEADER-MARKER", "EMBED-MARKER")
        )


@pytest.mark.parametrize(
    "kw",
    [
        {"outcome": ChunkOutcomeKind.EMPTY},
        {"outcome": ChunkOutcomeKind.NOT_MARKDOWN},
        {"outcome": ChunkOutcomeKind.FAILED},
        {"failure": ChunkFailureKind.LINE_TOO_LONG},
        {"outcome": ChunkOutcomeKind.CHUNKED, "drafts": ()},
        {"outcome": ChunkOutcomeKind.EMPTY, "drafts": (), "split_blocks": 1},
        {"outcome": ChunkOutcomeKind.FAILED, "drafts": ()},
    ],
)
def test_outcome_invariants(kw):
    with pytest.raises(ValueError):
        replace(outcome(), **kw)


def test_summary_counts_and_lower_median():
    a = ChunkedContent(screened=None, **outcome().__dict__)
    b = replace(
        a, drafts=(draft(30),), split_blocks=2, warnings=(StructureWarning(StructureWarningKind.UNCLOSED_FENCE, 1),)
    )
    c = replace(a, outcome=ChunkOutcomeKind.FAILED, drafts=(), failure=ChunkFailureKind.LINE_TOO_LONG)
    summary = ChunkingSummary.from_results((a, b, c))
    assert summary.by_outcome == {"CHUNKED": 2, "FAILED": 1}
    assert summary.by_failure == {"LINE_TOO_LONG": 1}
    assert summary.by_warning == {"UNCLOSED_FENCE": 1}
    assert summary.chunk_count == 2 and summary.split_blocks == 2
    assert (summary.tokens_min, summary.tokens_median, summary.tokens_max) == (10, 10, 30)
    assert ChunkingSummary.from_results((c,)).tokens_min is None
