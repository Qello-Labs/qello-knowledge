"""색인 쪽·질의 쪽 키워드 규칙 비교(spec SC-004·SC-005, US5 시나리오 1~6, tasks T040).

규칙마다 별도 `qk_test_*` 데이터베이스에 같은 합성 문서를 넣고, `keyword_query` → `search_keyword_terms`를 직접 부른다.
일치 확장은 새 함수에서 꺼져 있다(research R-03). 측정 조건과 비율은 `-s`로 볼 수 있게 출력한다.
"""

from __future__ import annotations

import io
from collections.abc import Iterator

import psycopg
import pytest

from qello_knowledge.adapters.postgres.migrate import apply_migrations, load_migrations
from qello_knowledge.adapters.postgres.store import PostgresStore
from qello_knowledge.chunking.header import search_text
from qello_knowledge.chunking.version import chunking_version
from qello_knowledge.domain.chunking import ChunkingSettings
from qello_knowledge.domain.keyword_rules import INDEX_BASELINE, INDEX_IDSPLIT, index_rule_for
from qello_knowledge.domain.store import ChunkInput
from qello_knowledge.retrieval import keyword_query
from qello_knowledge.sync.keys import index_version_id
from tests.conftest import _local_db_reachable, local_db_port
from tests.localdb.store.builders import artifact, create_database, database_url_for, drop_database

pytestmark = pytest.mark.localdb

CAMEL = ["retryPayment", "cancelOrder", "getUserProfile", "syncClickUpTasks", "buildEmbeddingInput"]
SNAKE = ["max_retry_count", "access_scope", "chunk_set_hash", "source_modified_at", "local_db_port"]
KEBAB = ["error-codes", "retry-policy", "access-check", "chunk-header", "release-notes"]
PATHS = [
    "/payments/{id}/cancel",
    "/api/v1/orders/{orderId}",
    "/users/me/settings",
    "/teams/{teamId}/members",
    "/health",
]
CAMEL_PARTS = {"retryPayment": "payment", "cancelOrder": "order", "getUserProfile": "profile",
               "syncClickUpTasks": "tasks", "buildEmbeddingInput": "embedding"}  # fmt: skip
SENTENCES = {
    "결제 재시도 횟수는 몇 번이야?": "결제 재시도는 세 번까지 한다.",
    "로컬 개발 환경은 어떻게 띄워?": "로컬 개발 환경을 띄우는 방법을 적었다.",
    "배포는 언제 하지 않아?": "배포는 금요일에 하지 않는다.",
    "권한 확인 규칙을 알려줘": "권한을 확인한 자료만 보여 준다.",
    "청크를 원본으로 되짚을 수 있어?": "청크는 원본 위치로 되짚을 수 있다.",
    "회의록은 어디에 남겨?": "회의록은 공용 문서함에 남긴다.",
    "온보딩 문서가 있나요?": "온보딩 안내 문서를 정리했다.",
    "장애가 나면 누구에게 알려?": "장애가 나면 당번에게 먼저 알린다.",
    "코드 리뷰 승인 기준이 뭐야?": "리뷰 승인 기준은 두 명이다.",
    "릴리스 노트는 누가 써?": "릴리스 노트는 담당자가 쓴다.",
}
FILLER = ["일정과 담당자를 정리했다.", "화면 문구를 다듬었다.", "저장소를 받는 방법을 적었다."] * 10
HEADER = "docs/sample.md\n표본 문서"


def _bodies() -> list[str]:
    return (
        [f"결제 실패 시 `{name}` 함수가 처리한다." for name in CAMEL]
        + [f"설정 키 `{key}` 의 기본값을 적는다." for key in SNAKE]
        + [f"문서 `{name}` 를 참고한다." for name in KEBAB]
        + [f"엔드포인트 `{path}` 는 인증이 필요하다." for path in PATHS]
        + list(SENTENCES.values())
        + FILLER
    )


def _seed(url: str, rule: str) -> str:
    version = chunking_version(ChunkingSettings(keyword_text_rule=rule))
    index_version = index_version_id("@cf/baai/bge-m3", 1024, version)
    with psycopg.connect(url, autocommit=True) as conn:
        assert apply_migrations(conn, load_migrations(), is_local=True, out=io.StringIO()) == 0
        conn.execute(
            "INSERT INTO qk.index_version (id, embedding_model, dimension, chunking_version, metadata_schema_version,"
            " status) VALUES (%s, '@cf/baai/bge-m3', 1024, %s, 'meta-v1', 'active')",
            (index_version, version),
        )
    with PostgresStore(url) as store:
        artifact_id = artifact(store, "sample.md")
        chunks = [
            ChunkInput(
                ordinal=i,
                locator={"path": "docs/sample.md", "lines": [i + 1, i + 1]},
                body=body,
                search_text=search_text(HEADER, body, rule),
                chunking_version=version,
            )
            for i, body in enumerate(_bodies())
        ]
        store.replace_chunks(artifact_id, index_version, "sha-1", chunks)
    return index_version


@pytest.fixture(scope="module")
def stores() -> Iterator[dict[str, PostgresStore]]:
    if not _local_db_reachable(local_db_port()):
        pytest.skip("로컬 DB가 없다")
    names = {rule: create_database() for rule in (INDEX_BASELINE, INDEX_IDSPLIT)}
    opened: dict[str, PostgresStore] = {}
    try:
        for rule, name in names.items():
            url = database_url_for(name)
            _seed(url, rule)
            opened[rule] = PostgresStore(url)
        yield opened
    finally:
        for store in opened.values():
            store.close()
        for name in names.values():
            drop_database(name)


def _top20(store: PostgresStore, question: str, rule: str = "kw-query-v1") -> list[str]:
    return [h.hit.body for h in store.search_keyword_terms(keyword_query(question, rule), 20).hits]


def _share(store: PostgresStore, cases: dict[str, str], rule: str = "kw-query-v1") -> float:
    found = sum(any(needle in body for body in _top20(store, question, rule)) for question, needle in cases.items())
    return found / len(cases)


def test_index_rule_is_known_for_each_database(stores: dict[str, PostgresStore]) -> None:
    for rule, store in stores.items():
        assert index_rule_for(store.search_keyword_terms(("결제",), 1).index_version) == rule


@pytest.mark.parametrize("rule", [INDEX_BASELINE, INDEX_IDSPLIT])
def test_whole_identifiers_found_by_both_rules(stores: dict[str, PostgresStore], rule: str) -> None:
    identifiers = {name: name for name in CAMEL + SNAKE + KEBAB + PATHS}
    assert _share(stores[rule], identifiers) == 1.0


def test_camel_parts_found_by_idsplit(stores: dict[str, PostgresStore], capsys: pytest.CaptureFixture[str]) -> None:
    cases = {part: whole for whole, part in CAMEL_PARTS.items()}
    idsplit = _share(stores[INDEX_IDSPLIT], cases)
    baseline = _share(stores[INDEX_BASELINE], cases)
    print(f"camel parts top20: idsplit={idsplit:.2f} baseline={baseline:.2f} n={len(cases)}")
    assert idsplit == 1.0 and baseline < idsplit


def test_snake_kebab_path_parts_found_by_both(stores: dict[str, PostgresStore]) -> None:
    cases = {"retry": "max_retry_count", "scope": "access_scope", "codes": "error-codes", "payments": "/payments/"}
    for rule in (INDEX_BASELINE, INDEX_IDSPLIT):
        assert _share(stores[rule], cases) == 1.0


def test_sentence_questions(stores: dict[str, PostgresStore], capsys: pytest.CaptureFixture[str]) -> None:
    store = stores[INDEX_BASELINE]
    v1 = _share(store, SENTENCES, "kw-query-v1")
    raw = _share(store, SENTENCES, "kw-query-raw")
    print(f"sentence top20: kw-query-v1={v1:.2f} kw-query-raw={raw:.2f} n={len(SENTENCES)} escalation=off")
    assert v1 >= 0.9


def test_special_characters_in_question(stores: dict[str, PostgresStore]) -> None:
    store = stores[INDEX_BASELINE]
    for question in ['"결제" (재시도) -횟수', "결제 OR 재시도", "a:b +c *d ~e <f>"]:
        store.search_keyword_terms(keyword_query(question, "kw-query-v1"), 20)
        store.search_keyword_terms(keyword_query(question, "kw-query-raw"), 20)
