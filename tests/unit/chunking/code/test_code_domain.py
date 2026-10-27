"""코드 청킹 도메인 타입과 요약 셈(QK-CHK-001 data-model, tasks T004)."""

from dataclasses import asdict, replace

import pytest

from qello_knowledge.domain.chunking import (
    AndroidComponent,
    ChunkDraft,
    ChunkedContent,
    ChunkingSettings,
    ChunkingSummary,
    ChunkOutcomeKind,
    CodeChunkingSettings,
    CodeChunkKind,
    StructureWarningKind,
)
from qello_knowledge.domain.embedding import MODELS
from qello_knowledge.domain.store import ChunkInput
from tests.unit.chunking.helpers import screened


def test_code_settings_defaults():
    code = CodeChunkingSettings()
    assert (code.model_version, code.target_tokens, code.limit_tokens) == ("@cf/baai/bge-m3", 512, 1500)


@pytest.mark.parametrize(
    "kw",
    [
        {"model_version": "missing"},
        {"target_tokens": 0},
        {"target_tokens": 1501},
        {"target_tokens": 10, "limit_tokens": 9},
        {"limit_tokens": 2809},  # 2809 × 3.5 ÷ 1.2 > 8192
    ],
)
def test_invalid_code_settings(kw):
    with pytest.raises(ValueError):
        CodeChunkingSettings(**kw)


def test_code_settings_safety_boundary():
    assert CodeChunkingSettings(limit_tokens=2808).limit_tokens == 2808


def test_enum_values():
    assert [k.value for k in CodeChunkKind] == [
        "FILE_HEAD",
        "FILE_SUMMARY",
        "TYPE_SUMMARY",
        "TYPE_HEAD",
        "METHOD",
        "CONSTRUCTOR",
        "TOP_FUNCTION",
        "FIELDS",
        "TOP_PROPERTIES",
        "INITIALIZER",
        "FALLBACK",
    ]
    assert len(AndroidComponent) == 8
    assert {"TABLE_CELL_MISMATCH", "UNCLOSED_FENCE", "PARSE_FALLBACK", "CONTEXT_OMITTED"} == {
        k.value for k in StructureWarningKind
    }


def test_chunking_settings_unchanged():
    # 측정 출력(devtools/measure.py)의 고정값이 그대로이려면 키 4개가 그대로여야 한다(plan 검토 H1).
    assert asdict(ChunkingSettings()) == {
        "model_version": "@cf/baai/bge-m3",
        "target_tokens": 512,
        "limit_tokens": 2800,
        "keyword_text_rule": "kw-index-baseline-v1",
    }


def code(kind, *, component="", test_code=False, summary=False):
    return {
        "language": "kotlin",
        "package": "",
        "symbol": "",
        "signature": "",
        "chunk_kind": kind,
        "type_kind": "",
        "type_modifiers": [],
        "annotations": [],
        "test_code": test_code,
        "test_method": False,
        "display_name": "",
        "component": component,
        "summary": summary,
    }


def draft(ordinal, path, meta=None):
    locator = {"path": "a.kt", "lines": [1, 1]}
    if meta is not None:
        locator["code"] = meta
    return ChunkDraft(ChunkInput(ordinal, locator, "b", "s", "v", tuple(path)), "h", "e", 3)


def result(*drafts, outcome=ChunkOutcomeKind.CHUNKED, version="chk-code-x"):
    return ChunkedContent(
        outcome=outcome,
        document_title=None,
        drafts=tuple(drafts),
        warnings=(),
        failure=None,
        split_blocks=0,
        chunking_version=version,
        screened=screened("x"),
    )


def test_summary_defaults_and_versions():
    empty = ChunkingSummary.from_results(())
    assert empty.chunking_version == ""
    assert (empty.code_chunking_version, dict(empty.by_code_kind), empty.code_test_chunks) == (None, {}, 0)
    assert dict(empty.code_components) == {}
    one = result(draft(0, ["A"]), version="chk-md-1")
    assert ChunkingSummary.from_results([one]).chunking_version == "chk-md-1"
    given = ChunkingSummary.from_results([one], chunking_version="chk-md-1+chk-code-2", code_chunking_version="c")
    assert (given.chunking_version, given.code_chunking_version) == ("chk-md-1+chk-code-2", "c")


def test_summary_code_counts():
    vm = AndroidComponent.VIEW_MODEL.value
    composable = AndroidComponent.COMPOSABLE.value
    chunks = [
        draft(0, [], code("FILE_HEAD")),
        draft(1, ["LoginViewModel"], code("TYPE_SUMMARY", component=vm, summary=True)),
        draft(2, ["LoginViewModel"], code("TYPE_HEAD", component=vm)),
        draft(3, ["LoginViewModel"], code("TYPE_HEAD", component=vm)),  # 나뉜 형식 머리의 뒤 조각
        draft(4, ["LoginViewModel", "load()"], code("METHOD", component=vm, test_code=True)),
        draft(5, ["Screen.kt", "Screen()"], code("TOP_FUNCTION", component=composable)),
        draft(6, ["Screen.kt", "Screen()"], code("TOP_FUNCTION", component=composable)),
        draft(7, ["Screen.kt", "Other()"], code("TOP_FUNCTION", component=composable)),
        draft(8, ["A"], code("METHOD", component=composable)),
    ]
    markdown = result(draft(0, ["Doc"]), version="chk-md-1")
    summary = ChunkingSummary.from_results([result(*chunks), markdown])
    assert dict(summary.by_code_kind) == {
        CodeChunkKind.FILE_HEAD: 1,
        CodeChunkKind.TYPE_SUMMARY: 1,
        CodeChunkKind.TYPE_HEAD: 2,
        CodeChunkKind.METHOD: 2,
        CodeChunkKind.TOP_FUNCTION: 3,
    }
    assert summary.code_test_chunks == 1
    assert dict(summary.code_components) == {AndroidComponent.VIEW_MODEL: 1, AndroidComponent.COMPOSABLE: 3}
    assert summary.chunk_count == 10


def test_summary_repr_has_no_metadata():
    meta = {**code("METHOD"), "symbol": "QK-CHK-001-LEAK-MARKER"}
    summary = ChunkingSummary.from_results([result(draft(0, ["QK-CHK-001-LEAK-MARKER"], meta))])
    assert "LEAK-MARKER" not in repr(summary)


def test_code_settings_follow_model_table(monkeypatch):
    monkeypatch.setitem(MODELS, "test-model", replace(MODELS["@cf/baai/bge-m3"], model_version="test-model"))
    assert CodeChunkingSettings(model_version="test-model").model_version == "test-model"
