"""US2: 권한·상태·버전 조건은 질의 안에서 적용된다(SC-002, FR-006·008·009)."""

from __future__ import annotations

import pytest

from qello_knowledge.adapters.postgres.store import PostgresStore
from qello_knowledge.domain.store import SearchFilter
from tests.localdb.store.builders import ARCHIVED, COLLECTED_AT, document, vec

pytestmark = pytest.mark.localdb

QUERY = vec(42)
WORD = "결제재시도정책"


@pytest.fixture
def mixed(store: PostgresStore) -> dict[str, int]:
    """질의와 똑같이 가까운 청크를 허용·금지 조건별로 섞는다. 금지 청크가 더 가깝게 만든다."""
    ids = {
        "team": document(store, "team.md", [f"{WORD} 팀 공용 문서"], vector=QUERY),
        "repo_doc": document(
            store, "repo.md", [f"{WORD} 저장소 문서"], vector=QUERY, source_kind="clickup", artifact_kind="doc"
        ),
        "unconfirmed": document(store, "unknown.md", [f"{WORD} 미확인"] * 3, vector=QUERY, access_scope=None),
        "restricted": document(store, "secret.md", [f"{WORD} 제한"] * 3, vector=QUERY, access_scope="restricted"),
        "deleted": document(store, "deleted.md", [f"{WORD} 삭제"] * 3, vector=QUERY),
        "archived_only": document(store, "old.md", [f"{WORD} 구버전"] * 3, vector=QUERY, index_version=ARCHIVED),
    }
    store.mark_deleted("github", "deleted.md")
    return ids


def _sources(result) -> set[str]:
    return {hit.provenance.source_url.rsplit("/", 1)[-1] for hit in result.hits}


def test_vector_search_returns_only_visible_chunks(store: PostgresStore, mixed: dict[str, int]) -> None:
    result = store.search_vector(QUERY, 20)
    assert result.status == "ok"
    assert _sources(result) == {"team.md", "repo.md"}


def test_keyword_search_returns_only_visible_chunks(store: PostgresStore, mixed: dict[str, int]) -> None:
    result = store.search_keyword(WORD, 20)
    assert result.status == "ok"
    assert _sources(result) == {"team.md", "repo.md"}


def test_filters_by_source_kind_and_artifact_kind(store: PostgresStore, mixed: dict[str, int]) -> None:
    only_clickup = SearchFilter(source_kinds=("clickup",))
    assert _sources(store.search_vector(QUERY, 20, only_clickup)) == {"repo.md"}
    assert _sources(store.search_keyword(WORD, 20, only_clickup)) == {"repo.md"}
    assert _sources(store.search_keyword(WORD, 20, SearchFilter(artifact_kinds=("markdown",)))) == {"team.md"}


def test_each_hit_has_rank_score_id_and_provenance(store: PostgresStore, mixed: dict[str, int]) -> None:
    for result in (store.search_vector(QUERY, 20), store.search_keyword(WORD, 20)):
        assert [hit.rank for hit in result.hits] == list(range(1, len(result.hits) + 1))
        scores = [hit.score for hit in result.hits]
        assert scores == sorted(scores, reverse=True)
        for hit in result.hits:
            assert hit.chunk_id > 0
            assert hit.body
            assert hit.provenance.source_version == "sha-1"
            assert hit.provenance.locator["path"] == "docs/sample.md"
            assert hit.provenance.collected_at == COLLECTED_AT


def test_vector_score_orders_by_closeness(store: PostgresStore) -> None:
    document(store, "close.md", ["가까운 문서"], vector=QUERY)
    document(store, "far.md", ["먼 문서"], vector=vec(7))
    result = store.search_vector(QUERY, 20)
    assert [hit.body for hit in result.hits] == ["가까운 문서", "먼 문서"]
    assert result.hits[0].score > 0.9
