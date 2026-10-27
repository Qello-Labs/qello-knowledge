"""코드 청크를 저장한 뒤 검색·문맥 확장·청크 추적의 출처 정보로 그대로 돌아오는지.

QK-CHK-001 spec SC-006, US3-5, tasks T025.

임베딩은 고정 시드 가짜 벡터다. 외부 호출이 없다.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest

from qello_knowledge.adapters.postgres.store import PostgresStore
from qello_knowledge.chunking.code.service import chunk_code
from qello_knowledge.domain.chunking import ChunkingSettings, CodeChunkingSettings
from tests.localdb.retrieval.builders import ACTIVE, chunk_ids, seed_doc, vec
from tests.localdb.store.builders import artifact, embedded
from tests.unit.chunking.code.helpers import FIXTURES

pytestmark = pytest.mark.localdb

LOCATION = "src/main/java/com/acme/web/OrderController.java"
MIGRATIONS = "src/qello_knowledge/adapters/postgres/migrations"


def _store_code(store: PostgresStore):
    body = (FIXTURES / "java_controller.java").read_text(encoding="utf-8")
    result = chunk_code(body, location=LOCATION, settings=ChunkingSettings(), code=CodeChunkingSettings())
    artifact_id = artifact(store, LOCATION, artifact_kind="code")
    chunks = [
        replace(d.chunk, embedding=embedded(store, f"code-{d.chunk.ordinal}", vec(500 + d.chunk.ordinal)))
        for d in result.drafts
    ]
    store.replace_chunks(artifact_id, ACTIVE, "sha-1", chunks)
    return result.drafts, chunk_ids(store, artifact_id)


def test_search_context_and_trace_return_code_metadata(store: PostgresStore) -> None:
    drafts, ids = _store_code(store)
    method = drafts[3].chunk
    assert method.locator["code"]["symbol"] == "getOrder(Long)"

    [vector_hit] = [h for h in store.search_vector(vec(503), 3).hits if h.chunk_id == ids[3]]
    assert vector_hit.provenance.locator == method.locator
    assert vector_hit.provenance.heading_path == method.heading_path

    keyword_hits = {h.chunk_id: h for h in store.search_keyword("ResponseEntity", 10).hits}
    assert keyword_hits[ids[3]].provenance.locator == method.locator

    item = store.chunk_context([ids[3]], 1, 1).items[0]
    assert item.center.provenance.locator == method.locator
    assert item.before[0].provenance.locator == drafts[2].chunk.locator

    trace = store.trace_chunk(ids[3])
    assert trace is not None
    assert trace.provenance.locator == method.locator
    assert trace.provenance.heading_path == ("OrderController", "getOrder(Long)")
    assert trace.chunking_version == method.chunking_version


def test_markdown_provenance_is_unchanged(store: PostgresStore) -> None:
    _store_code(store)
    _, ids = seed_doc(store, "a.md", [("문서 본문", ("문서",))])
    trace = store.trace_chunk(ids[0])
    assert trace is not None
    assert trace.provenance.locator == {"path": "docs/a.md", "lines": [1, 9]}
    assert trace.provenance.heading_path == ("문서",)


def test_no_code_chunking_migration() -> None:
    # 코드 메타데이터는 기존 locator(jsonb)에 들어가 저장 스키마가 그대로다(research R-11). 위 왕복 시험이 그 근거다.
    # 기준 커밋과의 파일 목록 비교는 최종 보고의 git diff로 한다. CI는 깊이 1로 체크아웃해 기준 커밋이 없다(TASK.md).
    root = Path(__file__).resolve().parents[3]
    sql = sorted((root / MIGRATIONS).glob("*.sql"))
    assert sql
    assert not [p.name for p in sql if "QK-CHK-001" in p.read_text(encoding="utf-8")]
