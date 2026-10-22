"""하이브리드 검색 로컬 DB 시험(spec US1 수용 시나리오 1~5, SC-001, tasks T018). 임베딩은 가짜 제공자다."""

from __future__ import annotations

from fractions import Fraction

import pytest

from qello_knowledge.adapters.postgres.store import PostgresStore
from qello_knowledge.domain.retrieval import RetrievalRequest
from qello_knowledge.domain.store import SearchFilter
from qello_knowledge.embedding.fake import fake_vector
from qello_knowledge.retrieval import RetrievalDeps, retrieve
from tests.localdb.retrieval.builders import seed_doc
from tests.localdb.store.builders import vec
from tests.unit.retrieval.fakes import query_embedder

pytestmark = pytest.mark.localdb

QUESTION = "주문 환불 정책"


def _deps(store: PostgresStore) -> RetrievalDeps:
    embedder, _, _ = query_embedder()
    return RetrievalDeps(store=store, embedder=embedder, new_run_id=lambda: "run")


@pytest.fixture
def corpus(store: PostgresStore) -> dict[str, int]:
    query = list(fake_vector(QUESTION, 1024))
    _, [semantic] = seed_doc(store, "semantic.md", ["돈을 돌려주는 절차를 설명한다"], vector=query)
    _, [lexical] = seed_doc(store, "lexical.md", ["주문 환불 정책 요약"], vector=vec(101))
    _, [both] = seed_doc(store, "both.md", ["환불 정책 상세"], vector=query)
    _, [other] = seed_doc(store, "other.md", ["배포 일정"], vector=vec(202), source_kind="clickup_tasks")
    return {"semantic": semantic, "lexical": lexical, "both": both, "other": other}


def _request(**kwargs) -> RetrievalRequest:
    return RetrievalRequest(QUESTION, want_context=False, **kwargs)


def test_both_top_hits_survive_fusion(store: PostgresStore, corpus: dict[str, int]) -> None:
    result = retrieve(_request(), _deps(store))
    ids = [h.chunk_id for h in result.hits]
    assert corpus["semantic"] in ids and corpus["lexical"] in ids and corpus["both"] in ids
    by_id = {h.chunk_id: h for h in result.hits}
    lexical = by_id[corpus["lexical"]]
    assert lexical.keyword_rank == 1
    expected = Fraction(1, 60 + lexical.keyword_rank) + (
        Fraction(1, 60 + lexical.vector_rank) if lexical.vector_rank else 0
    )
    assert lexical.score == float(expected)


def test_chunk_in_both_appears_once(store: PostgresStore, corpus: dict[str, int]) -> None:
    result = retrieve(_request(), _deps(store))
    ids = [h.chunk_id for h in result.hits]
    assert ids.count(corpus["both"]) == 1
    both = next(h for h in result.hits if h.chunk_id == corpus["both"])
    assert both.vector_rank is not None and both.keyword_rank is not None


def test_order_is_repeatable(store: PostgresStore, corpus: dict[str, int]) -> None:
    first = [h.chunk_id for h in retrieve(_request(), _deps(store)).hits]
    assert first == [h.chunk_id for h in retrieve(_request(), _deps(store)).hits]


def test_source_filter_applies_to_both(store: PostgresStore, corpus: dict[str, int]) -> None:
    result = retrieve(_request(filters=SearchFilter(source_kinds=("github",))), _deps(store))
    assert corpus["other"] not in [h.chunk_id for h in result.hits]


def test_hit_has_provenance(store: PostgresStore, corpus: dict[str, int]) -> None:
    top = retrieve(_request(), _deps(store)).hits[0]
    assert top.provenance.source_url.startswith("https://example.invalid/") and top.provenance.collected_at
    assert top.rank == 1 and top.score > 0
