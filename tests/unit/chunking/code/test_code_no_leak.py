"""비노출과 실패 격리(QK-CHK-001 spec SC-009, FR-006·007, research R-01, tasks T042).

외부 호출은 `tests/conftest.py`의 소켓 차단이 막는다.
청커는 저장소·제공자를 받지 않으므로 저장·원본 쓰기 호출이 생길 자리가 없다.
"""

import json
import logging

import pytest

from qello_knowledge.chunking import chunk_screened
from qello_knowledge.chunking.code import parse, units
from qello_knowledge.chunking.code.service import chunk_code
from qello_knowledge.domain.chunking import (
    ChunkFailureKind,
    ChunkingSettings,
    ChunkingSummary,
    ChunkOutcomeKind,
    CodeChunkingSettings,
)
from qello_knowledge.sync.report import summary_values
from tests.unit.chunking.helpers import screened

MARKER = "QK-CHK-001-LEAK-MARKER"
IDENT = "QK_CHK_001_LEAK_MARKER"
JAVA = f"""package a;

class {IDENT}Service {{
    @Test
    @DisplayName("{MARKER} 표시 이름")
    void {IDENT}(String {IDENT}Arg) {{
        log("{MARKER}");
    }}
}}
"""
KOTLIN = f"""package a

class Screen {{
    fun `{MARKER} 백틱`() {{
        show("{MARKER}")
    }}
}}
"""
SMALL = CodeChunkingSettings(target_tokens=60, limit_tokens=100)


def outcomes():
    settings, code = ChunkingSettings(), CodeChunkingSettings()
    long_line = JAVA.replace(f'log("{MARKER}");', f'log("{MARKER}{"x" * 600}");')
    nested = (
        f'package a;\n\n@Schema(description = "{MARKER}{"설명" * 40}")\nclass Outer {{\n    static class Inner {{\n'
        f"        void {IDENT}(OrderRequest request, PaymentRequest payment) {{\n"
        "            run();\n        }\n    }\n}\n"
    )
    return [
        chunk_code(JAVA, location="order/src/test/java/a/Service.java", settings=settings, code=code),
        chunk_code(KOTLIN, location="app/src/test/java/a/Screen.kt", settings=settings, code=code),
        chunk_code("  \n", location="a/Empty.java", settings=settings, code=code),
        chunk_code(long_line, location="a/Long.java", settings=settings, code=SMALL),
        chunk_code(JAVA, location="a/" + "d/" * 200 + f"{IDENT}.java", settings=settings, code=SMALL),
        chunk_code(JAVA.replace("}\n}", ")\n}"), location="a/Broken.java", settings=settings, code=code),
        chunk_code(
            nested,
            location="a/Outer.java",
            settings=settings,
            code=CodeChunkingSettings(target_tokens=60, limit_tokens=135),
        ),
    ]


def test_outcomes_cover_every_result_kind():
    results = outcomes()
    assert [r.outcome for r in results] == ["CHUNKED", "CHUNKED", "EMPTY", "FAILED", "FAILED", "CHUNKED", "CHUNKED"]
    assert [r.failure for r in results if r.failure] == ["LINE_TOO_LONG", "HEADER_TOO_LONG"]
    assert {w.kind for r in results for w in r.warnings} == {"PARSE_FALLBACK", "CONTEXT_OMITTED"}
    assert any(MARKER in d.chunk.body for d in results[0].drafts)  # 표지가 결과 안에는 실제로 있다


def test_repr_records_and_logs_have_no_marker(caplog):
    caplog.set_level(logging.DEBUG)
    results = outcomes()
    batch = chunk_screened(
        [screened(JAVA, content_format="CODE", location="order/src/test/java/a/Service.java")],
        ChunkingSettings(),
        code=CodeChunkingSettings(),
    )
    texts = [repr(r) for r in results] + [repr(w) for r in results for w in r.warnings]
    texts += [repr(batch.summary), json.dumps(summary_values(batch.summary), ensure_ascii=False), caplog.text]
    texts += [repr(ChunkingSummary.from_results(batch.results))]
    for text in texts:
        assert MARKER not in text and IDENT not in text


def test_failures_are_isolated_in_a_batch(monkeypatch):
    original = units.Builder.units

    def boom(self):
        if self.location.endswith("Boom.java"):
            raise RuntimeError(MARKER)
        return original(self)

    def broken_import(name):
        if name == "tree_sitter_kotlin":
            raise ImportError(MARKER)
        return __import__(name)

    monkeypatch.setattr(units.Builder, "units", boom)
    monkeypatch.setattr(parse, "_PARSERS", {})
    monkeypatch.setattr(parse, "_import", broken_import)
    batch = [
        screened(JAVA, content_format="CODE", location="a/Boom.java"),
        screened(KOTLIN, content_format="CODE", location="a/Screen.kt"),
        screened(JAVA, content_format="CODE", location="a/Fine.java"),
        screened("# 문서\n\n본문\n", location="docs/a.md"),
        screened(JAVA, content_format="CODE", location="b/Fine.java"),
    ]
    result = chunk_screened(batch, ChunkingSettings(), code=CodeChunkingSettings())
    assert [(r.outcome, r.failure) for r in result.results] == [
        (ChunkOutcomeKind.FAILED, ChunkFailureKind.PROCESSING_ERROR),
        (ChunkOutcomeKind.FAILED, ChunkFailureKind.PROCESSING_ERROR),
        (ChunkOutcomeKind.CHUNKED, None),
        (ChunkOutcomeKind.CHUNKED, None),
        (ChunkOutcomeKind.CHUNKED, None),
    ]
    assert all(not r.drafts for r in result.results[:2])
    assert MARKER not in repr(result.summary)


@pytest.mark.parametrize("value", [MARKER, IDENT])
def test_warning_and_failure_values_carry_only_kind_and_line(value):
    for result in outcomes():
        for warning in result.warnings:
            assert set(vars(warning)) == {"kind", "line"}
        assert value not in str(result.failure)
