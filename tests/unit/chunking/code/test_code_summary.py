"""요약 청크 불변식과 국소성(QK-CHK-001 spec SC-002·SC-003, FR-012~015, US1-5, tasks T021)."""

import pytest

from qello_knowledge.chunking.code import parse, symbols
from qello_knowledge.domain.chunking import ChunkOutcomeKind
from tests.unit.chunking.code.helpers import FIXTURES, cases, run

CASES = [c for c in cases() if any(ch["code"]["summary"] for ch in c[2]["expected"].get("chunks", []))]
METHOD_NODES = {
    "method_declaration",
    "constructor_declaration",
    "compact_constructor_declaration",
    "static_initializer",
    "function_declaration",
    "secondary_constructor",
    "anonymous_initializer",
}


def body_rows(source, location):
    """메서드·생성자·초기화 블록에서 본문을 여는 줄 뒤의 줄 번호(1부터)."""
    language = "java" if location.endswith(".java") else "kotlin"
    tree = parse.parse(source.encode(), language)
    rows, stack = set(), [tree.root_node]
    while stack:
        node = stack.pop()
        stack.extend(node.children)
        if node.type in METHOD_NODES or (node.type == "block" and node.parent.type == "class_body"):
            rows.update(range(symbols.signature_end(node) + 2, node.end_point[0] + 2))
    return rows


def matched_rows(body, lines, start, end):
    """요약 본문 줄을 범위 안 원문 줄에 순서대로 대응시킨다. 대응이 없으면 실패한다."""
    rows, cursor = [], start
    for line in body.split("\n"):
        while cursor <= end and lines[cursor - 1] != line:
            cursor += 1
        assert cursor <= end, line
        rows.append(cursor)
        cursor += 1
    return rows


def test_there_are_summary_cases():
    assert len(CASES) >= 10


@pytest.mark.parametrize(("name", "body", "case"), CASES, ids=[c[0] for c in CASES])
def test_summary_lines_are_signature_lines_in_range(name, body, case):
    result = run(body, case)
    assert result.outcome == ChunkOutcomeKind.CHUNKED
    lines = body.split("\n")
    forbidden = body_rows(body, case["input"]["location"])
    drafts = result.drafts
    for i, draft in enumerate(drafts):
        code = draft.chunk.locator["code"]
        if not code["summary"]:
            continue
        start, end = draft.chunk.locator["lines"]
        rows = matched_rows(draft.chunk.body, lines, start, end)
        assert not set(rows) & forbidden, (name, rows)
        later = [d for d in drafts[i + 1 :] if not d.chunk.locator["code"]["summary"]]
        if code["chunk_kind"] == "TYPE_SUMMARY":
            # 요약은 그 형식의 첫 원문 청크 바로 앞에 온다
            assert later[0].chunk.heading_path == draft.chunk.heading_path
            assert later[0].chunk.locator["code"]["chunk_kind"] == "TYPE_HEAD"
            assert later[0].chunk.locator["lines"][0] == start
        else:
            before = [d.chunk.locator["code"]["chunk_kind"] for d in drafts[:i]]
            assert before in ([], ["FILE_HEAD"])


THREE = (FIXTURES / "java_three_methods.java").read_text(encoding="utf-8")
CASE = {"input": {"location": "src/main/java/com/acme/order/OrderService.java"}}


def summary_of(body):
    return next(d.embedding_text for d in run(body, CASE).drafts if d.chunk.locator["code"]["summary"])


def test_body_change_keeps_summary():
    assert summary_of(THREE.replace("int offset = page * size;", "int offset = 0;")) == summary_of(THREE)


def test_parameter_change_changes_summary():
    assert summary_of(THREE.replace("list(int page, int size)", "list(long page, int size)")) != summary_of(THREE)


def test_member_doc_comment_is_not_in_summary():
    assert summary_of(THREE.replace("/** 주문 목록 */", "/** 바뀐 설명 */")) == summary_of(THREE)
