"""사람이 쓴 기대값과 비교한다(QK-CHK-001 spec SC-001, tasks T013·T047)."""

import copy

import pytest

from tests.unit.chunking.code.helpers import CHUNK_KEYS, assert_matches, cases, run

CODE_KEYS = (
    "language",
    "package",
    "symbol",
    "signature",
    "chunk_kind",
    "type_kind",
    "type_modifiers",
    "annotations",
    "test_code",
    "test_method",
    "display_name",
    "component",
    "summary",
)


@pytest.mark.parametrize(("name", "body", "case"), list(cases()), ids=[c[0] for c in cases()])
def test_expected(name, body, case):
    assert_matches(name, run(body, case), case["expected"])


def assert_required_keys(case):
    expected = case["expected"]
    assert {"outcome", "document_title", "warnings"} <= expected.keys()
    if expected["outcome"] == "CHUNKED":
        assert expected["chunks"]
        for chunk in expected["chunks"]:
            assert {*CHUNK_KEYS, "code"} <= chunk.keys()
            assert set(CODE_KEYS) <= chunk["code"].keys()
    if expected["outcome"] == "FAILED":
        assert "failure" in expected


def test_fixture_schema():
    assert len(list(cases())) >= 40
    for _, _, case in cases():
        assert_required_keys(case)


@pytest.mark.parametrize("key", ["outcome", "document_title", "warnings", *CHUNK_KEYS, "code", *CODE_KEYS])
def test_missing_oracle_key_fails(key):
    case = copy.deepcopy(next(c for _, _, c in cases() if c["expected"]["outcome"] == "CHUNKED"))
    if key in ("outcome", "document_title", "warnings"):
        del case["expected"][key]
    elif key in CODE_KEYS:
        del case["expected"]["chunks"][0]["code"][key]
    else:
        del case["expected"]["chunks"][0][key]
    with pytest.raises(AssertionError):
        assert_required_keys(case)


def test_missing_failure_key_fails():
    case = copy.deepcopy(next(c for _, _, c in cases() if c["expected"]["outcome"] == "FAILED"))
    del case["expected"]["failure"]
    with pytest.raises(AssertionError):
        assert_required_keys(case)
