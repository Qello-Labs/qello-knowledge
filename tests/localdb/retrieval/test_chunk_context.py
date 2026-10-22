"""`qk.chunk_context`와 `PostgresStore.source_revisions`(research R-06·R-09, data-model 4.2, tasks T009)."""

from __future__ import annotations

import psycopg
import pytest

from qello_knowledge.adapters.postgres.store import PostgresStore
from tests.localdb.retrieval.builders import record_run, seed_doc, set_status
from tests.localdb.store.builders import ARCHIVED

pytestmark = pytest.mark.localdb

A = ("문서",)
B = ("문서", "설치")
C = ("문서", "설정")


def _ids(neighbors) -> list[int]:
    return [n.chunk_id for n in neighbors]


def test_before_after_in_order_same_document(store: PostgresStore) -> None:
    _, ids = seed_doc(store, "a.md", [f"본문{i}" for i in range(6)])
    _, other = seed_doc(store, "b.md", ["다른 문서"])
    result = store.chunk_context([ids[3], other[0]], 2, 1)
    assert result.index_version == "v1"
    item = result.items[0]
    assert item.center.chunk_id == ids[3] and item.center.ordinal == 3
    assert _ids(item.before) == [ids[1], ids[2]] and _ids(item.after) == [ids[4]]
    assert result.items[1].before == () and result.items[1].after == ()
    assert item.center.artifact_id == result.items[0].before[0].artifact_id
    assert item.center.provenance.source_url.endswith("/a.md") and item.center.provenance.locator["path"] == "docs/a.md"


def test_other_index_version_neighbors_are_excluded(store: PostgresStore) -> None:
    artifact_id, ids = seed_doc(store, "a.md", ["0", "1", "2"])
    seed_doc(store, "a.md", ["옛0", "옛1", "옛2", "옛3"], index_version=ARCHIVED)
    item = store.chunk_context([ids[1]], 3, 3).items[0]
    assert _ids(item.before) == [ids[0]] and _ids(item.after) == [ids[2]]
    assert artifact_id == item.center.artifact_id


def test_section_first(store: PostgresStore) -> None:
    _, ids = seed_doc(
        store,
        "a.md",
        [("머리", A), ("설치1", B), ("설치2", B), ("설치3", B), ("설정1", C), ("설치 다시", B), ("설치 다시2", B)],
    )
    items = {i.center.chunk_id: i for i in store.chunk_context([ids[3], ids[1], ids[6], ids[0]], 0, 0).items}
    assert items[ids[3]].section_first.chunk_id == ids[1]
    assert items[ids[1]].section_first is None  # 중심이 절의 첫 청크
    assert items[ids[6]].section_first.chunk_id == ids[5]  # 같은 제목 경로가 앞에도 있지만 이어진 범위만
    assert items[ids[0]].section_first is None  # 자료의 첫 청크


def test_section_first_without_earlier_other_heading(store: PostgresStore) -> None:
    _, ids = seed_doc(store, "a.md", [("1", B), ("2", B), ("3", B)])
    assert store.chunk_context([ids[2]], 0, 0).items[0].section_first.chunk_id == ids[0]


def test_hidden_or_missing_centers_have_no_item(store: PostgresStore, db_url: str) -> None:
    _, visible = seed_doc(store, "team.md", ["공개"])
    _, unknown = seed_doc(store, "unknown.md", ["미확인"], access_scope=None)
    _, deleted = seed_doc(store, "deleted.md", ["삭제"])
    store.mark_deleted("github", "deleted.md")
    _, archived = seed_doc(store, "archived.md", ["보관"])
    set_status(db_url, "archived.md", "archived")
    _, old = seed_doc(store, "old.md", ["옛"], index_version=ARCHIVED)
    result = store.chunk_context([unknown[0], deleted[0], archived[0], old[0], 999999, visible[0]], 1, 1)
    assert [i.center.chunk_id for i in result.items] == [visible[0]]


def test_limits(store: PostgresStore) -> None:
    _, ids = seed_doc(store, "a.md", [str(i) for i in range(30)])
    result = store.chunk_context(ids[:21], 4, 4)
    assert len(result.items) == 20
    item = next(i for i in result.items if i.center.chunk_id == ids[10])
    assert len(item.before) == 3 and len(item.after) == 3


def test_no_active_version(store: PostgresStore, db_url: str) -> None:
    _, ids = seed_doc(store, "a.md", ["0"])
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute("UPDATE qk.index_version SET status = 'ready' WHERE status = 'active'")
    result = store.chunk_context(ids, 1, 1)
    assert result.index_version is None and result.items == ()


def test_source_revisions_use_latest_succeeded_run(store: PostgresStore, db_url: str) -> None:
    record_run(db_url, "r1", "docs", "succeeded", "sha-old", "2026-10-20T00:00:00Z")
    record_run(db_url, "r2", "docs", "succeeded", "sha-new", "2026-10-21T00:00:00Z")
    record_run(db_url, "r3", "docs", "partial", "sha-partial", "2026-10-22T00:00:00Z")
    record_run(db_url, "r4", "other", "succeeded", "sha-other", "2026-10-21T00:00:00Z")
    assert store.source_revisions() == {"docs": "sha-new", "other": "sha-other"}


def test_source_revisions_empty(store: PostgresStore) -> None:
    assert store.source_revisions() == {}
