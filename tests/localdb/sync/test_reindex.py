"""재색인 통합(QK-STO-002 SC-001·SC-006, US1-2~US1-5, research R-01~R-03). 가짜 자료원·가짜 임베딩만 쓴다.

SC-001의 비교 항목 가운데 "제목"은 검색 결과에 값이 없어 비교 대상이 없다(research R-01).
벡터 근사 결과가 정확 검색과 같아지도록 청크 수를 40개 이하로 둔다.
"""

from dataclasses import replace

import psycopg
import pytest

from qello_knowledge.domain.embedding import ProviderFailureKind
from qello_knowledge.domain.source import ContentFormat
from qello_knowledge.embedding.fake import FakeEmbeddingProvider
from qello_knowledge.ports.embedder import ProviderFailure
from qello_knowledge.sync.activate import activate_first_index
from qello_knowledge.sync.preview import reindex_preview
from qello_knowledge.sync.run import SyncOptions, current_spec, plan_all, run_sync
from tests.localdb.store.builders import vec
from tests.unit.sync.helpers import harness
from tests.unit.sync.reindex_fakes import DOCS, NEW_CHUNKING
from tests.unit.synthetic_secrets import SYNTHETIC

pytestmark = pytest.mark.localdb

REINDEX = SyncOptions(reindex=True)
# 보안 내림·원본 삭제를 함께 넣어 내림 비율 안전장치(20%)를 넘으므로 사람이 확인 옵션을 준 실행이다.
CONFIRMED = SyncOptions(reindex=True, confirm_takedown=True)
QUERIES = ("Synthetic", "Text")


def _snapshot(store):
    """상위 20건의 순위·위치·원본 링크·원본 버전·제목 경로·원본 수정 시각·수집 시각(점수 제외)."""

    def row(hit):
        p = hit.provenance
        return (
            hit.rank,
            hit.chunk_id,
            p.source_url,
            p.source_version,
            dict(p.locator),
            p.heading_path,
            p.source_modified_at,
            p.collected_at,
            hit.body,
        )

    value = {f"kw:{q}": [row(h) for h in store.search_keyword(q, 20).hits] for q in QUERIES}
    value["vec"] = [row(h) for h in store.search_vector(vec(3), 20).hits]
    return value


def _without(snapshot, urls):
    """내린 문서를 빼고 남은 결과의 순위를 다시 매긴다(순서는 그대로)."""
    return {
        k: [(i, *r[1:]) for i, r in enumerate((r for r in rows if r[2] not in urls), start=1)]
        for k, rows in snapshot.items()
    }


def _chunks(db_url, version):
    with psycopg.connect(db_url) as conn:
        return conn.execute(
            "SELECT id, artifact_id, ordinal, body, source_version FROM qk.chunk WHERE index_version=%s ORDER BY id",
            (version,),
        ).fetchall()


@pytest.fixture
def active_v1(sync_store, store):
    first = harness(DOCS, store=sync_store, cache_store=store)
    run_sync(first.targets, first.deps, SyncOptions())
    v1 = current_spec(first.deps).id
    sync_store.current_version = v1
    assert activate_first_index(sync_store, v1).failed_conditions == ()
    v2 = current_spec(harness(DOCS, store=sync_store, cache_store=store, chunking=NEW_CHUNKING).deps).id
    sync_store.current_version = v2
    return v1, v2


def _url(name):
    return f"https://fake.invalid/view/{name}"


def test_reindex_keeps_active_results_and_provenance(db_url, sync_store, store, active_v1, monkeypatch):
    v1, v2 = active_v1
    before = _snapshot(store)
    v1_rows = _chunks(db_url, v1)
    with psycopg.connect(db_url, autocommit=True) as conn:
        # H는 이미 일반 내림, G는 보안 내림 뒤 본문 삭제 대기다(둘 다 원본에는 다시 나온다).
        conn.execute("UPDATE qk.artifact SET status='deleted', takedown_reason='source_missing' WHERE source_id='H'")
        conn.execute(
            "UPDATE qk.artifact SET status='deleted', takedown_reason='security_secret', purge_pending=ARRAY[%s],"
            " purge_reason='security_secret' WHERE source_id='G'",
            (v1,),
        )
    hidden = _without(before, {_url("H"), _url("G")})
    docs = {k: v for k, v in DOCS.items() if k != "J"}  # J는 원본에서 사라짐
    docs["B"] = "# Synthetic B\n\nText for B, changed at the source.\n"  # 원본에서 바뀐 문서
    docs["I"] = f"# Synthetic I\n\nText for I {SYNTHETIC['github-classic']}\n"  # 비밀값
    preview_h = harness(docs, store=sync_store, cache_store=store, chunking=NEW_CHUNKING)
    _text_for(preview_h, monkeypatch, "F")
    spec = current_spec(preview_h.deps)
    plans = plan_all(preview_h.targets, preview_h.deps, spec, sync_store.index_state(), CONFIRMED)
    value, runnable = reindex_preview(
        plans,
        preview_h.deps.embedder,
        spec,
        sync_store.index_state(),
        candidate_status=None,
        coverage=None,
        options=CONFIRMED,
    )
    assert runnable and value["hidden_held"] == 2

    h = harness(docs, store=sync_store, cache_store=store, chunking=NEW_CHUNKING)
    _text_for(h, monkeypatch, "F")
    result = run_sync(h.targets, h.deps, CONFIRMED)
    assert result.status == "succeeded", (
        result.sources[0]["holds"],
        result.sources[0]["counts"],
        result.sources[0]["takedown_ratio"],
    )
    assert sum(len(call) for call in h.provider.calls) == value["embedding"]["to_embed"]
    after = _snapshot(store)
    assert after == _without(hidden, {_url("J"), _url("I")})
    # 활성 버전 청크는 만들어지거나 바뀌지 않았다(보안 내림 문서 I·대기 문서 G의 본문 삭제만 지금 규칙대로).
    untouched = [r for r in v1_rows if r[1] not in _artifact_ids(db_url, ("I", "G"))]
    assert [r for r in _chunks(db_url, v1) if r[1] not in _artifact_ids(db_url, ("I", "G"))] == untouched
    with psycopg.connect(db_url) as conn:
        states = dict(
            conn.execute("SELECT source_id, processed_outcome FROM qk.artifact WHERE processed_index_version=%s", (v2,))
        )
        held = conn.execute(
            "SELECT doc_display, action FROM qk.sync_document_result WHERE run_id=%s AND failure='reindex_hidden'",
            (result.run_id,),
        ).fetchall()
        g_status = conn.execute("SELECT status FROM qk.artifact WHERE source_id='G'").fetchone()[0]
    assert states["F"] == "not_target" and g_status == "deleted"
    # G는 확인 옵션으로 대기 본문을 지운다(지금 보안 규칙). 처리(되살리기)는 하지 않는다.
    assert sorted(held) == [("G", "HOLD"), ("G", "PURGE"), ("H", "HOLD")], held
    assert {"G", "H", "I", "J"}.isdisjoint(states)
    assert any(r[2] == _url("F") for r in after["kw:Synthetic"])  # 대상 아님 문서는 V1에서 계속 검색


def _artifact_ids(db_url, names):
    with psycopg.connect(db_url) as conn:
        return {r[0] for r in conn.execute("SELECT id FROM qk.artifact WHERE source_id = ANY(%s)", (list(names),))}


def _text_for(h, monkeypatch, name):
    adapter = h.targets[0].adapter
    original = type(adapter).fetch_content

    def fetched(self, session, config, item):
        content = original(self, session, config, item)
        return replace(content, content_format=ContentFormat.TEXT) if item.source_id == name else content

    monkeypatch.setattr(type(adapter), "fetch_content", fetched)


def test_second_reindex_and_resume_make_no_repeated_embedding(sync_store, store, active_v1):
    v1, v2 = active_v1
    docs = {k: f"# Synthetic {k}\n\nFresh text for {k}.\n" for k in DOCS}  # 모든 문서가 새 임베딩을 요구한다
    failing = FakeEmbeddingProvider(fail_calls={4: ProviderFailure(ProviderFailureKind.PROVIDER_QUOTA)})
    first = harness(docs, store=sync_store, cache_store=store, chunking=NEW_CHUNKING, provider=failing)
    result = run_sync(first.targets, first.deps, REINDEX)
    assert result.status != "succeeded"
    embedded_first = {t for call in failing.calls for t in call}
    resume = harness(docs, store=sync_store, cache_store=store, chunking=NEW_CHUNKING)
    result = run_sync(resume.targets, resume.deps, REINDEX)
    assert result.status == "succeeded"
    resumed = [t for call in resume.provider.calls for t in call]
    assert resumed and not (set(resumed) & embedded_first - {t for call in failing.calls[3:4] for t in call})
    again = harness(docs, store=sync_store, cache_store=store, chunking=NEW_CHUNKING)
    result = run_sync(again.targets, again.deps, REINDEX)
    assert result.status == "succeeded" and again.provider.calls == []
    assert result.sources[0]["counts"] == {"UNCHANGED": len(DOCS)}
