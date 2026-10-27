"""해석 경계: 같은 길이 해석용 사본, 오류 판정, 지연 가져오기(QK-CHK-001 research R-01, tasks T008)."""

import pytest

from qello_knowledge.chunking.code import parse
from tests.unit.chunking.code import fresh
from tests.unit.chunking.code.fresh import run_fresh


@pytest.mark.parametrize(
    ("source", "changed"),
    [
        (b"val x = suspend { 1 }", True),
        (b"suspend{ 1 }", True),
        (b"suspend\n    {\n}", True),
        (b"suspend fun load() {}", False),
        (b"val f: suspend () -> Unit", False),
        (b"_suspend { 1 }", False),
        (b"xsuspend { 1 }", False),
    ],
)
def test_parse_copy_keeps_length(source, changed):
    copy = parse.parse_copy(source)
    assert len(copy) == len(source)
    assert (copy != source) is changed
    if changed:
        assert b"run    " in copy


VIEW_MODEL = """package a

class LoginViewModel : ViewModel() {
    fun load() {
        val job = suspend { fetch() }
        suspend {
            fetch()
        }
    }
}
"""


def test_suspend_lambda_view_model_parses():
    assert parse.has_error(parse.parse(VIEW_MODEL.encode(), "kotlin")) is False


@pytest.mark.parametrize(
    ("language", "source"),
    [
        ("java", "class A {\n    void f() {\n        if (x) {\n    }\n"),
        ("kotlin", "class A {\n    fun f() {\n        if (x) {\n    }\n"),
    ],
)
def test_unbalanced_is_error(language, source):
    tree = parse.parse(source.encode(), language)
    assert parse.has_error(tree) is True
    assert parse.first_error_line(tree) >= 1


def test_parser_is_loaded_lazily():
    before, java, kotlin = run_fresh(fresh.around_first_parse)
    assert (before, java, kotlin) == ([], True, False)


def test_loader_failure_reaches_caller(monkeypatch):
    def broken(name):
        raise ImportError("synthetic")

    monkeypatch.setattr(parse, "_PARSERS", {})
    monkeypatch.setattr(parse, "_import", broken)
    with pytest.raises(ImportError):
        parse.parse(b"class A {}", "java")
    assert parse._PARSERS == {}
