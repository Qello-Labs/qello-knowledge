"""`Store` 경계의 PostgreSQL 구현(QK-STO-001).

검색은 마이그레이션 `0002_search_functions.sql`의 SQL 함수를 부른다. 노출 조건은 그 함수 안에서만 판정하고
여기서 결과를 다시 거르지 않는다(FR-008). 경계 밖으로 psycopg 타입을 내보내지 않는다(FR-015).
"""

from __future__ import annotations

import json
from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import datetime
from typing import Any

import psycopg
from psycopg import errors

from qello_knowledge.adapters.postgres.connection import connect
from qello_knowledge.domain.store import (
    NO_FILTER,
    ArtifactRecord,
    ChunkInput,
    ChunkTrace,
    EmbeddingRef,
    InvalidRecord,
    NeighborResult,
    Provenance,
    ReplaceOutcome,
    SearchFilter,
    SearchHit,
    SearchResult,
    StoreError,
    StoreUnavailable,
    StoreUsage,
    chunk_set_hash,
    clamp_top_n,
    validate_artifact,
    validate_chunks,
    validate_vector,
)

_INVALID = (errors.IntegrityError, errors.DataError)


def _vector_text(vector: Sequence[float]) -> str:
    return "[" + ",".join(repr(float(v)) for v in vector) + "]"


def _parse_vector(text: str) -> tuple[float, ...]:
    return tuple(float(v) for v in text.strip("[]").split(",") if v)


def _parse_time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _provenance(data: Mapping[str, Any]) -> Provenance:
    collected_at = _parse_time(data["collected_at"])
    assert collected_at is not None  # noqa: S101 - collected_at은 NOT NULL 칼럼이다
    return Provenance(
        source_url=data["source_url"],
        source_version=data["source_version"],
        locator=data["locator"],
        heading_path=tuple(data["heading_path"]),
        collected_at=collected_at,
        source_modified_at=_parse_time(data.get("source_modified_at")),
    )


def _hit(data: Mapping[str, Any]) -> SearchHit:
    return SearchHit(
        chunk_id=int(data["chunk_id"]),
        rank=int(data["rank"]),
        score=float(data["score"]),
        body=data["body"],
        provenance=_provenance(data["provenance"]),
    )


def _search_result(data: Mapping[str, Any]) -> SearchResult:
    active = data["active_index_version"]
    if active is None:
        return SearchResult(status="no_active_index")
    return SearchResult(status="ok", index_version=active, hits=tuple(_hit(h) for h in data["hits"]))


def _kinds(values: tuple[str, ...]) -> list[str] | None:
    return list(values) or None


class PostgresStore:
    """연결 하나를 쓴다. 스레드마다 따로 만든다."""

    def __init__(self, url: str) -> None:
        self._url = url
        self._conn: psycopg.Connection | None = None

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def __enter__(self) -> PostgresStore:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    @contextmanager
    def _db(self) -> Iterator[psycopg.Connection]:
        """DB 오류를 경계 오류로 바꾼다. 메시지에는 오류 분류만 남긴다."""
        if self._conn is None or self._conn.closed:
            self._conn = connect(self._url)
        try:
            yield self._conn
        except _INVALID as exc:
            raise InvalidRecord(f"저장소가 입력을 거부했다: {exc.diag.sqlstate} {exc.diag.message_primary}") from exc
        except psycopg.OperationalError as exc:
            self.close()
            raise StoreUnavailable("저장소를 쓸 수 없다") from exc
        except psycopg.Error as exc:
            raise StoreError(f"저장소 오류: {exc.diag.sqlstate}") from exc

    def upsert_artifact(self, record: ArtifactRecord) -> int:
        validate_artifact(record)
        with self._db() as conn:
            row = conn.execute(
                """
                INSERT INTO qk.artifact (source_kind, source_id, source_url, source_version, source_modified_at,
                                         collected_at, content_hash, artifact_kind, title, access_scope)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (source_kind, source_id) DO UPDATE SET
                    source_url = EXCLUDED.source_url,
                    source_version = EXCLUDED.source_version,
                    source_modified_at = EXCLUDED.source_modified_at,
                    collected_at = EXCLUDED.collected_at,
                    content_hash = EXCLUDED.content_hash,
                    artifact_kind = EXCLUDED.artifact_kind,
                    title = EXCLUDED.title,
                    access_scope = EXCLUDED.access_scope,
                    status = 'active',
                    updated_at = now()
                RETURNING id
                """,
                (
                    record.source_kind,
                    record.source_id,
                    record.source_url,
                    record.source_version,
                    record.source_modified_at,
                    record.collected_at,
                    record.content_hash,
                    record.artifact_kind,
                    record.title,
                    record.access_scope,
                ),
            ).fetchone()
        assert row is not None  # noqa: S101 - RETURNING은 언제나 한 행을 준다
        return int(row[0])

    def replace_chunks(
        self, artifact_id: int, index_version: str, source_version: str, chunks: Sequence[ChunkInput]
    ) -> ReplaceOutcome:
        validate_chunks(source_version, chunks)
        new_hash = chunk_set_hash(index_version, source_version, chunks)
        with self._db() as conn, conn.transaction():
            # 같은 자료의 교체를 직렬화한다. 커밋 전에는 다른 세션이 이전 묶음만 본다(research R-07).
            row = conn.execute(
                "SELECT chunk_set_hash FROM qk.artifact WHERE id = %s FOR UPDATE", (artifact_id,)
            ).fetchone()
            if row is None:
                raise InvalidRecord(f"원본 자료가 없다: {artifact_id}")
            if row[0] == new_hash:
                return "unchanged"
            embedding_ids = self._embedding_ids(conn, chunks)
            conn.execute(
                "DELETE FROM qk.chunk WHERE artifact_id = %s AND index_version = %s", (artifact_id, index_version)
            )
            with conn.cursor() as cur:
                cur.executemany(
                    """
                    INSERT INTO qk.chunk (artifact_id, index_version, source_version, locator, heading_path, ordinal,
                                          body, search_text, chunking_version, embedding_id)
                    VALUES (%s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s)
                    """,
                    [
                        (
                            artifact_id,
                            index_version,
                            source_version,
                            json.dumps(dict(c.locator), ensure_ascii=False),
                            list(c.heading_path),
                            c.ordinal,
                            c.body,
                            c.search_text,
                            c.chunking_version,
                            embedding_ids.get(c.ordinal),
                        )
                        for c in chunks
                    ],
                )
            conn.execute(
                "UPDATE qk.artifact SET source_version = %s, chunk_set_hash = %s, updated_at = now() WHERE id = %s",
                (source_version, new_hash, artifact_id),
            )
        return "replaced"

    @staticmethod
    def _embedding_ids(conn: psycopg.Connection, chunks: Sequence[ChunkInput]) -> dict[int, int]:
        ids: dict[int, int] = {}
        for chunk in chunks:
            if chunk.embedding is None:
                continue
            row = conn.execute(
                "SELECT id FROM qk.embedding WHERE input_hash = %s AND model_version = %s",
                (chunk.embedding.input_hash, chunk.embedding.model_version),
            ).fetchone()
            if row is None:
                raise InvalidRecord(f"청크 {chunk.ordinal}이 가리키는 임베딩이 없다")
            ids[chunk.ordinal] = int(row[0])
        return ids

    def mark_deleted(self, source_kind: str, source_id: str) -> None:
        with self._db() as conn:
            conn.execute(
                "UPDATE qk.artifact SET status = 'deleted', updated_at = now()"
                " WHERE source_kind = %s AND source_id = %s AND status <> 'deleted'",
                (source_kind, source_id),
            )

    def put_embedding(self, ref: EmbeddingRef, vector: Sequence[float]) -> None:
        validate_vector(vector)
        with self._db() as conn:
            conn.execute(
                "INSERT INTO qk.embedding (input_hash, model_version, vector) VALUES (%s, %s, %s::vector)"
                " ON CONFLICT (input_hash, model_version) DO NOTHING",
                (ref.input_hash, ref.model_version, _vector_text(vector)),
            )

    def find_embedding(self, ref: EmbeddingRef) -> tuple[float, ...] | None:
        with self._db() as conn:
            row = conn.execute(
                "SELECT vector::text FROM qk.embedding WHERE input_hash = %s AND model_version = %s",
                (ref.input_hash, ref.model_version),
            ).fetchone()
        return _parse_vector(row[0]) if row else None

    def search_vector(self, query: Sequence[float], top_n: int, filters: SearchFilter = NO_FILTER) -> SearchResult:
        validate_vector(query)
        with self._db() as conn:
            row = conn.execute(
                "SELECT qk.search_vector(%s::vector, %s, %s, %s)",
                (_vector_text(query), clamp_top_n(top_n), _kinds(filters.source_kinds), _kinds(filters.artifact_kinds)),
            ).fetchone()
        assert row is not None  # noqa: S101
        return _search_result(row[0])

    def search_keyword(self, query: str, top_n: int, filters: SearchFilter = NO_FILTER) -> SearchResult:
        if not query.strip():
            return SearchResult(status="ok")
        with self._db() as conn:
            row = conn.execute(
                "SELECT qk.search_keyword(%s, %s, %s, %s)",
                (query, clamp_top_n(top_n), _kinds(filters.source_kinds), _kinds(filters.artifact_kinds)),
            ).fetchone()
        assert row is not None  # noqa: S101
        return _search_result(row[0])

    def chunk_neighbors(self, chunk_id: int, before: int, after: int) -> NeighborResult | None:
        with self._db() as conn:
            row = conn.execute("SELECT qk.chunk_neighbors(%s, %s, %s)", (chunk_id, before, after)).fetchone()
        if row is None or row[0] is None:
            return None
        data = row[0]
        return NeighborResult(
            center=_hit(data["center"]),
            before=tuple(_hit(h) for h in data["before"]),
            after=tuple(_hit(h) for h in data["after"]),
            parents=tuple(_hit(h) for h in data["parents"]),
        )

    def trace_chunk(self, chunk_id: int) -> ChunkTrace | None:
        with self._db() as conn:
            row = conn.execute(
                """
                SELECT a.source_url, c.source_version, c.locator, c.heading_path, a.collected_at, a.source_modified_at,
                       c.chunking_version, c.index_version, e.model_version
                FROM qk.chunk c
                JOIN qk.artifact a ON a.id = c.artifact_id
                LEFT JOIN qk.embedding e ON e.id = c.embedding_id
                WHERE c.id = %s
                """,
                (chunk_id,),
            ).fetchone()
        if row is None:
            return None
        url, version, locator, heading_path, collected_at, modified_at, chunking, index_version, model = row
        return ChunkTrace(
            chunk_id=chunk_id,
            provenance=Provenance(
                source_url=url,
                source_version=version,
                locator=locator,
                heading_path=tuple(heading_path),
                collected_at=collected_at,
                source_modified_at=modified_at,
            ),
            chunking_version=chunking,
            index_version=index_version,
            embedding_model=model,
        )

    def usage(self) -> StoreUsage:
        with self._db() as conn:
            row = conn.execute(
                "SELECT pg_database_size(current_database()),"
                " (SELECT count(*) FROM qk.chunk), (SELECT count(*) FROM qk.embedding)"
            ).fetchone()
        assert row is not None  # noqa: S101
        return StoreUsage(total_bytes=int(row[0]), chunk_count=int(row[1]), embedding_count=int(row[2]))
