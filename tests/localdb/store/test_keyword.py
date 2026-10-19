"""US2: 한국어 단어와 코드 식별자를 원형 그대로 찾는다(SC-007, FR-007·010)."""

from __future__ import annotations

import pytest

from qello_knowledge.adapters.postgres.store import PostgresStore
from tests.localdb.store.builders import document

pytestmark = pytest.mark.localdb

FUNCTIONS = ["retryPayment", "cancelOrder", "getUserProfile", "syncClickUpTasks", "buildEmbeddingInput"]
PATHS = [
    "/payments/{id}/cancel",
    "/api/v1/orders/{orderId}",
    "/users/me/settings",
    "/teams/{teamId}/members",
    "/health",
]
SNAKE = ["max_retry_count", "access_scope", "chunk_set_hash", "source_modified_at", "qk_local_db_port"]
KOREAN = ["재시도", "개발", "배포", "권한", "청크"]

FILLER = [
    "회의록: 다음 주 일정과 담당자를 정리했다.",
    "릴리스 노트: 화면 문구를 다듬었다.",
    "온보딩 안내: 저장소를 받는 방법을 적었다.",
] * 10


@pytest.fixture
def corpus(store: PostgresStore) -> None:
    bodies = (
        [f"결제 실패 시 `{name}` 함수가 처리한다." for name in FUNCTIONS]
        + [f"엔드포인트 `{path}` 는 인증이 필요하다." for path in PATHS]
        + [f"설정 키 `{key}` 의 기본값을 적는다." for key in SNAKE]
        + ["결제 재시도는 세 번까지 한다.", "로컬 개발 환경을 띄운다.", "배포는 금요일에 하지 않는다."]
        + ["권한을 확인한 자료만 보여 준다.", "청크는 원본 위치로 되짚을 수 있다."]
    )
    document(store, "target.md", bodies)
    document(store, "filler.md", FILLER)


def _top20(store: PostgresStore, term: str) -> list[str]:
    return [hit.body for hit in store.search_keyword(term, 20).hits]


@pytest.mark.parametrize("term", FUNCTIONS + PATHS + SNAKE)
def test_identifier_found_in_top20(store: PostgresStore, corpus: None, term: str) -> None:
    assert any(term in body for body in _top20(store, term))


@pytest.mark.parametrize("term", KOREAN)
def test_korean_word_found(store: PostgresStore, corpus: None, term: str) -> None:
    assert any(term in body for body in _top20(store, term))


def test_identifier_is_case_insensitive(store: PostgresStore, corpus: None) -> None:
    assert any("retryPayment" in body for body in _top20(store, "retrypayment"))


@pytest.mark.parametrize("term", ['(a OR "b', "a) OR (b", "-개발", "x:y", "\\", '"'])
def test_query_syntax_characters_are_literal(store: PostgresStore, corpus: None, term: str) -> None:
    result = store.search_keyword(term, 20)
    assert result.status == "ok"
    assert all(term in hit.body for hit in result.hits)


@pytest.mark.parametrize("term", ["", "   ", "\t\n"])
def test_blank_query_returns_empty(store: PostgresStore, corpus: None, term: str) -> None:
    result = store.search_keyword(term, 20)
    assert result.hits == ()


def test_keyword_score_prefers_more_matches(store: PostgresStore) -> None:
    document(store, "many.md", ["배포 배포 배포 절차"])
    document(store, "once.md", ["배포 일정과 회의 안건과 담당자 정리"])
    hits = store.search_keyword("배포", 20).hits
    assert hits[0].body == "배포 배포 배포 절차"
    assert hits[0].score > hits[1].score > 0
