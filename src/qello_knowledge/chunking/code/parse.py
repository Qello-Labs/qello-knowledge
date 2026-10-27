"""tree-sitter 호출 경계(research R-01·R-15). 해석기는 함수 안에서 처음 해석할 때만 불러온다.

해석기를 불러오다 실패하면 예외를 그대로 올린다. 호출자가 그 파일만 처리 오류로 돌린다.
"""

import importlib

from qello_knowledge.chunking.code.version import KOTLIN_PARSE_COPY, KOTLIN_PARSE_COPY_WITH

GRAMMARS = {"java": "tree_sitter_java", "kotlin": "tree_sitter_kotlin"}
_PARSERS: dict = {}
_import = importlib.import_module  # 시험이 적재 실패를 흉내 낼 때 바꾼다


def _parser(language):
    if language not in _PARSERS:
        tree_sitter = _import("tree_sitter")
        grammar = _import(GRAMMARS[language])
        _PARSERS[language] = tree_sitter.Parser(tree_sitter.Language(grammar.language()))
    return _PARSERS[language]


def parse_copy(source: bytes) -> bytes:
    """같은 길이 해석용 사본. 바이트·줄 위치가 그대로라 노드 위치를 원문에 쓴다."""
    return KOTLIN_PARSE_COPY.sub(KOTLIN_PARSE_COPY_WITH, source)


def blanked(source: bytes, spans) -> bytes:
    """`spans`(시작·끝 바이트) 부분을 같은 길이 공백으로 바꾼 사본. 줄 바꿈은 남겨 줄·바이트 위치가 그대로다."""
    data = bytearray(source)
    for span in spans:
        for index in range(span.start_byte, span.end_byte):
            if data[index] != 0x0A:
                data[index] = 0x20
    return bytes(data)


def parse(source: bytes, language: str):
    return _parser(language).parse(parse_copy(source) if language == "kotlin" else source)


def has_error(tree) -> bool:
    return tree.root_node.has_error


def first_error_line(tree) -> int:
    """첫 오류 노드(또는 빠진 노드)의 1부터 센 줄 번호."""
    stack = [tree.root_node]
    while stack:
        node = stack.pop()
        if node.is_error or node.is_missing:
            return node.start_point[0] + 1
        stack.extend(reversed([c for c in node.children if c.has_error or c.is_missing]))
    return 1
