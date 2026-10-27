"""청커 나눠 주기(QK-CHK-001 contracts 6절, spec FR-001·002, US6-2, tasks T010)."""

import pytest

from qello_knowledge.chunking import service
from qello_knowledge.chunking.version import index_chunking_version
from qello_knowledge.domain.chunking import (
    ChunkingSettings,
    ChunkOutcome,
    ChunkOutcomeKind,
    CodeChunkingSettings,
)
from qello_knowledge.domain.embedding import MODELS
from tests.unit.chunking.code import fresh
from tests.unit.chunking.code.fresh import run_fresh
from tests.unit.chunking.helpers import screened

JAVA = "class A {\n    void f() {\n        g();\n    }\n}\n"
MARKDOWN = "# 제목\n\n본문 줄\n"


def batch():
    return [
        screened(MARKDOWN, location="docs/a.md"),
        screened(JAVA, content_format="CODE", location="src/A.java"),
        screened("class K {\n}\n", content_format="CODE", location="app/K.kt"),
        screened("print(1)\n", content_format="CODE", location="tools/a.py"),
        screened("plugins {}\n", content_format="CODE", location="build.gradle.kts"),
        screened("apply plugin\n", content_format="CODE", location="build.gradle"),
        screened("{}", content_format="JSON", location="a.json"),
        screened("text", content_format="TEXT", location="a.txt"),
    ]


@pytest.fixture
def calls(monkeypatch):
    seen = []

    def fake(body, *, location, settings, code):
        seen.append((location, settings, code))
        return ChunkOutcome(ChunkOutcomeKind.EMPTY, None, (), (), None, 0, "chk-code-fake")

    monkeypatch.setattr(service, "chunk_code", fake)
    return seen


def test_off_keeps_code_not_target(calls):
    result = service.chunk_screened(batch(), ChunkingSettings())
    assert calls == []
    assert [r.outcome for r in result.results] == [ChunkOutcomeKind.CHUNKED] + [ChunkOutcomeKind.NOT_MARKDOWN] * 7
    assert all(not r.drafts for r in result.results[1:])
    assert result.summary.chunking_version == "chk-md-20d966f730bb"
    assert result.summary.code_chunking_version is None


def test_on_sends_only_java_and_kotlin(calls):
    settings, code = ChunkingSettings(), CodeChunkingSettings()
    result = service.chunk_screened(batch(), settings, code=code)
    assert [c[0] for c in calls] == ["src/A.java", "app/K.kt"]
    assert all(c[1] is settings and c[2] is code for c in calls)
    assert [r.outcome for r in result.results] == [
        ChunkOutcomeKind.CHUNKED,
        ChunkOutcomeKind.EMPTY,
        ChunkOutcomeKind.EMPTY,
        *[ChunkOutcomeKind.NOT_MARKDOWN] * 5,
    ]
    assert result.summary.chunking_version == index_chunking_version(settings, code)
    assert result.summary.code_chunking_version.startswith("chk-code-")


def test_markdown_results_are_identical(calls):
    off = service.chunk_screened(batch()[:1], ChunkingSettings())
    on = service.chunk_screened(batch()[:1], ChunkingSettings(), code=CodeChunkingSettings())
    assert off.results[0].drafts == on.results[0].drafts
    assert off.results[0].chunking_version == on.results[0].chunking_version == "chk-md-20d966f730bb"


def test_empty_batch_summary_version():
    assert service.chunk_screened([], ChunkingSettings(), code=CodeChunkingSettings()).summary.chunking_version == ""


def test_model_mismatch_and_keyword_only(monkeypatch, calls):
    from dataclasses import replace

    monkeypatch.setitem(MODELS, "test-model", replace(MODELS["@cf/baai/bge-m3"], model_version="test-model"))
    with pytest.raises(ValueError):
        service.chunk_screened(batch(), ChunkingSettings(), code=CodeChunkingSettings(model_version="test-model"))
    assert calls == []
    with pytest.raises(TypeError):
        service.chunk_screened(batch(), ChunkingSettings(), CodeChunkingSettings())


def test_off_does_not_import_parser():
    assert run_fresh(fresh.after_off_chunking) == []
