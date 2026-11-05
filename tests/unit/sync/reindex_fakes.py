"""재색인 시험 도우미(QK-STO-002 tasks T015). 기존 `fake_store.py`는 고치지 않고 상속한다."""

from types import SimpleNamespace

from qello_knowledge.domain.chunking import ChunkingSettings
from qello_knowledge.ports.index_versions import Coverage
from qello_knowledge.sync.run import SyncOptions, current_spec, run_sync
from tests.unit.sync.fake_store import MemorySyncStore
from tests.unit.sync.helpers import harness

NEW_CHUNKING = ChunkingSettings(target_tokens=400)
DOCS = {name: f"# Synthetic {name}\n\nText for {name}.\n" for name in "ABCDEFGHIJ"}


class _FakeVersions:
    def __init__(self, store):
        self.store = store
        self.closed = False

    def coverage(self, version):
        active = next((v for v, s in self.store.indexes.items() if s == "active"), None)
        visible = [
            r
            for (_, i), r in self.store.documents.items()
            if r.status == "active" and (r.artifact_id, active) in self.store.chunks
        ]
        covered = sum(1 for r in visible if r.processed_index_version == version)
        return Coverage(version, len(visible), covered, len(visible) - covered)

    def versions(self):
        return tuple(SimpleNamespace(id=v, status=s) for v, s in sorted(self.store.indexes.items()))

    def close(self):
        self.closed = True


class ReindexMemoryStore(MemorySyncStore):
    def __init__(self):
        super().__init__()
        self.transitions = []
        self.run_kinds = {}

    def begin_run(self, run, source_names):
        super().begin_run(run, source_names)
        self.run_kinds[run.run_id] = run.kind

    def prepare_candidate(self, spec, *, target):
        self._write("prepare_candidate")
        status = self.indexes.get(spec.id)
        if status is None:
            self.indexes[spec.id] = "ready"
        elif status == "archived":
            self.indexes[spec.id] = "ready"
            self.transitions.append(("reuse", spec.id, target))
        return spec.id

    def index_versions(self):
        return _FakeVersions(self)


def mismatched(docs=None):
    """V1으로 색인하고 활성으로 둔 뒤 청킹 설정을 바꾼 하네스. (저장소, 새 하네스, V1, V2)."""
    store = ReindexMemoryStore()
    first = harness(docs or DOCS, store=store)
    run_sync(first.targets, first.deps, SyncOptions())
    v1 = current_spec(first.deps).id
    store.indexes[v1] = "active"
    second = harness(docs or DOCS, store=store, chunking=NEW_CHUNKING)
    v2 = current_spec(second.deps).id
    assert v1 != v2
    return SimpleNamespace(store=store, h=second, v1=v1, v2=v2)
