"""Confluence 동기화 왕복(QK-ING-003 SC-002·SC-011·SC-013·SC-014). 재생 응답과 가짜 임베딩만 쓴다."""

from dataclasses import replace

import psycopg
import pytest

from qello_knowledge.sync.plan import SyncTarget
from qello_knowledge.sync.run import SyncOptions, current_spec, run_sync
from tests.unit.adapters import confluence_scenarios as cf
from tests.unit.sync.helpers import harness

pytestmark = pytest.mark.localdb

DOC_TYPES = {"10": "설계 문서"}


def _pages(*, edit=False, title="세 번째", restricted=False):
    restriction = "VIEW_RESTRICTED" if restricted else "OPEN"
    pages = cf.tree(
        ("10", "설계", "1", {"body": cf.doc(cf.paragraph("설계 안내"))}),
        ("11", "첫 번째", "10", {"body": cf.doc(cf.paragraph("첫 내용")), "restriction": restriction}),
        ("12", "두 번째", "10", {"body": cf.doc(cf.paragraph("고친 내용" if edit else "둘 내용"))}),
        ("13", title, "10", {"body": cf.doc(cf.paragraph("셋 내용"))}),
        ("20", "미분류", "1", {"body": cf.doc(cf.paragraph("미분류 내용"))}),
    )  # fmt: skip
    pages[0]["body"] = cf.doc(cf.paragraph("홈"))
    return pages


def _run(sync_store, store, pages=None, *, confluence_enabled=True, confirm=False, exclude_trees=(), scenario=None):
    h = harness(store=sync_store, cache_store=store)
    deps = replace(h.deps, confluence=True)
    targets = list(h.targets)
    if confluence_enabled:
        config = cf.config(doc_types=DOC_TYPES, exclude_trees=exclude_trees)
        adapter = cf.adapter()
        transport = (scenario or cf.Scenario(pages=pages or _pages())).transport()
        targets.append(
            SyncTarget(
                config.name, config.kind, config=config, adapter=adapter, session=cf.session(adapter, transport, config)
            )
        )
    result = run_sync(tuple(targets), deps, SyncOptions(confirm_takedown=confirm))
    return result, h, deps


def _rows(db_url):
    with psycopg.connect(db_url) as conn:
        return {
            source_id: (status, takedown)
            for source_id, status, takedown in conn.execute(
                "SELECT source_id, status, takedown_reason FROM qk.artifact WHERE source_kind='confluence_pages'"
            ).fetchall()
        }


def _chunk_ids(db_url, kind):
    with psycopg.connect(db_url) as conn:
        return dict(
            conn.execute(
                "SELECT a.source_id, array_agg(c.id ORDER BY c.ordinal) FROM qk.artifact a "
                "JOIN qk.chunk c ON a.id=c.artifact_id WHERE a.source_kind=%s GROUP BY a.source_id",
                (kind,),
            ).fetchall()
        )


def test_confluence_round_trip(db_url, sync_store, store, monkeypatch):
    result, _, deps = _run(sync_store, store)
    assert result.status == "succeeded"
    assert set(_rows(db_url)) == {"10", "11", "12", "13"}  # 홈·미분류는 색인하지 않는다
    with psycopg.connect(db_url) as conn:
        assert conn.execute("SELECT metadata_schema_version FROM qk.index_version").fetchone() == ("meta-v1+cf1",)
        locator = conn.execute(
            "SELECT c.locator FROM qk.chunk c JOIN qk.artifact a ON a.id=c.artifact_id WHERE a.source_id='12'"
        ).fetchone()[0]
    assert locator["confluence"] == {"page_id": "12", "doc_type": "설계 문서", "meeting": None}
    assert set(locator) == {"path", "lines", "confluence"}

    again, h, _ = _run(sync_store, store)
    assert again.status == "succeeded" and h.provider.calls == []

    before = _chunk_ids(db_url, "confluence_pages")
    edited, h, _ = _run(sync_store, store, _pages(edit=True, title="이름 바뀐 세 번째"))
    after = _chunk_ids(db_url, "confluence_pages")
    assert edited.status == "succeeded"
    assert after["12"] != before["12"] and after["13"] != before["13"]
    assert after["10"] == before["10"] and after["11"] == before["11"]

    _run(sync_store, store, _pages(edit=True, title="이름 바뀐 세 번째", restricted=True), confirm=True)
    assert _rows(db_url)["11"][0] == "deleted"

    # 변환 규칙 버전만 바꾸면 Confluence 문서만 다시 처리된다(SC-013).
    fake_before = _chunk_ids(db_url, "fake")
    monkeypatch.setattr("qello_knowledge.adapters.confluence.RULES_VERSION", "adf-md-v2-test")
    reprocessed, h, _ = _run(sync_store, store, _pages(edit=True, title="이름 바뀐 세 번째", restricted=True))
    assert reprocessed.status == "succeeded"
    assert _chunk_ids(db_url, "fake") == fake_before
    assert _chunk_ids(db_url, "confluence_pages") != after


def test_disabling_after_indexing_keeps_version_and_takes_pages_down(db_url, sync_store, store):
    _, _, deps = _run(sync_store, store)
    version = current_spec(deps).id
    held, _, _ = _run(sync_store, store, confluence_enabled=False)
    confluence = next(source for source in held.sources if source["source_name"] == "confluence-scrum")
    assert "INDEX_MISMATCH" not in str(confluence) and "TAKEDOWN_RATIO" in str(confluence)
    with psycopg.connect(db_url) as conn:
        assert {row[0] for row in conn.execute("SELECT id FROM qk.index_version").fetchall()} == {version}
    assert all(status == "active" for status, _ in _rows(db_url).values())  # 전체 내림은 비율 보류
    _run(sync_store, store, confluence_enabled=False, confirm=True)
    assert all(status == "deleted" and reason == "source_disabled" for status, reason in _rows(db_url).values())


def test_excluded_tree_and_gone_page_are_security_takedowns(db_url, sync_store, store):
    _run(sync_store, store)
    _run(sync_store, store, exclude_trees=("12",), confirm=True)
    rows = _rows(db_url)
    assert rows["12"] == ("deleted", "security_path")
    assert rows["11"][0] == rows["13"][0] == "active"
    pages = [page for page in _pages() if page["id"] != "13"]
    scenario = cf.Scenario(pages=pages).missing("13", status=404)
    _run(sync_store, store, scenario=scenario, exclude_trees=("12",), confirm=True)
    assert _rows(db_url)["13"] == ("deleted", "security_access")
    with psycopg.connect(db_url) as conn:
        left = conn.execute(
            "SELECT count(*) FROM qk.chunk c JOIN qk.artifact a ON a.id=c.artifact_id WHERE a.source_id IN ('12','13')"
        ).fetchone()
    assert left == (0,)
