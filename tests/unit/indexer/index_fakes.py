"""index 명령 시험 도우미(QK-STO-002 T040·T047·T051, 수집 대상 아님). 저장소와 git을 쓰지 않는다."""

from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace

from qello_knowledge.domain.sync import ActivationCheck
from qello_knowledge.gate.verify import VerifiedGate
from qello_knowledge.ports.index_versions import (
    ActivationState,
    Coverage,
    PruneResult,
    PruneState,
    RollbackState,
    RunRef,
    SourceRef,
    SwitchResult,
    VersionRow,
)
from qello_knowledge.ports.sync import IndexState

T = datetime(2026, 11, 5, tzinfo=UTC)
V1, V2 = "iv-active-1", "iv-ready-2"
BODY = "synthetic chunk body must not leak"
DB_URL = "postgres" + "ql://user:pw@db.invalid/x"


def row(vid, status, **kw):
    values = dict(
        id=vid,
        embedding_model="@cf/baai/bge-m3",
        dimension=1024,
        chunking_version="c",
        metadata_schema_version="meta-v1",
        status=status,
        created_at=T,
        activated_at=None,
        pruned_at=None,
        documents=5,
        chunks=6,
        chunks_without_vector=0,
        ever_active=status != "ready",
        last_reindex=RunRef("sync-r", "succeeded", T),
    )
    values.update(kw)
    return VersionRow(**values)


class FakeVersions:
    def __init__(self, *, activation=None, rollback=None, prune=None, switch=None):
        self.current_version = V2
        self.activation = activation or ActivationState(
            active=row(V1, "active"),
            target=row(V2, "ready"),
            current=V2,
            sync_running=False,
            coverage=Coverage(V2, 5, 5, 0),
            purge_pending=0,
            tokenizer="TokenBigramSplitSymbol",
            sources=(SourceRef("docs", "github_repo_files"), SourceRef("wiki", "confluence_pages")),
        )
        self.rollback = rollback or RollbackState(
            active=row(V2, "active"),
            target=row(V1, "archived"),
            current=V2,
            sync_running=False,
            purge_pending=0,
            missing_documents=1,
            provenance_mismatch=0,
        )
        self.prune_snapshot = prune or PruneState(row(V1, "archived"), V2, V2, None, 6, False)
        self.switch = switch
        self.calls = []
        self.closed = False

    def versions(self):
        return (row(V1, "active"), row(V2, "ready"))

    def coverage(self, version):
        return Coverage(version, 5, 3, 2)

    def mismatch_since(self, active, current):
        return T

    def rollback_target(self):
        return None

    def activation_state(self, version):
        return self.activation

    def rollback_state(self, version):
        return self.rollback

    def prune_state(self, version):
        return self.prune_snapshot

    def switch_active(self, version, *, check, kind, **kw):
        self.calls.append(("switch", version, kind, kw))
        if self.switch is not None:
            return self.switch
        state = self.activation if kind == "activation" else self.rollback
        failed = tuple(check(state))
        return SwitchResult(not failed, failed, 7 if not failed else None)

    def prune(self, version, *, check, **kw):
        self.calls.append(("prune", version))
        failed = tuple(check(self.prune_snapshot))
        return PruneResult(not failed, failed, 6 if not failed else 0, not failed)

    def close(self):
        self.closed = True


class FakeStore:
    def __init__(self, *, active=V1, ready=(V2,), versions=None, with_versions=True):
        self.state = IndexState(active, tuple(ready))
        self._versions = versions or FakeVersions()
        self.current_version = None
        if not with_versions:
            self.index_versions = None

    def load_sources(self):
        return {}

    def index_state(self):
        return self.state

    def index_versions(self):  # 생성자에서 None으로 덮으면 버전 저장소가 없는 대역이다
        return self._versions

    def activate(self, version):
        return ActivationCheck(version, 1, 1, 0, "succeeded", ())

    def close(self):
        pass


def verified(**kw):
    values = dict(
        gate_id="gate-x",
        sha256="a" * 64,
        verdict="pass",
        baseline=None,
        candidate_tokenizer="TokenBigramSplitSymbol",
        search={"query_rule": "kw-query-v1", "candidates": 20, "rrf_k": 60},
        covered_sources=("docs",),
        summary={"policy": {"id": "p", "version": 1}, "sets": [], "embedding_model": "@cf/baai/bge-m3"},
    )
    values.update(kw)
    return VerifiedGate(**values)


def verifier(result=None, failed=()):
    calls = []

    def verify(path, *, active, target, history, repo_root):
        calls.append((path, active, target))
        return (result if result is not None else verified()), tuple(failed)

    verify.calls = calls
    return verify


def with_store(store):
    def factory(source, version):
        store.current_version = version
        return store

    return factory


__all__ = [
    "BODY",
    "DB_URL",
    "FakeStore",
    "FakeVersions",
    "SimpleNamespace",
    "replace",
    "row",
    "verified",
    "verifier",
    "with_store",
]
