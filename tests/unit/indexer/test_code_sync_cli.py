"""코드 청킹 설정의 CLI 연결(QK-CHK-001 contracts 4절, plan 재검토 N3, tasks T028). 외부 호출과 DB 연결이 없다."""

from __future__ import annotations

import json

import pytest

from qello_knowledge.config.loader import load
from qello_knowledge.config.registry import Entrypoint
from qello_knowledge.domain.chunking import ChunkingSettings, CodeChunkingSettings
from qello_knowledge.domain.source_config import SourceConfig, SourceScope
from qello_knowledge.indexer.cli import main
from qello_knowledge.indexer.sync_cli import build_runtime, current_index_version
from qello_knowledge.security.policy import SecurityPolicy
from qello_knowledge.sync.plan import SyncTarget

SOURCE = {"DATABASE_URL": "postgresql://placeholder@127.0.0.1/db"}  # 연결하지 않는다(저장소는 게으르게 연결)


def _settings(**extra):
    return load(Entrypoint.INDEX, environ={**SOURCE, **extra}, env_file=None)


def _runtime(settings, **kwargs):
    from qello_knowledge.embedding.fake import FakeEmbeddingProvider

    config = SourceConfig(name="docs", kind="fake", enabled=True, scope=SourceScope(include=("**/*.java",)))
    return build_runtime(
        settings=settings,
        configs=(config,),
        policy=SecurityPolicy(),
        source=SOURCE,
        targets_factory=lambda configs, settings, clock: [SyncTarget(c.name, c.kind, config=c) for c in configs],
        provider_factory=lambda source, settings: FakeEmbeddingProvider(),
        **kwargs,
    )


def test_current_index_version_off_and_on():
    assert current_index_version() == "iv-4c0bc4fcc642"
    assert current_index_version(code=CodeChunkingSettings()) != "iv-4c0bc4fcc642"


@pytest.mark.parametrize(
    ("value", "kwargs", "expected"),
    [
        ("on", {}, CodeChunkingSettings()),
        ("off", {}, None),
        ("on", {"chunking": ChunkingSettings()}, None),  # 평가용 색인 준비는 청커 설정을 명시한다
        ("off", {"code": CodeChunkingSettings(target_tokens=100)}, CodeChunkingSettings(target_tokens=100)),
    ],
)
def test_build_runtime_code_setting(value, kwargs, expected):
    runtime = _runtime(_settings(QK_CODE_CHUNKING=value), **kwargs)
    try:
        assert runtime.deps.code_chunking == expected
        assert runtime.deps.store.current_version == current_index_version(code=expected)
    finally:
        runtime.close()


class StatusStore:
    def __init__(self, seen):
        self.seen = seen

    def index_state(self):
        from types import SimpleNamespace

        return SimpleNamespace(active="iv-4c0bc4fcc642", ready=())

    def close(self):
        pass


def test_index_status_reports_on_version(monkeypatch, capsys):
    seen = []
    monkeypatch.setenv("QK_CODE_CHUNKING", "on")

    def factory(source, version):
        seen.append(version)
        return StatusStore(seen)

    assert main(["index", "status", "--json", "--env-file", "/dev/null"], sync_store_factory=factory) == 0
    output = json.loads(capsys.readouterr().out)
    on = current_index_version(code=CodeChunkingSettings())
    assert seen == [on] and output["current"] == on and output["matches"] is False


def test_index_status_rejects_invalid_switch(monkeypatch, capsys):
    monkeypatch.setenv("QK_CODE_CHUNKING", "yes")
    called = []
    code = main(
        ["index", "status", "--json", "--env-file", "/dev/null"],
        sync_store_factory=lambda source, version: called.append(version),
    )
    assert code == 1 and called == []
    report = json.loads(capsys.readouterr().out)
    assert {"name": "QK_CODE_CHUNKING", "status": "INVALID"} in report["items"]
