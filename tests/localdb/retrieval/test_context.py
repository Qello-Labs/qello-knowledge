"""문맥 확장 로컬 DB 시험(spec US3 수용 시나리오 1~5, tasks T027). 임베딩은 가짜 제공자다."""

from __future__ import annotations

import pytest

from qello_knowledge.adapters.postgres.store import PostgresStore
from qello_knowledge.domain.retrieval import ChunkRole, RetrievalMode, RetrievalRequest
from qello_knowledge.retrieval import RetrievalDeps, retrieve
from tests.localdb.retrieval.builders import seed_doc
from tests.unit.retrieval.fakes import query_embedder

pytestmark = pytest.mark.localdb

A = ("문서",)
B = ("문서", "설치")
C = ("문서", "설정")


def _keyword(store: PostgresStore, question: str, **overrides):
    embedder, _, _ = query_embedder()
    request = RetrievalRequest(question, mode=RetrievalMode.KEYWORD, overrides=overrides)
    return retrieve(request, RetrievalDeps(store=store, embedder=embedder))


def test_neighbors_and_section_first_in_original_order(store: PostgresStore) -> None:
    _, ids = seed_doc(
        store,
        "a.md",
        [("머리말", A), ("설치 준비", B), ("설치 중간", B), ("설치 목표어", B), ("설치 끝", B), ("설정", C)],
    )
    result = _keyword(store, "목표어")
    [block] = result.context
    assert [c.chunk_id for c in block.chunks] == [ids[1], ids[2], ids[3], ids[4]]
    roles = {c.chunk_id: c.role for c in block.chunks}
    assert roles[ids[1]] is ChunkRole.SECTION_FIRST and roles[ids[3]] is ChunkRole.CENTER
    assert block.gaps == ()


def test_first_and_last_chunks(store: PostgresStore) -> None:
    _, ids = seed_doc(store, "a.md", ["처음 목표어", "중간", "끝 다른표지"])
    first = _keyword(store, "목표어").context[0]
    last = _keyword(store, "다른표지").context[0]
    assert [c.chunk_id for c in first.chunks] == [ids[0], ids[1]]
    # 제목 경로가 모두 같아 절은 자료의 첫 청크부터다. 앞 1개 + 절 첫 청크가 붙고 뒤는 없다.
    assert [c.chunk_id for c in last.chunks] == [ids[0], ids[1], ids[2]]
    assert last.chunks[0].role is ChunkRole.SECTION_FIRST


def test_repeated_heading_path_uses_current_section_only(store: PostgresStore) -> None:
    _, ids = seed_doc(
        store, "a.md", [("앞 설치", B), ("앞 설치2", B), ("설정", C), ("뒤 설치", B), ("뒤 설치 목표어", B)]
    )
    block = _keyword(store, "목표어", before=0, after=0).context[0]
    assert [c.chunk_id for c in block.chunks] == [ids[3], ids[4]]


def test_block_fields(store: PostgresStore) -> None:
    _, ids = seed_doc(store, "a.md", ["목표어 하나", "둘"])
    result = _keyword(store, "목표어")
    block = result.context[0]
    assert block.source_id == "S1" and block.rank == 1
    assert block.source_url.endswith("/a.md") and block.collected_at is not None
    assert block.centers == ((ids[0], 1),)
    assert all(c.locator["path"] == "docs/a.md" for c in block.chunks)


def test_two_documents_two_blocks(store: PostgresStore) -> None:
    seed_doc(store, "a.md", ["목표어 목표어 하나"])
    seed_doc(store, "b.md", ["목표어 둘"])
    result = _keyword(store, "목표어")
    assert [b.source_id for b in result.context] == ["S1", "S2"]
    assert len({b.artifact_id for b in result.context}) == 2
