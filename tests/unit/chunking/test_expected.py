import pytest

from qello_knowledge.chunking import chunk_markdown
from tests.unit.chunking.helpers import cases, kwargs


@pytest.mark.parametrize("name,body,case", list(cases()))
def test_expected(name, body, case):
    result = chunk_markdown(body, **kwargs(case))
    expected = case["expected"]
    assert result.outcome == expected["outcome"], name
    assert result.failure == expected.get("failure")
    assert [{"kind": w.kind, "line": w.line} for w in result.warnings] == expected["warnings"]
    assert len(result.drafts) == len(expected.get("chunks", []))
    for draft, oracle in zip(result.drafts, expected.get("chunks", []), strict=True):
        actual = dict(
            ordinal=draft.chunk.ordinal,
            lines=draft.chunk.locator["lines"],
            heading_path=list(draft.chunk.heading_path),
            search_header=draft.search_header,
            search_text=draft.chunk.search_text,
            embedding_text=draft.embedding_text,
        )
        assert {k: actual[k] for k in oracle} == oracle


def assert_required_keys(case):
    expected = case["expected"]
    assert {"outcome", "warnings"} <= expected.keys()
    if expected["outcome"] == "CHUNKED":
        assert expected["chunks"]
        for chunk in expected["chunks"]:
            assert {
                "ordinal",
                "lines",
                "heading_path",
                "search_header",
                "search_text",
                "embedding_text",
            } <= chunk.keys()
    if expected["outcome"] == "FAILED":
        assert "failure" in expected


def test_fixture_schema():
    for _, _, case in cases():
        assert_required_keys(case)


@pytest.mark.parametrize(
    "key",
    [
        "outcome",
        "warnings",
        "ordinal",
        "lines",
        "heading_path",
        "search_header",
        "search_text",
        "embedding_text",
        "failure",
    ],
)
def test_missing_oracle_key_fails(key):
    import copy

    case = copy.deepcopy(
        next(c for _, _, c in cases() if c["expected"]["outcome"] == ("FAILED" if key == "failure" else "CHUNKED"))
    )
    if key in ("outcome", "warnings", "failure"):
        del case["expected"][key]
    else:
        del case["expected"]["chunks"][0][key]
    with pytest.raises(AssertionError):
        assert_required_keys(case)
