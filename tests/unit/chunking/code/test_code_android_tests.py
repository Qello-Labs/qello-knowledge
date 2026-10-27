"""Android 컴포넌트·테스트 판정(QK-CHK-001 spec SC-007, FR-024·025, US4, tasks T034).

T033 픽스처의 전체 비교는 `test_code_expected.py`가 한다. 여기서는 판정 값만 모아 본다.
"""

import pytest

from tests.unit.chunking.code.helpers import FIXTURES, cases, run

CASES = {name: (body, case) for name, body, case in cases()}


def chunks(name):
    body, case = CASES[name]
    return [d for d in run(body, case).drafts]


def kinds(name):
    return {(tuple(d.chunk.heading_path), d.chunk.locator["code"]["chunk_kind"]): d for d in chunks(name)}


@pytest.mark.parametrize(
    ("name", "component"),
    [
        ("android_viewmodel", "VIEW_MODEL"),
        ("android_base_fragment", "FRAGMENT"),
        ("spring_service_impl", ""),
        ("spring_activity_named", ""),
    ],
)
def test_type_component_reaches_member_chunks(name, component):
    typed = [d for d in chunks(name) if d.chunk.heading_path]
    assert typed and {d.chunk.locator["code"]["component"] for d in typed} == {component}


def test_composable_function():
    function = kinds("android_composable")[(("LoginScreen.kt", "LoginScreen(()->Unit)"), "TOP_FUNCTION")]
    assert function.chunk.locator["code"]["component"] == "COMPOSABLE"


@pytest.mark.parametrize(
    ("name", "test_code", "test_methods"),
    [
        ("test_display_name", True, 3),
        ("test_integration", True, 1),
        ("test_android", True, 1),
        ("test_fixtures", True, 0),
        ("test_helper_no_annotation", True, 0),
        ("abtest_main", False, 0),
        ("kotlin_test_backtick", True, 1),
    ],
)
def test_test_code_and_test_methods(name, test_code, test_methods):
    drafts = chunks(name)
    assert {d.chunk.locator["code"]["test_code"] for d in drafts} == {test_code}
    assert sum(d.chunk.locator["code"]["test_method"] for d in drafts) == test_methods


def test_display_names_reach_search_header():
    display = kinds("test_display_name")[(("OrderServiceTest", "rejectsWhenOutOfStock()"), "METHOD")]
    assert display.chunk.locator["code"]["display_name"] == "재고가 없으면 주문을 거절한다"
    assert display.search_header.endswith("[METHOD] 재고가 없으면 주문을 거절한다")
    nested = kinds("test_display_name")[(("OrderServiceTest", "Cancel", "cancelsOrder()"), "METHOD")]
    assert nested.chunk.locator["code"]["test_method"] and nested.chunk.locator["code"]["display_name"] == ""
    backtick = [d for d in chunks("kotlin_test_backtick") if d.chunk.locator["code"]["test_method"]][0]
    assert backtick.search_header.endswith("[METHOD] 로그인에 실패하면 오류를 보여 준다")


def test_android_kinds_need_android_import():
    body = (FIXTURES / "android_base_fragment.kt").read_text(encoding="utf-8")
    without = body.replace("import androidx.fragment.app.viewModels\n", "")
    case = {"input": {"location": "presentation/src/main/java/com/acme/home/HomeFragment.kt"}}
    assert {d.chunk.locator["code"]["component"] for d in run(without, case).drafts} == {""}
