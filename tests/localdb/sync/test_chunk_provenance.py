"""버전별 출처 정보(QK-STO-002 research R-01, SC-001의 출처 부분)."""

from dataclasses import replace
from datetime import UTC, datetime

import psycopg
import pytest

from qello_knowledge.domain.store import ArtifactRecord
from tests.localdb.store.builders import chunk, embedded, near, vec

pytestmark = pytest.mark.localdb

V1, V2 = "iv-prov-1", "iv-prov-2"
OLD = ArtifactRecord(
    source_kind="fake",
    source_id="doc-1",
    source_url="https://example.invalid/old",
    source_version="rev-1",
    collected_at=datetime(2026, 10, 1, tzinfo=UTC),
    source_modified_at=datetime(2026, 9, 30, tzinfo=UTC),
    content_hash="h1",
    artifact_kind="markdown",
    title="Old",
    access_scope="team",
)
NEW = replace(
    OLD,
    source_url="https://example.invalid/new",
    source_version="rev-2",
    collected_at=datetime(2026, 11, 1, tzinfo=UTC),
    source_modified_at=datetime(2026, 10, 31, tzinfo=UTC),
    content_hash="h2",
)


@pytest.fixture
def two_versions(db_url, store):
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO qk.index_version(id,embedding_model,dimension,chunking_version,metadata_schema_version,status)"
            " VALUES (%s,'@cf/baai/bge-m3',1024,'c1','meta-v1','active'),"
            " (%s,'@cf/baai/bge-m3',1024,'c2','meta-v1','ready')",
            (V1, V2),
        )
    base = vec(7)
    identity = store.upsert_artifact(OLD)
    old_chunks = [
        chunk(i, f"provenance alpha {i}", embedding=embedded(store, f"old-{i}", near(base, i)), heading_path=("H",))
        for i in range(3)
    ]
    store.replace_chunks(identity, V1, OLD.source_version, old_chunks)
    store.upsert_artifact(NEW)
    new_chunks = [chunk(i, f"provenance alpha new {i}", heading_path=("H",)) for i in range(2)]
    store.replace_chunks(identity, V2, NEW.source_version, new_chunks)
    return identity, base


def _assert_old(provenance):
    assert provenance.source_url == OLD.source_url
    assert provenance.source_version == OLD.source_version
    assert provenance.collected_at == OLD.collected_at
    assert provenance.source_modified_at == OLD.source_modified_at


def test_active_version_keeps_provenance_of_its_own_write(store, two_versions):
    _, base = two_versions
    keyword = store.search_keyword("provenance", 20)
    assert keyword.index_version == V1 and len(keyword.hits) == 3
    for hit in keyword.hits:
        _assert_old(hit.provenance)
    terms = store.search_keyword_terms(["provenance"], 20)
    for hit in terms.hits:
        _assert_old(hit.hit.provenance)
    vector = store.search_vector(base, 20)
    assert len(vector.hits) == 3
    for hit in vector.hits:
        _assert_old(hit.provenance)
    center = keyword.hits[1].chunk_id
    context = store.chunk_context([center], 1, 1)
    item = context.items[0]
    for neighbor in (item.center, *item.before, *item.after):
        _assert_old(neighbor.provenance)
    neighbors = store.chunk_neighbors(center, 1, 1)
    for hit in (neighbors.center, *neighbors.before, *neighbors.after, *neighbors.parents):
        _assert_old(hit.provenance)
    _assert_old(store.trace_chunk(center).provenance)


def test_null_chunk_provenance_falls_back_to_artifact(db_url, store, two_versions):
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute("UPDATE qk.chunk SET source_url=NULL, collected_at=NULL, source_modified_at=NULL")
    hit = store.search_keyword("provenance", 20).hits[0]
    assert hit.provenance.source_url == NEW.source_url
    assert hit.provenance.collected_at == NEW.collected_at
    assert hit.provenance.source_modified_at == NEW.source_modified_at
    assert store.trace_chunk(hit.chunk_id).provenance.source_url == NEW.source_url


def test_null_modified_time_is_not_replaced_by_a_later_version(db_url, store):
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO qk.index_version(id,embedding_model,dimension,chunking_version,metadata_schema_version,status)"
            " VALUES (%s,'@cf/baai/bge-m3',1024,'c1','meta-v1','active'),"
            " (%s,'@cf/baai/bge-m3',1024,'c2','meta-v1','ready')",
            (V1, V2),
        )
    identity = store.upsert_artifact(replace(OLD, source_modified_at=None))
    store.replace_chunks(identity, V1, OLD.source_version, [chunk(0, "provenance beta")])
    store.upsert_artifact(NEW)
    store.replace_chunks(identity, V2, NEW.source_version, [chunk(0, "provenance beta new")])
    hit = store.search_keyword("provenance", 20).hits[0]
    assert hit.provenance.source_modified_at is None
    assert store.trace_chunk(hit.chunk_id).provenance.source_modified_at is None
