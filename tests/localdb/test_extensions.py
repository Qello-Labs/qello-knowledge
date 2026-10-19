"""로컬 DB에서 벡터 유사도 질의와 한국어 키워드 질의가 되는지 본다(US1 AS3, FR-011)."""

import psycopg
import pytest

from tests.conftest import local_db_port

pytestmark = pytest.mark.localdb


@pytest.fixture
def conn():
    # compose.yaml의 로컬 전용 기본 계정이다.
    with psycopg.connect(
        host="127.0.0.1", port=local_db_port(), user="postgres", password="postgres", dbname="postgres"
    ) as connection:
        yield connection
        connection.rollback()


def test_extensions_are_enabled(conn) -> None:
    rows = conn.execute("SELECT extname FROM pg_extension WHERE extname IN ('vector', 'pgroonga')").fetchall()
    assert {row[0] for row in rows} == {"vector", "pgroonga"}


def test_vector_similarity_query(conn) -> None:
    conn.execute("CREATE TEMP TABLE qk_vec (id int, embedding vector(3))")
    conn.execute("INSERT INTO qk_vec VALUES (1, '[1,0,0]'), (2, '[0,1,0]'), (3, '[0.9,0.1,0]')")
    rows = conn.execute("SELECT id FROM qk_vec ORDER BY embedding <-> '[1,0,0]' LIMIT 2").fetchall()
    assert [row[0] for row in rows] == [1, 3]


def test_korean_keyword_query(conn) -> None:
    conn.execute("CREATE TEMP TABLE qk_doc (id int, body text)")
    conn.execute(
        "INSERT INTO qk_doc VALUES (1, '로컬 개발 환경을 띄우는 방법'), (2, '배포 절차'), (3, '개발 서버 설정')"
    )
    conn.execute("CREATE INDEX qk_doc_body ON qk_doc USING pgroonga (body)")
    rows = conn.execute("SELECT id FROM qk_doc WHERE body &@~ '개발' ORDER BY id").fetchall()
    assert [row[0] for row in rows] == [1, 3]
