"""`qk-dev store bench`: 저장소 검색 지연과 저장 사용량을 합성 데이터로 잰다(QK-STO-001 SC-005·SC-006, research R-12).

로컬 DB 안에 `qk_bench_<무작위>` 데이터베이스를 만들어 쓰고 끝나면 지운다. 실제 팀 자료와 외부 API를 쓰지 않는다.
"""

from __future__ import annotations

import io
import math
import platform
import random
import secrets
import statistics
import sys
import time
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from typing import TextIO

import psycopg

from qello_knowledge.adapters.postgres.connection import database_url, is_local, with_database
from qello_knowledge.adapters.postgres.migrate import apply_migrations, load_migrations
from qello_knowledge.adapters.postgres.store import PostgresStore
from qello_knowledge.domain.store import EMBEDDING_DIMENSION, ArtifactRecord, ChunkInput, EmbeddingRef

IMAGE = "supabase/postgres:17.11.0.004"  # compose.yaml과 같게 유지한다
MODEL = "bench-model"
PHASE2_TEXT_BYTES = 10_000_000  # ADR-008 Phase 2 예상 원문 규모
STORAGE_BUDGET_BYTES = 500_000_000  # spec SC-006 저장 예산 초기값

WORDS = (
    "결제 재시도 배포 권한 청크 색인 검색 임베딩 동기화 저장소 마이그레이션 인덱스 버전 출처 문서 회의 일정 담당자 "
    "설정 환경 서버 요청 응답 오류 로그 사용자 팀 공용 확인 정책 절차 기준 평가 질문 답변 근거 원본 수집 시각"
).split()
IDENTIFIERS = ("retryPayment", "/payments/{id}/cancel", "max_retry_count", "syncClickUpTasks", "access_scope")


def _unit_vector(rng: random.Random) -> list[float]:
    raw = [rng.gauss(0, 1) for _ in range(EMBEDDING_DIMENSION)]
    norm = math.sqrt(sum(v * v for v in raw))
    return [v / norm for v in raw]


def _sentence(rng: random.Random, target_bytes: int) -> str:
    parts: list[str] = []
    size = 0
    while size < target_bytes:
        word = rng.choice(IDENTIFIERS) if rng.random() < 0.03 else rng.choice(WORDS)
        parts.append(word)
        size += len(word.encode("utf-8")) + 1
    return " ".join(parts)


def _percentiles(samples: list[float]) -> tuple[float, float]:
    ordered = sorted(samples)
    p95 = ordered[min(len(ordered) - 1, math.ceil(0.95 * len(ordered)) - 1)]
    return statistics.median(ordered), p95


def _time(call: Callable[[], object], repeat: int) -> list[float]:
    samples = []
    for _ in range(repeat):
        start = time.perf_counter()
        call()
        samples.append((time.perf_counter() - start) * 1000)
    return samples


def _load(store: PostgresStore, rng: random.Random, text_bytes: int, chunk_bytes: int, chunks_per_doc: int) -> int:
    total = 0
    doc = 0
    collected_at = datetime(2026, 10, 19, tzinfo=UTC)
    while total < text_bytes:
        artifact_id = store.upsert_artifact(
            ArtifactRecord(
                source_kind="github",
                source_id=f"bench/{doc}.md",
                source_url=f"https://example.invalid/bench/{doc}",
                source_version="bench",
                collected_at=collected_at,
                content_hash=f"bench-{doc}",
                artifact_kind="markdown",
                access_scope="team",
            )
        )
        chunks = []
        for i in range(chunks_per_doc):
            body = _sentence(rng, chunk_bytes)
            total += len(body.encode("utf-8"))
            ref = EmbeddingRef(f"bench-{doc}-{i}", MODEL)
            store.put_embedding(ref, _unit_vector(rng))
            chunks.append(
                ChunkInput(
                    ordinal=i,
                    locator={"path": f"bench/{doc}.md", "chunk": i},
                    body=body,
                    search_text=body,
                    chunking_version="bench",
                    embedding=ref,
                )
            )
        store.replace_chunks(artifact_id, "bench", "bench", chunks)
        doc += 1
    return total


def _index_scans(conn: psycopg.Connection) -> dict[str, int]:
    conn.execute("SELECT pg_stat_clear_snapshot()")
    rows = conn.execute(
        "SELECT indexrelname, idx_scan FROM pg_stat_user_indexes"
        " WHERE indexrelname IN ('embedding_vector_hnsw', 'chunk_search_text_pgroonga')"
    ).fetchall()
    return {name: int(count) for name, count in rows}


def run_bench(
    source: Mapping[str, str],
    *,
    text_bytes: int = 1_100_000,
    chunk_bytes: int = 1_200,
    chunks_per_doc: int = 8,
    repeat: int = 100,
    top_n: int = 20,
    seed: int = 20261019,
    out: TextIO = sys.stdout,
) -> int:
    def write(line: str) -> None:
        print(line, file=out)

    if not is_local(source):
        write("DATABASE_URL이 로컬 개발 DB가 아니어서 측정을 거부한다.")
        return 1
    admin = database_url(source)
    name = f"qk_bench_{secrets.token_hex(4)}"
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
    url = with_database(admin, name)
    try:
        with psycopg.connect(url, autocommit=True) as conn:
            if apply_migrations(conn, load_migrations(), is_local=True, out=io.StringIO()) != 0:
                write("마이그레이션 적용에 실패했다.")
                return 1
            conn.execute(
                "INSERT INTO qk.index_version (id, embedding_model, dimension, chunking_version,"
                " metadata_schema_version, status) VALUES ('bench', %s, 1024, 'bench', 'bench', 'active')",
                (MODEL,),
            )
        rng = random.Random(seed)  # noqa: S311 - 재현 가능한 합성 데이터용이다
        with PostgresStore(url) as store:
            loaded = _load(store, rng, text_bytes, chunk_bytes, chunks_per_doc)
            with psycopg.connect(url, autocommit=True) as conn:
                conn.execute("ANALYZE")
                scans_before = _index_scans(conn)
            queries = [_unit_vector(rng) for _ in range(repeat)]
            terms = [rng.choice(WORDS + list(IDENTIFIERS)) for _ in range(repeat)]
            store.search_vector(queries[0], top_n)  # 첫 호출 준비 비용을 빼려고 한 번 먼저 부른다
            store.search_keyword(terms[0], top_n)
            next_query, next_term = iter(queries).__next__, iter(terms).__next__
            vector_ms = _time(lambda: store.search_vector(next_query(), top_n), repeat)
            keyword_ms = _time(lambda: store.search_keyword(next_term(), top_n), repeat)
            usage = store.usage()
        with psycopg.connect(url, autocommit=True) as conn:
            conn.execute("SELECT pg_stat_force_next_flush()")
        time.sleep(1)
        with psycopg.connect(url, autocommit=True) as conn:
            scans_after = _index_scans(conn)
            qk_bytes = conn.execute(
                "SELECT coalesce(sum(pg_total_relation_size(c.oid)), 0) FROM pg_class c"
                " JOIN pg_namespace n ON n.oid = c.relnamespace WHERE n.nspname = 'qk' AND c.relkind = 'r'"
            ).fetchone()[0]
    finally:
        with psycopg.connect(admin, autocommit=True) as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')

    ratio = qk_bytes / loaded
    estimate = ratio * PHASE2_TEXT_BYTES
    v50, v95 = _percentiles(vector_ms)
    k50, k95 = _percentiles(keyword_ms)
    used = {k: scans_after.get(k, 0) - scans_before.get(k, 0) for k in scans_before}
    write(
        f"conditions: image={IMAGE} machine={platform.machine()} system={platform.system()}"
        f" repeat={repeat} top_n={top_n} seed={seed} measured_at={datetime.now(UTC):%Y-%m-%d}"
    )
    write(f"data: text_bytes={loaded} chunks={usage.chunk_count} vectors={usage.embedding_count} dim=1024")
    write(f"vector_search_ms: p50={v50:.1f} p95={v95:.1f}")
    write(f"keyword_search_ms: p50={k50:.1f} p95={k95:.1f}")
    write(f"index_scans: {', '.join(f'{k}={v}' for k, v in sorted(used.items()))}")
    write(f"storage: qk_tables_bytes={qk_bytes} database_bytes={usage.total_bytes} ratio_to_text={ratio:.1f}")
    write(
        f"phase2_estimate: text_bytes={PHASE2_TEXT_BYTES} qk_tables_bytes={estimate:.0f}"
        f" budget_share={estimate / STORAGE_BUDGET_BYTES:.1%}"
    )
    return 0
