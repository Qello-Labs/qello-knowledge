"""저장소 테스트용 합성 데이터. 실제 팀 자료와 외부 API를 쓰지 않는다."""

from __future__ import annotations

import math
import random
import secrets
import zlib
from datetime import UTC, datetime

import psycopg
from psycopg.conninfo import make_conninfo

from qello_knowledge.domain.store import EMBEDDING_DIMENSION, ArtifactRecord, ChunkInput, EmbeddingRef
from qello_knowledge.ports.store import Store
from tests.conftest import local_db_port

ACTIVE = "v1"
ARCHIVED = "v0"
MODEL = "@cf/baai/bge-m3"
COLLECTED_AT = datetime(2026, 10, 19, 9, 0, tzinfo=UTC)


def admin_url() -> str:
    # compose.yaml의 로컬 전용 기본 계정이다.
    return database_url_for("postgres")


def database_url_for(name: str) -> str:
    return make_conninfo(host="127.0.0.1", port=local_db_port(), user="postgres", password="postgres", dbname=name)


def create_database(prefix: str = "qk_test") -> str:
    name = f"{prefix}_{secrets.token_hex(4)}"
    with psycopg.connect(admin_url(), autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
    return name


def drop_database(name: str) -> None:
    with psycopg.connect(admin_url(), autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


def seed_index_versions(conn: psycopg.Connection, *, active: bool = True) -> None:
    conn.execute(
        "INSERT INTO qk.index_version"
        " (id, embedding_model, dimension, chunking_version, metadata_schema_version, status)"
        " VALUES (%s, %s, 1024, 'chunk-v1', 'meta-v1', %s), (%s, %s, 1024, 'chunk-v0', 'meta-v1', 'archived')",
        (ACTIVE, MODEL, "active" if active else "ready", ARCHIVED, MODEL),
    )


def vec(seed: int) -> list[float]:
    """고정 시드 단위 벡터."""
    rng = random.Random(seed)  # noqa: S311 - 재현 가능한 합성 데이터용이다
    raw = [rng.uniform(-1, 1) for _ in range(EMBEDDING_DIMENSION)]
    norm = math.sqrt(sum(v * v for v in raw))
    return [v / norm for v in raw]


def near(base: list[float], seed: int, eps: float = 0.05) -> list[float]:
    noise = vec(seed)
    mixed = [b + eps * n for b, n in zip(base, noise, strict=True)]
    norm = math.sqrt(sum(v * v for v in mixed))
    return [v / norm for v in mixed]


def artifact(
    store: Store,
    source_id: str,
    *,
    access_scope: str | None = "team",
    source_kind: str = "github",
    artifact_kind: str = "markdown",
    source_version: str = "sha-1",
) -> int:
    return store.upsert_artifact(
        ArtifactRecord(
            source_kind=source_kind,
            source_id=source_id,
            source_url=f"https://example.invalid/{source_kind}/{source_id}",
            source_version=source_version,
            collected_at=COLLECTED_AT,
            content_hash=f"hash-{source_id}",
            artifact_kind=artifact_kind,
            title=source_id,
            access_scope=access_scope,
        )
    )


def chunk(
    ordinal: int,
    body: str,
    *,
    embedding: EmbeddingRef | None = None,
    heading_path: tuple[str, ...] = (),
    locator: dict | None = None,
) -> ChunkInput:
    return ChunkInput(
        ordinal=ordinal,
        locator={"path": "docs/sample.md", "lines": [ordinal * 10 + 1, ordinal * 10 + 9]}
        if locator is None
        else locator,
        heading_path=heading_path,
        body=body,
        search_text=body,
        chunking_version="chunk-v1",
        embedding=embedding,
    )


def embedded(store: Store, key: str, vector: list[float]) -> EmbeddingRef:
    ref = EmbeddingRef(input_hash=key, model_version=MODEL)
    store.put_embedding(ref, vector)
    return ref


def document(
    store: Store,
    source_id: str,
    bodies: list[str],
    *,
    vector: list[float] | None = None,
    index_version: str = ACTIVE,
    **artifact_kwargs: object,
) -> int:
    """자료 하나와 청크 묶음을 저장한다. `vector`를 주면 모든 청크가 그 근처 벡터를 갖는다."""
    artifact_id = artifact(store, source_id, **artifact_kwargs)  # type: ignore[arg-type]
    chunks = []
    for i, body in enumerate(bodies):
        ref = (
            embedded(store, f"{source_id}-{i}", near(vector, zlib.crc32(f"{source_id}-{i}".encode())))
            if vector
            else None
        )
        chunks.append(chunk(i, body, embedding=ref))
    store.replace_chunks(artifact_id, index_version, str(artifact_kwargs.get("source_version", "sha-1")), chunks)
    return artifact_id
