"""US4: 문서 하나의 청크를 한 번에 교체한다(SC-003, FR-012·013).

교체 도중 실패는 위치 정보를 비우거나 없는 인덱스 버전을 줘서 일으킨다.
제품 코드에 테스트 훅을 두지 않는다(research R-10).
"""

from __future__ import annotations

import threading

import psycopg
import pytest

from qello_knowledge.adapters.postgres.store import PostgresStore
from qello_knowledge.domain.store import ChunkInput, InvalidRecord
from tests.localdb.store.builders import ACTIVE, artifact, chunk, document

pytestmark = pytest.mark.localdb

WORD = "교체시험"


def _visible(store: PostgresStore) -> list[str]:
    return sorted(hit.body for hit in store.search_keyword(WORD, 50).hits)


def _new_chunks(prefix: str, count: int) -> list[ChunkInput]:
    return [chunk(i, f"{WORD} {prefix}{i}") for i in range(count)]


@pytest.fixture
def doc_a(store: PostgresStore) -> int:
    artifact_id = artifact(store, "a.md")
    store.replace_chunks(artifact_id, ACTIVE, "sha-1", _new_chunks("old", 5))
    document(store, "b.md", [f"{WORD} 다른문서"])
    return artifact_id


def test_replace_swaps_only_that_document(store: PostgresStore, doc_a: int) -> None:
    assert store.replace_chunks(doc_a, ACTIVE, "sha-2", _new_chunks("new", 3)) == "replaced"
    assert _visible(store) == [f"{WORD} new0", f"{WORD} new1", f"{WORD} new2", f"{WORD} 다른문서"]
    trace = store.search_keyword(f"{WORD} new0", 1).hits[0].provenance
    assert trace.source_version == "sha-2"


def test_failed_replace_keeps_previous_chunks(store: PostgresStore, doc_a: int) -> None:
    before = _visible(store)
    broken = [*_new_chunks("new", 2), chunk(2, f"{WORD} new2", locator={})]
    with pytest.raises(InvalidRecord):
        store.replace_chunks(doc_a, ACTIVE, "sha-2", broken)
    assert _visible(store) == before


def test_db_constraint_failure_mid_replace_keeps_previous_chunks(store: PostgresStore, doc_a: int) -> None:
    """경계 검증을 통과하고 DB에서 실패하는 경우(존재하지 않는 인덱스 버전)도 이전 묶음이 남는다."""
    before = _visible(store)
    with pytest.raises(InvalidRecord):
        store.replace_chunks(doc_a, "no-such-version", "sha-2", _new_chunks("new", 3))
    assert _visible(store) == before


def test_same_request_twice_is_unchanged(store: PostgresStore, doc_a: int, db_url: str) -> None:
    assert store.replace_chunks(doc_a, ACTIVE, "sha-2", _new_chunks("new", 3)) == "replaced"
    with psycopg.connect(db_url) as conn:
        ids_before = conn.execute("SELECT id FROM qk.chunk ORDER BY id").fetchall()
    assert store.replace_chunks(doc_a, ACTIVE, "sha-2", _new_chunks("new", 3)) == "unchanged"
    with psycopg.connect(db_url) as conn:
        assert conn.execute("SELECT id FROM qk.chunk ORDER BY id").fetchall() == ids_before


def test_readers_see_old_chunks_until_commit(store: PostgresStore, doc_a: int, db_url: str) -> None:
    """교체 트랜잭션을 붙잡은 동안 다른 세션은 이전 묶음만 본다."""
    before = _visible(store)
    with psycopg.connect(db_url) as writer:
        writer.execute("SELECT 1 FROM qk.artifact WHERE id = %s FOR UPDATE", (doc_a,))
        writer.execute("DELETE FROM qk.chunk WHERE artifact_id = %s", (doc_a,))
        writer.execute(
            "INSERT INTO qk.chunk (artifact_id, index_version, source_version, locator, ordinal, body, search_text,"
            " chunking_version) VALUES (%s, %s, 'sha-2', '{\"path\": \"a\"}', 0, %s, %s, 'chunk-v1')",
            (doc_a, ACTIVE, f"{WORD} new0", f"{WORD} new0"),
        )
        assert _visible(store) == before
        writer.rollback()
    assert _visible(store) == before


def test_concurrent_replaces_never_mix(db_url: str, doc_a: int) -> None:
    barrier = threading.Barrier(2)
    errors: list[BaseException] = []

    def worker(prefix: str, count: int) -> None:
        try:
            with PostgresStore(db_url) as own:
                barrier.wait()
                own.replace_chunks(doc_a, ACTIVE, f"sha-{prefix}", _new_chunks(prefix, count))
        except BaseException as exc:  # noqa: BLE001 - 스레드 예외를 본 스레드에서 확인한다
            errors.append(exc)

    for _ in range(5):
        threads = [threading.Thread(target=worker, args=("A", 3)), threading.Thread(target=worker, args=("B", 2))]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert errors == []
        with PostgresStore(db_url) as reader:
            bodies = [b for b in _visible(reader) if "다른문서" not in b]
        assert bodies in ([f"{WORD} A0", f"{WORD} A1", f"{WORD} A2"], [f"{WORD} B0", f"{WORD} B1"])
