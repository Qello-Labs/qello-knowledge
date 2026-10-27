"""새 인터프리터에서 가져오기 상태를 확인하는 도우미(QK-CHK-001 research R-15).

`run_fresh`는 `spawn` 방식 프로세스에서 함수를 부르고 결과를 돌려준다. 함수 안에서만 패키지를 가져온다.
"""

import importlib
import multiprocessing
import sys

PARSERS = ("tree_sitter",)


def run_fresh(function):
    with multiprocessing.get_context("spawn").Pool(1) as pool:
        return pool.apply(function)


def loaded(prefixes=PARSERS):
    """`tree_sitter`는 `tree_sitter_java`·`tree_sitter_kotlin`까지 센다."""
    return sorted(m for m in sys.modules if any(m == p or m.startswith((p + ".", p + "_")) for p in prefixes))


def after_versions():
    from qello_knowledge.chunking.code.version import code_chunking_version
    from qello_knowledge.chunking.version import index_chunking_version
    from qello_knowledge.domain.chunking import ChunkingSettings, CodeChunkingSettings
    from qello_knowledge.sync.keys import metadata_schema_version

    code_chunking_version(CodeChunkingSettings(), ChunkingSettings())
    index_chunking_version(ChunkingSettings(), CodeChunkingSettings())
    metadata_schema_version(CodeChunkingSettings())
    return loaded()


def around_first_parse():
    from qello_knowledge.chunking.code import parse

    importlib.import_module("qello_knowledge.chunking")  # 패키지 공개 이름까지 가져와도 해석기는 불러오지 않는다

    before = loaded()
    parse.parse(b"class A {}", "java")
    return before, "tree_sitter" in sys.modules, "tree_sitter_kotlin" in sys.modules


def after_off_chunking():
    from qello_knowledge.chunking import chunk_screened
    from qello_knowledge.domain.chunking import ChunkingSettings
    from tests.unit.chunking.helpers import screened

    body = "class A {\n    void f() {}\n}\n"
    chunk_screened([screened(body, content_format="CODE", location="A.java")], ChunkingSettings())
    return loaded()


def after_query_imports():
    for name in ("qello_knowledge.config.check", "qello_knowledge.query.server", "qello_knowledge.query.app"):
        importlib.import_module(name)
    return loaded(("tree_sitter", "markdown_it", "qello_knowledge.chunking"))
