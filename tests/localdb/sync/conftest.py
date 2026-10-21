"""격리 DB를 재사용하되 기존 인덱스 버전을 미리 넣지 않는다."""

import psycopg
import pytest

from tests.localdb.store.conftest import db_url, store

__all__ = ["db_url", "store"]


@pytest.fixture(autouse=True)
def clean_sync_tables(db_url):
    with psycopg.connect(db_url, autocommit=True) as conn:
        conn.execute(
            "TRUNCATE qk.sync_run, qk.sync_source, qk.chunk, qk.embedding, qk.artifact, qk.index_version "
            "RESTART IDENTITY CASCADE"
        )


@pytest.fixture
def sync_store(db_url):
    from qello_knowledge.adapters.postgres.sync_store import PostgresSyncStore

    with PostgresSyncStore(db_url) as instance:
        yield instance
