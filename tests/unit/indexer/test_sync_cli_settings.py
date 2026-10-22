"""동기화 조립의 청커 설정·주입 인자(QK-RET-001 research R-09, tasks T041·T042). 외부 호출과 DB 연결이 없다."""

from __future__ import annotations

import pytest

from qello_knowledge.chunking.version import chunking_version
from qello_knowledge.domain.chunking import ChunkingSettings
from qello_knowledge.domain.keyword_rules import INDEX_IDSPLIT
from qello_knowledge.domain.source_config import SourceConfig, SourceScope
from qello_knowledge.indexer.sync_cli import build_runtime, current_index_version
from qello_knowledge.security.policy import SecurityPolicy
from qello_knowledge.sync.identity import IdentityError
from qello_knowledge.sync.keys import index_version_id
from qello_knowledge.sync.plan import SyncTarget

SOURCE = {"DATABASE_URL": "postgresql://placeholder@127.0.0.1/db"}  # 연결하지 않는다(저장소는 게으르게 연결)


def _config(kind: str = "fake") -> SourceConfig:
    return SourceConfig(name="docs", kind=kind, enabled=True, scope=SourceScope(include=("**/*.md",)))


def _settings():
    from qello_knowledge.config.loader import load
    from qello_knowledge.config.registry import Entrypoint

    return load(Entrypoint.INDEX, environ=SOURCE, env_file=None)


def test_default_runtime_uses_baseline_chunking_and_rejects_other_kinds() -> None:
    with pytest.raises(IdentityError):
        build_runtime(settings=_settings(), configs=(_config(),), policy=SecurityPolicy(), source=SOURCE)


def test_injected_targets_provider_and_chunking() -> None:
    made = []

    def targets(configs, settings, clock):
        made.append(tuple(c.name for c in configs))
        return [SyncTarget(c.name, c.kind, config=c) for c in configs if c.enabled]

    def provider(source, settings):
        from qello_knowledge.embedding.fake import FakeEmbeddingProvider

        return FakeEmbeddingProvider()

    chunking = ChunkingSettings(keyword_text_rule=INDEX_IDSPLIT)
    runtime = build_runtime(
        settings=_settings(),
        configs=(_config(),),
        policy=SecurityPolicy(),
        source=SOURCE,
        chunking=chunking,
        targets_factory=targets,
        provider_factory=provider,
    )
    try:
        assert made == [("docs",)]
        assert runtime.deps.chunking_settings == chunking
        expected = index_version_id("@cf/baai/bge-m3", 1024, chunking_version(chunking))
        assert runtime.deps.store.current_version == expected
    finally:
        runtime.close()


def test_current_index_version_follows_settings() -> None:
    assert current_index_version() == "iv-4c0bc4fcc642"
    assert current_index_version(ChunkingSettings(keyword_text_rule=INDEX_IDSPLIT)) == "iv-8b7e93b22051"
