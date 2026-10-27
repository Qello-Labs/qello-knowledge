"""고친 곳만 청크가 바뀐다(QK-CHK-001 spec SC-003, FR-011, US1-4·6, tasks T015). 요약 쪽 단언은 T021."""

from tests.unit.chunking.code.helpers import FIXTURES, run

THREE = (FIXTURES / "java_three_methods.java").read_text(encoding="utf-8")
CONTROLLER = (FIXTURES / "java_controller.java").read_text(encoding="utf-8")
CASE = {"input": {"location": "src/main/java/com/acme/order/OrderService.java"}}
CONTROLLER_CASE = {"input": {"location": "src/main/java/com/acme/web/OrderController.java"}}


def source_texts(body, case=CASE):
    return {
        d.chunk.ordinal: (d.chunk.body, d.chunk.heading_path, d.embedding_text)
        for d in run(body, case).drafts
        if not d.chunk.locator["code"]["summary"]
    }


def changed(before, after):
    return sorted(k for k in before if before[k] != after[k])


def ordinal_of(body, symbol, case=CASE):
    return next(d.chunk.ordinal for d in run(body, case).drafts if d.chunk.heading_path[-1:] == (symbol,))


def test_body_line_change_touches_only_that_method():
    edited = THREE.replace("int offset = page * size;", "int offset = (page - 1) * size;")
    assert changed(source_texts(THREE), source_texts(edited)) == [ordinal_of(THREE, "list(int,int)")]


def test_parameter_change_touches_only_that_source_chunk():
    edited = THREE.replace("list(int page, int size)", "list(long page, int size)")
    assert changed(source_texts(THREE), source_texts(edited)) == [ordinal_of(THREE, "list(int,int)")]


def test_member_doc_comment_change_touches_only_that_member():
    edited = THREE.replace("/** 주문 목록 */", "/** 주문 목록을 쪽 단위로 돌려준다 */")
    before = {d.chunk.ordinal: d.embedding_text for d in run(THREE, CASE).drafts}
    after = {d.chunk.ordinal: d.embedding_text for d in run(edited, CASE).drafts}
    assert changed(before, after) == [ordinal_of(THREE, "list(int,int)")]


def test_class_annotation_change_touches_every_chunk_of_the_class():
    edited = CONTROLLER.replace('@RequestMapping("/orders")', '@RequestMapping("/v2/orders")')
    before = {d.chunk.ordinal: d.embedding_text for d in run(CONTROLLER, CONTROLLER_CASE).drafts}
    after = {d.chunk.ordinal: d.embedding_text for d in run(edited, CONTROLLER_CASE).drafts}
    assert changed(before, after) == [1, 2, 3]  # 파일 머리만 그대로다
    method = run(edited, CONTROLLER_CASE).drafts[3]
    assert '@RequestMapping("/v2/orders")' in method.embedding_text
    assert '@RequestMapping("/v2/orders")' in method.chunk.search_text
    assert "@RequestMapping" not in method.chunk.body


def test_location_change_touches_every_header():
    moved = {"input": {"location": "src/main/java/com/acme/order/v2/OrderService.java"}}
    before, after = run(THREE, CASE).drafts, run(THREE, moved).drafts
    assert len(before) == len(after)
    assert all(a.search_header != b.search_header for a, b in zip(before, after, strict=True))
    assert [a.chunk.body for a in before] == [b.chunk.body for b in after]
