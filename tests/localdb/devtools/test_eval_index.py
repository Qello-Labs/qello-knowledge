"""평가용 색인 준비(QK-RET-001 spec FR-029, SC-009, research R-09, tasks T043).

가짜 자료원(`adapters/fake.py` + 재생 전송)과 가짜 임베딩 제공자를 주입한다. 네트워크와 Workers AI 호출이 없다.
시험 전용 커밋 SHA를 써서 사람 단계 H02의 데이터베이스 이름과 겹치지 않게 한다.
끝나면 이 시험이 만든 `qk_eval_*` 데이터베이스를 지운다.
"""

from __future__ import annotations

import hashlib
import io
import json
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest

from qello_knowledge.adapters.postgres.connection import with_database
from qello_knowledge.adapters.postgres.migrate import apply_migrations, load_migrations
from qello_knowledge.adapters.postgres.store import PostgresStore
from qello_knowledge.devtools.eval_index import PREPARING_SUFFIX, eval_db_name, prepare
from qello_knowledge.domain.chunking import ChunkingSettings
from qello_knowledge.domain.keyword_rules import INDEX_BASELINE, INDEX_IDSPLIT, index_rule_for
from qello_knowledge.embedding.fake import FakeEmbeddingProvider
from qello_knowledge.indexer.sync_cli import build_runtime
from qello_knowledge.sync.run import SyncOptions, run_sync
from tests.conftest import _local_db_reachable, local_db_port
from tests.localdb.store.builders import admin_url, create_database, drop_database
from tests.unit.security.helpers import fake_config, team_policy
from tests.unit.sync.helpers import harness

pytestmark = pytest.mark.localdb

SHA = "0" * 39 + "1"  # 시험 전용 커밋
DOCS = {"A": "# 결제\n\n`retryPayment` 함수가 재시도한다.\n", "B": "# 배포\n\n금요일에는 배포하지 않는다.\n"}
REPO_CONFIG = (Path("config/sources.toml"), Path("config/source_reviews"))


def _settings():
    from qello_knowledge.config.loader import load
    from qello_knowledge.config.registry import Entrypoint

    return load(Entrypoint.INDEX, environ={}, env_file=None)  # 예산 기본값만 쓴다


def _digest(path: Path) -> str:
    files = sorted(p for p in ([path] if path.is_file() else path.rglob("*")) if p.is_file())
    return hashlib.sha256(b"".join(p.read_bytes() for p in files)).hexdigest()


def _targets_factory(docs=DOCS):
    def make(configs, settings, clock):
        return list(harness(docs, config=fake_config(name="dnd-backend-docs")).targets)

    return make


class CountingProvider(FakeEmbeddingProvider):
    instances: list[CountingProvider] = []

    def __init__(self) -> None:
        super().__init__()
        CountingProvider.instances.append(self)


def _provider_factory(source, settings):
    return CountingProvider()


def _drop_eval_databases() -> None:
    with psycopg.connect(admin_url(), autocommit=True) as conn:
        names = [r[0] for r in conn.execute("SELECT datname FROM pg_database WHERE datname LIKE 'qk_eval_%%'")]
        for name in names:
            if SHA[:12] in name:
                conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


@pytest.fixture
def origin() -> Iterator[str]:
    """임베딩 캐시 원본 데이터베이스. 기준선 규칙으로 같은 가짜 문서를 색인해 둔다."""
    if not _local_db_reachable(local_db_port()):
        pytest.skip("로컬 DB가 없다")
    name = create_database()
    url = with_database(admin_url(), name)
    with psycopg.connect(url, autocommit=True) as conn:
        assert apply_migrations(conn, load_migrations(), is_local=True, out=io.StringIO()) == 0
    runtime = build_runtime(
        settings=_settings(),
        configs=(),
        policy=team_policy(),
        source={"DATABASE_URL": url},
        targets_factory=_targets_factory(),
        provider_factory=_provider_factory,
    )
    try:
        assert run_sync(runtime.targets, runtime.deps, SyncOptions()).exit_code == 0
    finally:
        runtime.close()
    CountingProvider.instances.clear()
    _drop_eval_databases()
    try:
        yield url
    finally:
        _drop_eval_databases()
        drop_database(name)


def _prepare(origin: str, rule: str = INDEX_IDSPLIT, **kwargs) -> tuple[int, dict]:
    out = io.StringIO()
    code = prepare(
        rule=rule,
        commit=kwargs.pop("commit", SHA),
        source_env={"QK_EVAL_ORIGIN_URL": origin},
        from_url_env="QK_EVAL_ORIGIN_URL",
        settings=_settings(),
        sources_path=REPO_CONFIG[0],
        reviews_dir=REPO_CONFIG[1],
        policy=team_policy(),
        targets_factory=kwargs.pop("targets_factory", _targets_factory()),
        provider_factory=_provider_factory,
        out=out,
        **kwargs,
    )
    text = out.getvalue()
    return code, (json.loads(text) if text.strip().startswith("{") else {"text": text})


def _databases() -> set[str]:
    with psycopg.connect(admin_url(), autocommit=True) as conn:
        return {r[0] for r in conn.execute("SELECT datname FROM pg_database WHERE datname LIKE 'qk_eval_%%'")}


def test_prepares_idsplit_database_from_cache_without_embedding(origin: str) -> None:
    before_repo = [_digest(p) for p in REPO_CONFIG]
    with psycopg.connect(origin, autocommit=True) as conn:
        origin_rows = conn.execute("SELECT count(*), max(id) FROM qk.embedding").fetchone()
    code, data = _prepare(origin)
    assert code == 0, data
    name = eval_db_name(INDEX_IDSPLIT, SHA)
    assert data["database"] == name and data["rule"] == INDEX_IDSPLIT and data["commit"] == SHA
    assert data["copied_vectors"] == origin_rows[0] and data["embedding_calls"] == 0 and data["neurons"] == 0
    assert all(not p.calls for p in CountingProvider.instances)
    assert name in _databases() and name + PREPARING_SUFFIX not in _databases()
    with PostgresStore(with_database(admin_url(), name)) as store:
        result = store.search_keyword_terms(("payment",), 20)
        assert index_rule_for(result.index_version) == INDEX_IDSPLIT == index_rule_for(data["index_version"])
        assert [h.hit.body for h in result.hits]  # 식별자 분해로 `retryPayment`를 찾는다
    with psycopg.connect(origin, autocommit=True) as conn:
        assert conn.execute("SELECT count(*), max(id) FROM qk.embedding").fetchone() == origin_rows  # 원본 쓰기 없음
    assert [_digest(p) for p in REPO_CONFIG] == before_repo  # 저장소의 설정·검토 파일 그대로


def test_baseline_database_uses_baseline_version(origin: str) -> None:
    code, data = _prepare(origin, rule=INDEX_BASELINE)
    assert code == 0, data
    assert data["index_version"] == "iv-4c0bc4fcc642"


def test_existing_final_database_stops_with_5(origin: str) -> None:
    assert _prepare(origin)[0] == 0
    assert _prepare(origin)[0] == 5


def test_leftover_preparing_database_is_recreated(origin: str) -> None:
    leftover = eval_db_name(INDEX_IDSPLIT, SHA) + PREPARING_SUFFIX
    with psycopg.connect(admin_url(), autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{leftover}"')
    code, _ = _prepare(origin)
    assert code == 0 and leftover not in _databases()


def test_uncached_embedding_needs_allow_embed(origin: str) -> None:
    changed = _targets_factory({**DOCS, "C": "# 새 문서\n\n캐시에 없는 내용이다.\n"})
    code, data = _prepare(origin, targets_factory=changed)
    assert code == 4 and data["estimated_neurons"] > 0
    assert all(not p.calls for p in CountingProvider.instances)
    code, data = _prepare(origin, targets_factory=changed, allow_embed=True)
    assert code == 0 and data["embedding_calls"] >= 1


@pytest.mark.parametrize("commit", ["abc1234", "main", "G" * 40, "0" * 41])
def test_commit_must_be_full_sha(origin: str, commit: str) -> None:
    assert _prepare(origin, commit=commit)[0] == 2


def test_only_preparing_names_are_dropped(origin: str) -> None:
    other = "qk_eval_keepme_" + SHA[:12]
    with psycopg.connect(admin_url(), autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{other}"')
    try:
        assert _prepare(origin)[0] == 0
        assert other in _databases()
    finally:
        with psycopg.connect(admin_url(), autocommit=True) as conn:
            conn.execute(f'DROP DATABASE IF EXISTS "{other}" WITH (FORCE)')


def test_unused_chunking_settings_default_is_baseline() -> None:
    assert ChunkingSettings().keyword_text_rule == INDEX_BASELINE
