import pytest

from qello_knowledge.chunking.blocks import parse_document


def parse(text):
    return parse_document(text.split("\n"))


def test_refdef_and_front_matter():
    parsed = parse('---\ntitle: "Synthetic"\n---\n\n[x]: /example\n\n# A')
    assert parsed.front_matter_title == "Synthetic"
    assert [(b.kind, b.start, b.end) for b in parsed.blocks] == [
        ("front_matter", 0, 3),
        ("raw", 4, 5),
        ("heading", 6, 7),
    ]


@pytest.mark.parametrize(
    "text",
    ["```py\n# comment\n```", "~~~\n# comment\n~~~", "    # code", "> # quoted", "- # item", "<div>\n# html\n</div>"],
)
def test_nested_headings_are_not_sections(text):
    assert not any(b.kind == "heading" for b in parse(text).blocks)


def test_nested_tree():
    block = parse("- outer\n  - inner").blocks[0]
    assert block.kind == "list"
    item = block.children[0]
    assert item.kind == "list_item"
    nested = item.children[1]
    assert nested.kind == "list" and nested.children[0].kind == "list_item"
    assert nested.children[0].start == 1


@pytest.mark.parametrize(
    "text,title",
    [
        ("first\nsecond\n---", "first second"),
        ("## **중요** [링크](x) `code`", "중요 링크 code"),
        ("# ![대체](image.png)  text", "대체 text"),
    ],
)
def test_heading_text_and_last_line(text, title):
    b = parse(text).blocks[0]
    assert b.text == title and b.end == len(text.split("\n"))


def test_nested_table_metadata():
    from tests.unit.chunking.helpers import FIXTURES

    parsed = parse((FIXTURES / "nested_tables_valid.md").read_text())
    assert [(t.start, t.end, t.container_depth) for t in parsed.tables] == [
        (1, 4, 1),
        (5, 8, 0),
        (9, 12, 0),
        (13, 16, 2),
    ]
