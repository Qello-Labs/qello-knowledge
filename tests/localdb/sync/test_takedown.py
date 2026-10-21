import psycopg
import pytest

from qello_knowledge.domain.source_config import SourceScope
from qello_knowledge.sync.run import SyncOptions, run_sync
from tests.unit.security.helpers import fake_config
from tests.unit.sync.helpers import DEFAULT_DOCS, harness
from tests.unit.synthetic_secrets import SYNTHETIC

pytestmark = pytest.mark.localdb


def run(sync_store, store, docs=None, *, confirm=False, **kwargs):
    h = harness(docs, store=sync_store, cache_store=store, **kwargs)
    return h, run_sync(h.targets, h.deps, SyncOptions(confirm_takedown=confirm))


def activate(db_url):
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute("UPDATE qk.index_version SET status='active'")


def test_missing_document_is_hidden_but_body_kept(sync_store, store, db_url):
    run(sync_store, store)
    activate(db_url)
    old = next(
        hit for hit in store.search_keyword("Synthetic D", 50).hits if hit.provenance.locator["path"] == "docs/D.md"
    )
    run(sync_store, store, {k: v for k, v in DEFAULT_DOCS.items() if k != "D"})
    assert store.chunk_neighbors(old.chunk_id, 1, 1) is None
    assert all(hit.provenance.locator["path"] != "docs/D.md" for hit in store.search_keyword("Synthetic", 50).hits)
    assert sync_store.load_documents("fake")["D"].takedown_reason == "source_missing"
    with psycopg.connect(db_url) as conn:
        assert conn.execute("SELECT count(*) FROM qk.chunk WHERE id=%s", (old.chunk_id,)).fetchone() == (1,)


@pytest.mark.parametrize("mode", ["unknown", "secret", "excluded"])
def test_security_takedown_removes_all_versions_body_and_search_text(sync_store, store, db_url, mode):
    run(sync_store, store)
    activate(db_url)
    kwargs = {}
    docs = DEFAULT_DOCS
    if mode == "unknown":
        kwargs["access"] = {"D": None}
    elif mode == "secret":
        docs = {**DEFAULT_DOCS, "D": SYNTHETIC["github-classic"]}
    else:
        kwargs["config"] = fake_config(scope=SourceScope(("**/*.md",), ("DOCS/d.md",)))
    _, result = run(sync_store, store, docs, **kwargs)
    assert result.status == "succeeded"
    row = sync_store.load_documents("fake")["D"]
    assert row.status == "deleted" and row.purge_pending == ()
    with psycopg.connect(db_url) as conn:
        assert conn.execute("SELECT count(*) FROM qk.chunk WHERE artifact_id=%s", (row.artifact_id,)).fetchone() == (0,)
    assert all(hit.provenance.locator["path"] != "docs/D.md" for hit in store.search_keyword("Synthetic", 50).hits)


def test_ratio_hides_security_now_and_confirmation_purges_even_missing_documents(sync_store, store, db_url):
    run(sync_store, store)
    activate(db_url)
    _, result = run(sync_store, store, access={k: None for k in "DE"})
    assert result.status == "stopped"
    for key in "DE":
        row = sync_store.load_documents("fake")[key]
        assert row.status == "deleted" and row.purge_pending and row.purge_reason == "security_access"
    _, result = run(sync_store, store, {k: v for k, v in DEFAULT_DOCS.items() if k not in "DE"}, confirm=True)
    assert result.status == "succeeded"
    for key in "DE":
        row = sync_store.load_documents("fake")[key]
        assert row.purge_pending == () and row.purge_reason is None
        with psycopg.connect(db_url) as conn:
            assert conn.execute(
                "SELECT count(*) FROM qk.chunk WHERE artifact_id=%s", (row.artifact_id,)
            ).fetchone() == (0,)


def test_empty_security_hold_does_not_create_phantom_pending_versions(sync_store, store):
    run(sync_store, store, {"A": ""})
    _, result = run(sync_store, store, {"A": ""}, access={"A": None})
    row = sync_store.load_documents("fake")["A"]
    assert result.status == "stopped"
    assert row.status == "deleted" and row.purge_pending == () and row.purge_reason is None


def test_reinstatement_keeps_other_version_pending_until_confirmation(sync_store, store, db_url):
    run(sync_store, store)
    activate(db_url)
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO qk.index_version(id,embedding_model,dimension,chunking_version,"
            "metadata_schema_version,status) "
            "SELECT 'iv-old',embedding_model,dimension,chunking_version,metadata_schema_version,'ready' "
            "FROM qk.index_version WHERE status='active'"
        )
        conn.execute(
            "INSERT INTO qk.chunk(artifact_id,index_version,source_version,locator,heading_path,ordinal,"
            "body,search_text,chunking_version,embedding_id) "
            "SELECT artifact_id,'iv-old',source_version,locator,heading_path,ordinal,body,search_text,"
            "chunking_version,embedding_id FROM qk.chunk"
        )
    run(sync_store, store, access={key: None for key in "DE"})
    run(sync_store, store, access={"E": None})
    reinstated = sync_store.load_documents("fake")["D"]
    assert reinstated.status == "active" and reinstated.purge_pending == ("iv-old",)
    _, result = run(sync_store, store, confirm=True, access={"E": None})
    row = sync_store.load_documents("fake")["D"]
    assert row.status == "active" and row.purge_pending == ()
    with psycopg.connect(db_url) as conn:
        actions = conn.execute(
            "SELECT action FROM qk.sync_document_result WHERE run_id=%s AND artifact_id=%s ORDER BY action",
            (result.run_id, row.artifact_id),
        ).fetchall()
        assert actions == [("PURGE",), ("UNCHANGED",)]


def test_version_mismatch_blocks_processing_and_general_takedown_but_not_security(sync_store, store, db_url):
    run(sync_store, store)
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO qk.index_version(id,embedding_model,dimension,chunking_version,"
            "metadata_schema_version,status) "
            "SELECT 'iv-other',embedding_model,dimension,chunking_version,metadata_schema_version,'active' "
            "FROM qk.index_version LIMIT 1"
        )
    docs = {k: v for k, v in DEFAULT_DOCS.items() if k != "E"}
    h, result = run(sync_store, store, {**docs, "A": "# Changed A", "D": SYNTHETIC["github-classic"]})
    assert result.status == "stopped" and h.provider.calls == []
    assert sync_store.load_documents("fake")["E"].status == "active"
    assert sync_store.load_documents("fake")["D"].status == "deleted"
    assert sync_store.load_documents("fake")["A"].source_version == "v1"


def test_disabled_source_uses_general_takedown_only(sync_store, store, db_url):
    from qello_knowledge.sync.plan import SyncTarget

    h, _ = run(sync_store, store)
    activate(db_url)
    result = run_sync((SyncTarget("docs", "fake", mode="TAKEDOWN_ONLY"),), h.deps, SyncOptions(confirm_takedown=True))
    assert result.status == "succeeded"
    assert all(r.takedown_reason == "source_disabled" for r in sync_store.load_documents("fake").values())
    assert store.search_keyword("Synthetic", 50).hits == ()
    with psycopg.connect(db_url) as conn:
        assert conn.execute("SELECT count(*) FROM qk.chunk").fetchone() == (5,)


@pytest.mark.parametrize("mode", ["budget", "private", "stopped"])
def test_security_hide_survives_budget_private_transition_and_collection_stop(
    sync_store, store, db_url, mode, monkeypatch
):
    from qello_knowledge.domain.embedding import BudgetSettings
    from qello_knowledge.domain.source import RunStopped, StopInfo, StopReason

    run(sync_store, store)
    activate(db_url)
    h = harness(
        {**DEFAULT_DOCS, "A": "# Changed A", "B": SYNTHETIC["github-classic"]},
        store=sync_store,
        cache_store=store,
        settings=BudgetSettings(index_budget=0) if mode == "budget" else None,
        access={key: None for key in "CDE"} if mode == "private" else None,
    )
    if mode == "stopped":
        original = h.targets[0].adapter.fetch_content

        def fetched(session, config, item):
            if item.source_id == "C":
                raise RunStopped(StopInfo(StopReason.REQUEST_BUDGET))
            return original(session, config, item)

        monkeypatch.setattr(h.targets[0].adapter, "fetch_content", fetched)
    result = run_sync(h.targets, h.deps, SyncOptions())
    assert result.status == "stopped"
    assert sync_store.load_documents("fake")["B"].status == "deleted"
    assert all(hit.provenance.locator["path"] != "docs/B.md" for hit in store.search_keyword("Synthetic", 50).hits)


def test_purge_then_process_records_both_operations(sync_store, store, db_url):
    run(sync_store, store)
    run(sync_store, store, access={key: None for key in "DE"})
    _, result = run(sync_store, store, confirm=True)
    row = sync_store.load_documents("fake")["D"]
    assert row.status == "active" and row.purge_pending == ()
    with psycopg.connect(db_url) as conn:
        assert conn.execute(
            "SELECT action FROM qk.sync_document_result WHERE run_id=%s AND artifact_id=%s ORDER BY action",
            (result.run_id, row.artifact_id),
        ).fetchall() == [("PROCESS",), ("PURGE",)]


@pytest.mark.parametrize("mode", ["secret", "excluded", "path", "unknown"])
def test_confirmed_security_takedown_is_settled_on_repeated_runs(sync_store, store, db_url, mode):
    run(sync_store, store)
    docs = DEFAULT_DOCS
    kwargs = {}
    if mode == "secret":
        docs = {**docs, **{key: SYNTHETIC["github-classic"] for key in "DE"}}
    elif mode == "excluded":
        kwargs["config"] = fake_config(scope=SourceScope(("**/*.md",), ("docs/[DE].md",)))
    elif mode == "path":
        kwargs["locations"] = {key: f"secrets/{key}.md" for key in "DE"}
    else:
        kwargs["access"] = {key: None for key in "DE"}
    for confirm, expected in [(False, "stopped"), (True, "succeeded"), (False, "succeeded"), (False, "succeeded")]:
        with psycopg.connect(db_url) as conn:
            before = conn.execute("SELECT count(*) FROM qk.sync_document_result").fetchone()[0]
        _, result = run(sync_store, store, docs, confirm=confirm, **kwargs)
        assert result.status == expected
        if not confirm and expected == "succeeded":
            assert result.sources[0]["takedown_ratio"]["purge"] == 0
            assert result.sources[0]["counts"] == {"UNCHANGED": 3}
            with psycopg.connect(db_url) as conn:
                assert conn.execute("SELECT count(*) FROM qk.sync_document_result").fetchone() == (before + 3,)
