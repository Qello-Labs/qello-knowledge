"""보이는 청크가 있는 문서만 자료원 이름별로 센다."""

from datetime import UTC, datetime

import pytest

from qello_knowledge.adapters.postgres.query_log import PostgresQueryLog
from tests.localdb.query.bot_builders import bot_document
from tests.localdb.query.obs_db import obs_connection, query_connection

pytestmark = pytest.mark.localdb


def test_sources_visibility_and_last_seen(db_url, bot_store):
    with obs_connection(db_url) as admin:
        bot_document(bot_store, "obs-visible", ["합성 자료"])
        bot_document(bot_store, "obs-hidden", ["합성 자료"], access_scope=None)
        stamp = datetime(2026, 10, 29, 1, 0, tzinfo=UTC)
        admin.execute(
            "UPDATE qk.artifact SET source_name=CASE WHEN source_id='obs-hidden' THEN 'hidden' ELSE 'alpha' END,"
            " last_seen_at=%s",
            (stamp,),
        )
        with query_connection(db_url) as conn:
            port = PostgresQueryLog(db_url)
            port._conn = conn
            view = port.sources()
            port._conn = None
        assert view.index_version == "v1"
        assert len(view.sources) == 1
        assert (view.sources[0].name, view.sources[0].documents, view.sources[0].last_seen_at) == ("alpha", 1, stamp)
        admin.execute("UPDATE qk.index_version SET status='ready' WHERE status='active'")
        port = PostgresQueryLog(db_url)
        try:
            assert port.sources().index_version is None
        finally:
            port.close()
