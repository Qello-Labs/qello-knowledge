"""활성화·되돌리기·정리 로컬 DB 시험 공통 준비(QK-STO-002 tasks T041). 수집 대상 아님."""

from types import MappingProxyType, SimpleNamespace

import psycopg

from qello_knowledge.domain import keyword_rules
from qello_knowledge.indexer.index_cli import make_handler
from qello_knowledge.sync.activate import activate_first_index
from qello_knowledge.sync.run import SyncOptions, current_spec, run_sync
from tests.unit.indexer.index_fakes import verified, verifier
from tests.unit.sync.helpers import harness
from tests.unit.sync.reindex_fakes import DOCS, NEW_CHUNKING


def prepare(sync_store, store, monkeypatch, *, docs=DOCS, register_rule=True):
    """V1 활성, V2(새 청킹 설정) 재색인 성공, 현재 설정 버전 = V2."""
    first = harness(docs, store=sync_store, cache_store=store)
    run_sync(first.targets, first.deps, SyncOptions())
    v1 = current_spec(first.deps).id
    sync_store.current_version = v1
    assert activate_first_index(sync_store, v1).failed_conditions == ()
    second = harness(docs, store=sync_store, cache_store=store, chunking=NEW_CHUNKING)
    v2 = current_spec(second.deps).id
    sync_store.current_version = v2
    result = run_sync(second.targets, second.deps, SyncOptions(reindex=True))
    assert result.status == "succeeded", result.sources
    rules = {**keyword_rules.INDEX_KEYWORD_RULES, v1: keyword_rules.INDEX_BASELINE}
    if register_rule:
        rules[v2] = keyword_rules.INDEX_IDSPLIT
    monkeypatch.setattr(keyword_rules, "INDEX_KEYWORD_RULES", MappingProxyType(rules))
    return SimpleNamespace(v1=v1, v2=v2, run_id=result.run_id)


def activate(sync_store, version, *, confirm=True, gate=None):
    args = SimpleNamespace(index_command="activate", version=version, gate="gate.json", confirm=confirm)
    handler = make_handler(history_factory=lambda root: None, gate_verifier=gate or verifier())
    return handler(args, sync_store, sync_store.current_version, "local")


def rollback(sync_store, version, *, confirm=True, confirm_stale=False, reason="합성 되돌리기 사유"):
    args = SimpleNamespace(
        index_command="rollback", version=version, reason=reason, confirm=confirm, confirm_stale=confirm_stale
    )
    handler = make_handler(history_factory=lambda root: None, gate_verifier=verifier())
    return handler(args, sync_store, sync_store.current_version, "local")


def prune(sync_store, version, *, confirm=True, confirm_rollback_target=False):
    args = SimpleNamespace(
        index_command="prune", version=version, confirm=confirm, confirm_rollback_target=confirm_rollback_target
    )
    handler = make_handler(history_factory=lambda root: None, gate_verifier=verifier())
    return handler(args, sync_store, sync_store.current_version, "local")


def state(db_url):
    with psycopg.connect(db_url) as conn:
        statuses = dict(conn.execute("SELECT id, status FROM qk.index_version").fetchall())
        transitions = conn.execute("SELECT count(*) FROM qk.index_transition").fetchone()[0]
    return statuses, transitions


__all__ = ["DOCS", "NEW_CHUNKING", "activate", "prepare", "prune", "rollback", "state", "verified", "verifier"]
