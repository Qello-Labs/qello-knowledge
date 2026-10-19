"""주변 청크 조회(FR-011)."""

from __future__ import annotations

import psycopg
import pytest

from qello_knowledge.adapters.postgres.store import PostgresStore
from tests.localdb.store.builders import ACTIVE, artifact, chunk

pytestmark = pytest.mark.localdb

SECTIONS = [
    ("설치", ()),
    ("설치 개요", ("설치",)),
    ("요구 사항", ("설치", "요구 사항")),
    ("Docker 설치", ("설치", "요구 사항")),
    ("포트 설정", ("설치", "요구 사항")),
    ("문제 해결", ("문제 해결",)),
]


def _chunk_ids(db_url: str) -> list[int]:
    with psycopg.connect(db_url) as conn:
        return [row[0] for row in conn.execute("SELECT id FROM qk.chunk ORDER BY ordinal").fetchall()]


@pytest.fixture
def guide(store: PostgresStore) -> None:
    artifact_id = artifact(store, "guide.md")
    store.replace_chunks(
        artifact_id, ACTIVE, "sha-1", [chunk(i, body, heading_path=path) for i, (body, path) in enumerate(SECTIONS)]
    )


def test_returns_before_after_and_parents(store: PostgresStore, guide: None, db_url: str) -> None:
    ids = _chunk_ids(db_url)
    result = store.chunk_neighbors(ids[4], before=1, after=1)
    assert result is not None
    assert result.center.body == "포트 설정"
    assert [h.body for h in result.before] == ["Docker 설치"]
    assert [h.body for h in result.after] == ["문제 해결"]
    assert [h.body for h in result.parents] == ["설치 개요", "요구 사항"]


def test_hidden_chunk_returns_none(store: PostgresStore, guide: None, db_url: str) -> None:
    ids = _chunk_ids(db_url)
    store.mark_deleted("github", "guide.md")
    assert store.chunk_neighbors(ids[2], 1, 1) is None
    assert store.chunk_neighbors(999_999, 1, 1) is None
