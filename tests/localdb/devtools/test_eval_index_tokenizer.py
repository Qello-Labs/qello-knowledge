"""후보 C 평가 대상 준비(QK-EVL-001 spec FR-023, SC-009, research R-12, tasks T037).

후보 A 데이터베이스를 템플릿으로 복제하고 키워드 색인 토크나이저만 바꾼다. 외부 호출과 문서 임베딩이 없다.
기존 `test_eval_index.py`의 `origin` 픽스처·`_prepare`·`SHA`를 가져온다(그 파일은 고치지 않는다).
"""

from __future__ import annotations

import io
import json

import psycopg
import pytest

from qello_knowledge.adapters.postgres.connection import with_database
from qello_knowledge.adapters.postgres.migrate import load_migrations
from qello_knowledge.adapters.postgres.store import PostgresStore
from qello_knowledge.devtools.eval_index import (
    PREPARING_SUFFIX,
    eval_db_name,
    eval_tokenizer_db_name,
    prepare_tokenizer,
)
from qello_knowledge.domain.keyword_rules import INDEX_BASELINE, INDEX_IDSPLIT
from tests.localdb.devtools.test_eval_index import SHA, CountingProvider, _databases, _prepare, origin  # noqa: F401
from tests.localdb.store.builders import admin_url

pytestmark = pytest.mark.localdb

ALPHA = "TokenBigramSplitSymbolAlpha"


def _tokenize(commit: str = SHA) -> tuple[int, dict]:
    out = io.StringIO()
    code = prepare_tokenizer(commit=commit, tokenizer=ALPHA, source_env={}, out=out)
    return code, json.loads(out.getvalue())


def _url(name: str) -> str:
    return with_database(admin_url(), name)


def _indexdef(url: str) -> str:
    with psycopg.connect(url, autocommit=True) as conn:
        return conn.execute("SELECT pg_get_indexdef('qk.chunk_search_text_pgroonga'::regclass)").fetchone()[0]


def _rows(url: str) -> list[tuple]:
    with psycopg.connect(url, autocommit=True) as conn:
        return conn.execute("SELECT id, artifact_id, ordinal, embedding_id FROM qk.chunk ORDER BY id").fetchall()


def _payment_hits(name: str) -> int:
    with PostgresStore(_url(name)) as store:
        return len(store.search_keyword_terms(("payment",), 20).hits)


def test_prepares_candidate_c_from_candidate_a(origin: str) -> None:  # noqa: F811
    assert _prepare(origin, rule=INDEX_BASELINE)[0] == 0
    assert _prepare(origin, rule=INDEX_IDSPLIT)[0] == 0
    a, b, c = eval_db_name(INDEX_BASELINE, SHA), eval_db_name(INDEX_IDSPLIT, SHA), eval_tokenizer_db_name(SHA)
    before = {name: _indexdef(_url(name)) for name in (a, b)} | {"origin": _indexdef(origin)}
    migrations = [(m.version, m.checksum) for m in load_migrations()]
    CountingProvider.instances.clear()
    code, data = _tokenize()
    assert code == 0, data
    assert data["base_database"] == a and data["database"] == c and data["tokenizer"] == ALPHA
    assert data["index_version"] == "iv-4c0bc4fcc642" and data["external_calls"] == 0
    assert CountingProvider.instances == []  # 제공자를 만들지 않는다
    assert c in _databases() and c + PREPARING_SUFFIX not in _databases()
    assert f"tokenizer={ALPHA}" in _indexdef(_url(c)).replace("'", "").replace(" ", "")
    assert _rows(_url(c)) == _rows(_url(a))  # 청크 ID·임베딩이 같다(벡터 결과가 같다)
    assert _payment_hits(a) == 0 and _payment_hits(c) > 0  # 같은 영문 일부 낱말을 C만 찾는다
    after = {name: _indexdef(_url(name)) for name in (a, b)} | {"origin": _indexdef(origin)}
    assert after == before and [(m.version, m.checksum) for m in load_migrations()] == migrations


def test_existing_final_database_stops_with_5(origin: str) -> None:  # noqa: F811
    assert _prepare(origin, rule=INDEX_BASELINE)[0] == 0
    assert _tokenize()[0] == 0
    code, data = _tokenize()
    assert code == 5 and data["error"] == "database_exists"


def test_missing_candidate_a_stops_with_6(origin: str) -> None:  # noqa: F811
    code, data = _tokenize(commit="0" * 39 + "2")
    assert code == 6 and data["error"] == "base_database_missing"


def test_leftover_preparing_database_is_recreated(origin: str) -> None:  # noqa: F811
    assert _prepare(origin, rule=INDEX_BASELINE)[0] == 0
    leftover = eval_tokenizer_db_name(SHA) + PREPARING_SUFFIX
    with psycopg.connect(admin_url(), autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{leftover}"')
    code, _ = _tokenize()
    assert code == 0 and leftover not in _databases()


def test_open_connection_on_base_fails_at_clone(origin: str) -> None:  # noqa: F811
    assert _prepare(origin, rule=INDEX_BASELINE)[0] == 0
    with psycopg.connect(_url(eval_db_name(INDEX_BASELINE, SHA)), autocommit=True):
        code, data = _tokenize()
    assert code == 1 and data["stage"] == "clone"
    assert eval_tokenizer_db_name(SHA) not in _databases()
