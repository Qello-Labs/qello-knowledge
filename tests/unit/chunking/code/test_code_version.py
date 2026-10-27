"""코드 청킹 규칙 버전과 인덱스 버전 합치기(QK-CHK-001 contracts 1~3절, research R-08·R-09, tasks T006)."""

import importlib.metadata
import re
from dataclasses import replace

import pytest

from qello_knowledge.chunking import version as md_version
from qello_knowledge.chunking.code import version
from qello_knowledge.chunking.version import index_chunking_version
from qello_knowledge.domain.chunking import ChunkingSettings, CodeChunkingSettings
from qello_knowledge.domain.embedding import MODELS
from qello_knowledge.domain.keyword_rules import INDEX_IDSPLIT
from qello_knowledge.sync.keys import index_version_id, metadata_schema_version
from tests.unit.chunking.code import fresh
from tests.unit.chunking.code.fresh import run_fresh

MD = "chk-md-20d966f730bb"
FIRST_CODE_VERSION = "chk-code-4c1551b7519d"  # 루트 어노테이션 규칙을 더하고 다시 고정했다(2026-10-27, 독립 검토 반영)


def test_format_and_determinism():
    value = version.code_chunking_version(CodeChunkingSettings(), ChunkingSettings())
    assert re.fullmatch(r"chk-code-[0-9a-f]{12}", value)
    assert value == version.code_chunking_version(CodeChunkingSettings(), ChunkingSettings())


def test_first_value():
    assert version.code_chunking_version(CodeChunkingSettings(), ChunkingSettings()) == FIRST_CODE_VERSION


MODULE_MATERIALS = {
    "RULES_REVISION": 2,
    "HEADER_FORMAT": 2,
    "SEARCH_TEXT_FORMAT": 2,
    "EMBEDDING_INPUT_FORMAT": 2,
    "CONTEXT_OMISSION_REVISION": 2,
    "FALLBACK_REVISION": 2,
    "SUMMARY_SKIP_REVISION": 2,
    "WORST_BYTES_PER_TOKEN": 1.3,
    "KOTLIN_PARSE_COPY_RULE": "suspend-lambda-v2",
    "KOTLIN_ROOT_ANNOTATION_RULE": "root-annotation-v2",
}


@pytest.mark.parametrize(("name", "value"), MODULE_MATERIALS.items())
def test_module_materials(monkeypatch, name, value):
    old = version.code_chunking_version(CodeChunkingSettings(), ChunkingSettings())
    monkeypatch.setattr(version, name, value)
    assert version.code_chunking_version(CodeChunkingSettings(), ChunkingSettings()) != old


@pytest.mark.parametrize(
    ("name", "change"),
    [
        ("PARSER_VERSIONS", lambda v: {**v, "tree-sitter-kotlin": "9.9.9"}),
        ("ANDROID_BASES", lambda v: {**v, "BaseActivity": next(iter(v.values()))}),
        ("COMPONENT_SUFFIXES", lambda v: v[:-1]),
        ("TEST_SOURCE_SETS", lambda v: (*v, "src/e2e/")),
        ("TEST_ANNOTATIONS", lambda v: (*v, "Property")),
        ("KOTLIN_ROOT_NODES", lambda v: v[:-1]),
    ],
)
def test_list_materials(monkeypatch, name, change):
    old = version.code_chunking_version(CodeChunkingSettings(), ChunkingSettings())
    monkeypatch.setattr(version, name, change(getattr(version, name)))
    assert version.code_chunking_version(CodeChunkingSettings(), ChunkingSettings()) != old


@pytest.mark.parametrize("name", ["target_tokens", "limit_tokens", "model_version", "keyword_text_rule"])
def test_setting_materials(monkeypatch, name):
    code, settings = CodeChunkingSettings(), ChunkingSettings()
    old = version.code_chunking_version(code, settings)
    if name == "model_version":
        monkeypatch.setitem(MODELS, "test-model", replace(MODELS[code.model_version], model_version="test-model"))
        code = replace(code, model_version="test-model")
    elif name == "keyword_text_rule":
        settings = replace(settings, keyword_text_rule=INDEX_IDSPLIT)
    else:
        code = replace(code, **{name: getattr(code, name) - 1})
    assert version.code_chunking_version(code, settings) != old


def test_markdown_settings_other_than_keyword_rule_are_not_material():
    code = CodeChunkingSettings()
    assert version.code_chunking_version(code, ChunkingSettings()) == version.code_chunking_version(
        code, ChunkingSettings(limit_tokens=2000)
    )


def test_parser_version_constants_match_installed():
    assert version.PARSER_VERSIONS == {name: importlib.metadata.version(name) for name in version.PARSER_VERSIONS}
    assert set(version.PARSER_VERSIONS) == {"tree-sitter", "tree-sitter-java", "tree-sitter-kotlin"}


def test_version_functions_do_not_load_parser():
    assert run_fresh(fresh.after_versions) == []


def test_index_versions_off_and_on(monkeypatch):
    settings, code = ChunkingSettings(), CodeChunkingSettings()
    assert index_chunking_version(settings) == MD
    assert metadata_schema_version(None) == "meta-v1"
    assert metadata_schema_version(code) == "meta-v2"
    on = index_chunking_version(settings, code)
    assert on == MD + "+" + version.code_chunking_version(code, settings)
    off_id = index_version_id("@cf/baai/bge-m3", 1024, index_chunking_version(settings), metadata_schema_version(None))
    on_id = index_version_id("@cf/baai/bge-m3", 1024, on, metadata_schema_version(code))
    assert off_id == "iv-4c0bc4fcc642"
    assert on_id != off_id
    monkeypatch.setattr(md_version, "RULES_REVISION", 2)
    md_changed = index_version_id("@cf/baai/bge-m3", 1024, index_chunking_version(settings, code), "meta-v2")
    monkeypatch.undo()
    monkeypatch.setattr(version, "RULES_REVISION", 2)
    code_changed = index_version_id("@cf/baai/bge-m3", 1024, index_chunking_version(settings, code), "meta-v2")
    assert len({on_id, md_changed, code_changed}) == 3
