"""`qk.search_keyword_terms`(research R-03 결정 2, data-model 4.1, tasks T008)."""

from __future__ import annotations

import pytest

from qello_knowledge.adapters.postgres.store import PostgresStore
from qello_knowledge.domain.store import SearchFilter
from tests.localdb.retrieval.builders import seed_doc, set_status
from tests.localdb.store.builders import ARCHIVED

pytestmark = pytest.mark.localdb

TERMS = ("결제", "취소", "API", "경로")


def _bodies(store: PostgresStore, terms, top_n: int = 20, **kwargs) -> list[str]:
    return [h.hit.body for h in store.search_keyword_terms(terms, top_n, **kwargs).hits]


def test_distinct_matched_terms_beat_occurrence_count(store: PostgresStore) -> None:
    seed_doc(store, "a.md", ["결제 결제 결제 결제 결제 결제", "결제 취소 API 경로", "취소 경로"])
    result = store.search_keyword_terms(TERMS, 20)
    assert [h.hit.body for h in result.hits] == ["결제 취소 API 경로", "취소 경로", "결제 결제 결제 결제 결제 결제"]
    assert [h.matched_terms for h in result.hits] == [4, 2, 1]
    assert [h.hit.rank for h in result.hits] == [1, 2, 3]
    assert result.status == "ok" and result.index_version == "v1"


def test_same_matched_count_orders_by_score_then_id(store: PostgresStore) -> None:
    seed_doc(store, "a.md", ["결제 이야기", "결제 결제 결제", "결제 하나"])
    hits = store.search_keyword_terms(("결제",), 20).hits
    assert hits[0].hit.body == "결제 결제 결제"
    assert hits[0].hit.score > hits[1].hit.score
    # 점수가 같은 두 청크는 청크 식별자 순
    tied = [h for h in hits if h.hit.score == hits[1].hit.score]
    assert [h.hit.chunk_id for h in tied] == sorted(h.hit.chunk_id for h in tied)


def test_rows_missing_from_score_query_get_zero(store: PostgresStore) -> None:
    seed_doc(store, "a.md", ["커피 차", "결제 하나"])
    hits = store.search_keyword_terms(("커피", "결제"), 20).hits
    assert all(h.hit.score >= 0 for h in hits)
    assert len(hits) == 2


def test_match_escalation_is_off(store: PostgresStore) -> None:
    seed_doc(store, "a.md", ["retryPayment 함수", "다른 문장"])
    assert _bodies(store, ("retry",)) == []
    seed_doc(store, "b.md", ["retry 설명"])
    assert _bodies(store, ("retry",)) == ["retry 설명"]
    assert _bodies(store, ("retryPayment",)) == ["retryPayment 함수"]


def test_special_characters_are_literal(store: PostgresStore) -> None:
    seed_doc(store, "a.md", ["OR 조건 설명", "괄호 (없음 이야기", "커피 or 차"])
    assert sorted(_bodies(store, ("or",))) == ["OR 조건 설명", "커피 or 차"]
    for term in ('"x"', "(없음", "-z", "a:b", "+c", "*", "~d", "<e>"):
        store.search_keyword_terms((term,), 20)  # 문법 오류가 없어야 한다
    assert _bodies(store, ("(없음",)) == ["괄호 (없음 이야기"]


def test_hidden_chunks_are_excluded(store: PostgresStore, db_url: str) -> None:
    seed_doc(store, "team.md", ["결제 공개"])
    seed_doc(store, "unknown.md", ["결제 미확인"], access_scope=None)
    seed_doc(store, "limited.md", ["결제 제한"], access_scope="restricted")
    seed_doc(store, "deleted.md", ["결제 삭제"])
    store.mark_deleted("github", "deleted.md")
    seed_doc(store, "archived.md", ["결제 보관"])
    set_status(db_url, "archived.md", "archived")
    seed_doc(store, "old.md", ["결제 옛 버전"], index_version=ARCHIVED)
    assert _bodies(store, ("결제",)) == ["결제 공개"]


def test_filters_apply(store: PostgresStore) -> None:
    seed_doc(store, "a.md", ["결제 문서"])
    seed_doc(store, "b.md", ["결제 작업"], source_kind="clickup_tasks")
    assert _bodies(store, ("결제",), filters=SearchFilter(source_kinds=("clickup_tasks",))) == ["결제 작업"]


def test_empty_terms_report_active_version(store: PostgresStore) -> None:
    seed_doc(store, "a.md", ["결제"])
    result = store.search_keyword_terms((), 20)
    assert (result.status, result.index_version, result.hits) == ("ok", "v1", ())


def test_no_active_version(store: PostgresStore, db_url: str) -> None:
    import psycopg

    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute("UPDATE qk.index_version SET status = 'ready' WHERE status = 'active'")
    assert store.search_keyword_terms(("결제",), 20).status == "no_active_index"
    assert store.search_keyword_terms((), 20).status == "no_active_index"


FRUITS = (
    "사과", "바나나", "포도", "딸기", "수박", "참외", "자두", "복숭아", "레몬",
    "키위", "망고", "체리", "앵두", "살구", "석류", "대추", "감귤",
)  # fmt: skip


def test_limits(store: PostgresStore) -> None:
    seed_doc(store, "a.md", list(FRUITS))
    hits = store.search_keyword_terms(FRUITS, 20).hits
    assert len(hits) == 16 and all(h.hit.body != "감귤" for h in hits)  # 앞 16개 낱말만 쓴다
    assert len(store.search_keyword_terms(FRUITS[:16], 99).hits) == 16
    assert len(store.search_keyword_terms(FRUITS[:3], 0).hits) == 1  # top_n은 1~50으로 자른다


def test_repeatable(store: PostgresStore) -> None:
    seed_doc(store, "a.md", ["결제 취소", "취소 결제", "결제", "취소"])
    first = [h.hit.chunk_id for h in store.search_keyword_terms(TERMS, 20).hits]
    assert first == [h.hit.chunk_id for h in store.search_keyword_terms(TERMS, 20).hits]


def test_repeated_calls_keep_escalation_off(store: PostgresStore) -> None:
    """plpgsql 일반 계획으로 바뀐 뒤에도 일치 확장이 꺼져 있어야 한다(0005 `plan_cache_mode`, 구현 중 발견)."""
    seed_doc(store, "a.md", ["결제 실패 시 `retryPayment` 함수", "다른 문장"])
    results = [[h.hit.chunk_id for h in store.search_keyword_terms(("payment",), 20).hits] for _ in range(12)]
    assert results == [[]] * 12
