"""노출 차단(spec US2 수용 시나리오 1~4, SC-002, tasks T022·T030). 임베딩은 가짜 제공자다."""

from __future__ import annotations

import pytest

from qello_knowledge.adapters.postgres.store import PostgresStore
from qello_knowledge.domain.retrieval import RetrievalRequest
from qello_knowledge.embedding.fake import fake_vector
from qello_knowledge.retrieval import RetrievalDeps, retrieve
from tests.localdb.retrieval.builders import seed_doc, set_status
from tests.localdb.store.builders import ARCHIVED
from tests.unit.retrieval.fakes import query_embedder

pytestmark = pytest.mark.localdb

QUESTION = "배포 승인 절차"


def _deps(store: PostgresStore) -> RetrievalDeps:
    embedder, _, _ = query_embedder()
    return RetrievalDeps(store=store, embedder=embedder, new_run_id=lambda: "run")


def _all_chunk_ids(result) -> set[int]:
    ids = {h.chunk_id for h in result.hits}
    ids |= {c.chunk_id for block in result.context for c in block.chunks}
    return ids


@pytest.fixture
def query() -> list[float]:
    return list(fake_vector(QUESTION, 1024))


def test_hidden_chunks_never_appear_in_results(store: PostgresStore, db_url: str, query: list[float]) -> None:
    _, visible = seed_doc(store, "visible.md", ["배포 승인 절차 공개 문서"], vector=query)
    hidden: list[int] = []
    hidden += seed_doc(store, "unknown.md", ["배포 승인 절차 미확인"], vector=query, access_scope=None)[1]
    hidden += seed_doc(store, "limited.md", ["배포 승인 절차 제한"], vector=query, access_scope="restricted")[1]
    hidden += seed_doc(store, "deleted.md", ["배포 승인 절차 내림"], vector=query)[1]
    store.mark_deleted("github", "deleted.md")
    hidden += seed_doc(store, "archived.md", ["배포 승인 절차 보관"], vector=query)[1]
    set_status(db_url, "archived.md", "archived")
    hidden += seed_doc(store, "old.md", ["배포 승인 절차 옛 버전"], vector=query, index_version=ARCHIVED)[1]
    result = retrieve(RetrievalRequest(QUESTION), _deps(store))
    seen = _all_chunk_ids(result)
    assert visible[0] in seen
    assert seen.isdisjoint(hidden)


def test_nearest_unknown_scope_chunk_is_absent(store: PostgresStore, query: list[float]) -> None:
    _, [unknown] = seed_doc(store, "unknown.md", ["배포 승인 절차"], vector=query, access_scope=None)
    _, [far] = seed_doc(store, "far.md", ["다른 이야기"], vector=list(fake_vector("무관", 1024)))
    result = retrieve(RetrievalRequest(QUESTION), _deps(store))
    assert unknown not in _all_chunk_ids(result)
    assert far in {h.chunk_id for h in result.hits}
