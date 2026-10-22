"""검색 로컬 DB 시험용 합성 데이터(QK-RET-001 tasks T001). 실제 팀 자료와 외부 API를 쓰지 않는다."""

from __future__ import annotations

import zlib
from collections.abc import Sequence

import psycopg

from qello_knowledge.adapters.postgres.store import PostgresStore
from qello_knowledge.domain.store import ChunkInput
from tests.localdb.store.builders import ACTIVE, artifact, embedded, near, vec

Part = str | tuple[str, tuple[str, ...]]  # 본문 또는 (본문, 제목 경로)


def seed_doc(
    store: PostgresStore,
    source_id: str,
    parts: Sequence[Part],
    *,
    vector: list[float] | None = None,
    index_version: str = ACTIVE,
    search_texts: Sequence[str] | None = None,
    **artifact_kwargs: object,
) -> tuple[int, list[int]]:
    """자료 하나와 청크 묶음을 저장하고 (자료 id, 청크 id 목록)을 순서 번호 순으로 돌려준다."""
    artifact_id = artifact(store, source_id, **artifact_kwargs)  # type: ignore[arg-type]
    chunks = []
    for ordinal, part in enumerate(parts):
        body, heading_path = (part, ()) if isinstance(part, str) else part
        ref = None
        if vector is not None:
            ref = embedded(store, f"{source_id}-{index_version}-{ordinal}", near(vector, zlib.crc32(body.encode())))
        chunks.append(
            ChunkInput(
                ordinal=ordinal,
                locator={"path": f"docs/{source_id}", "lines": [ordinal * 10 + 1, ordinal * 10 + 9]},
                heading_path=heading_path,
                body=body,
                search_text=search_texts[ordinal] if search_texts else body,
                chunking_version="chunk-v1",
                embedding=ref,
            )
        )
    store.replace_chunks(artifact_id, index_version, str(artifact_kwargs.get("source_version", "sha-1")), chunks)
    return artifact_id, chunk_ids(store, artifact_id, index_version)


def chunk_ids(store: PostgresStore, artifact_id: int, index_version: str = ACTIVE) -> list[int]:
    with store._db() as conn:  # noqa: SLF001 - 시험 전용 조회
        rows = conn.execute(
            "SELECT id FROM qk.chunk WHERE artifact_id = %s AND index_version = %s ORDER BY ordinal",
            (artifact_id, index_version),
        ).fetchall()
    return [int(r[0]) for r in rows]


def set_status(db_url: str, source_id: str, status: str) -> None:
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute("UPDATE qk.artifact SET status = %s WHERE source_id = %s", (status, source_id))


def record_run(
    db_url: str, run_id: str, source_name: str, status: str, origin_version: str | None, started: str
) -> None:
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO qk.sync_run (run_id, trigger, target, started_at, rules_version, chunking_version,"
            " index_version, status) VALUES (%s, 'manual', 'local', %s, 'r', 'c', %s, %s)",
            (run_id, started, ACTIVE, status),
        )
        conn.execute(
            "INSERT INTO qk.sync_run_source (run_id, source_name, status, origin_version) VALUES (%s, %s, %s, %s)",
            (run_id, source_name, status, origin_version),
        )


__all__ = ["ACTIVE", "chunk_ids", "record_run", "seed_doc", "set_status", "vec"]
