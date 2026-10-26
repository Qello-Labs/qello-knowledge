"""세션 전용 로컬 DB에서 검색 마감·취소를 검증한다(T025)."""

import threading
from concurrent.futures import ThreadPoolExecutor
from time import monotonic

import psycopg
import pytest

from qello_knowledge.adapters.postgres.store import PostgresStore, StoreDeadline
from qello_knowledge.domain.store import EMBEDDING_DIMENSION, StoreError

pytestmark = pytest.mark.localdb


class BotConnection:
    def __init__(self, connection, *, delay=0, cancel_fails=False):
        self.connection = connection
        self.delay = delay
        self.cancel_fails = cancel_fails
        self.queries = []
        self.cancelled = threading.Event()

    @property
    def closed(self):
        return self.connection.closed

    def execute(self, query, params=None):
        self.queries.append(query)
        if self.delay:
            self.connection.execute("SELECT pg_sleep(%s)", (self.delay,))
        return self.connection.execute(query, params)

    def cancel_safe(self, **kwargs):
        self.cancelled.set()
        if self.cancel_fails:
            raise OSError("synthetic cancellation failure")
        self.connection.cancel_safe(**kwargs)

    def close(self):
        self.connection.close()


@pytest.mark.parametrize(
    "method,args",
    [
        ("search_vector", ((1.0,) * EMBEDDING_DIMENSION, 1)),
        ("search_keyword", ("synthetic", 1)),
        ("search_keyword_terms", (("synthetic",), 1)),
        ("chunk_context", ((), 0, 0)),
        ("chunk_neighbors", (1, 0, 0)),
        ("source_revisions", ()),
    ],
)
def test_bot_no_query_or_new_connection_without_time(db_url, monkeypatch, method, args):
    opened = []
    monkeypatch.setattr("qello_knowledge.adapters.postgres.store.connect", lambda url: opened.append(url))
    with PostgresStore(db_url, deadline=lambda: 0) as store:
        with pytest.raises(StoreDeadline):
            getattr(store, method)(*args)
    assert not opened
    assert issubclass(StoreDeadline, StoreError)


def test_bot_no_new_connection_with_less_than_connection_timeout(db_url, monkeypatch):
    opened = []
    monkeypatch.setattr("qello_knowledge.adapters.postgres.store.connect", lambda url: opened.append(url))
    with PostgresStore(db_url, deadline=lambda: 9.99) as store:
        with pytest.raises(StoreDeadline):
            store.search_keyword("synthetic", 1)
    assert not opened


@pytest.mark.parametrize("cancel_fails", [False, True])
def test_bot_slow_query_cancel_closes_connection_then_next_call_reconnects(db_url, cancel_fails):
    connection = BotConnection(psycopg.connect(db_url, autocommit=True), delay=0.08, cancel_fails=cancel_fails)
    end = monotonic() + 0.02
    store = PostgresStore(db_url, deadline=lambda: end - monotonic())
    store._conn = connection
    try:
        with pytest.raises(StoreDeadline):
            store.search_keyword("synthetic", 1)
        assert connection.cancelled.is_set() and connection.closed
        end = monotonic() + 15
        assert store.search_keyword("synthetic", 1).status == "ok"
        assert store._conn is not connection
    finally:
        store.close()
    assert not any(t.name.startswith("qk-store-deadline") for t in threading.enumerate())


def test_bot_finished_query_cancels_timer_and_adds_no_set_statement(db_url):
    connection = BotConnection(psycopg.connect(db_url, autocommit=True))
    with PostgresStore(db_url, deadline=lambda: 10) as store:
        store._conn = connection
        for _ in range(12):
            assert store.search_keyword("synthetic", 1).status == "ok"
    assert len(connection.queries) == 12
    assert all(query.startswith("SELECT qk.search_keyword(") for query in connection.queries)
    assert not connection.cancelled.is_set()
    assert not any(t.name.startswith("qk-store-deadline") for t in threading.enumerate())


def test_bot_deadline_optional_preserves_existing_behavior(db_url):
    with PostgresStore(db_url) as store:
        assert store.search_keyword("synthetic", 1).status == "ok"


def test_bot_query_completion_races_late_cancel_without_leaking_timer(db_url):
    query_done, cancel_started, release_cancel = threading.Event(), threading.Event(), threading.Event()

    class BotLateCancel(BotConnection):
        def execute(self, query, params=None):
            result = super().execute(query, params)
            query_done.set()
            assert cancel_started.wait(0.4)
            return result

        def cancel_safe(self, **kwargs):
            cancel_started.set()
            assert query_done.wait(0.4) and release_cancel.wait(0.4)
            super().cancel_safe(**kwargs)

    connection = BotLateCancel(psycopg.connect(db_url, autocommit=True))
    end = monotonic() + 0.04
    with PostgresStore(db_url, deadline=lambda: end - monotonic()) as store, ThreadPoolExecutor(1) as pool:
        store._conn = connection
        future = pool.submit(store.search_keyword, "synthetic", 1)
        try:
            assert cancel_started.wait(0.4) and query_done.is_set()
        finally:
            release_cancel.set()
        with pytest.raises(StoreDeadline):
            future.result()
    assert connection.closed
    assert not any(t.name.startswith("qk-store-deadline") for t in threading.enumerate())


def test_bot_retrieval_summary_counts_actual_sql_calls_without_set(db_url):
    from qello_knowledge.domain.retrieval import RetrievalRequest
    from qello_knowledge.retrieval import RetrievalDeps, retrieve
    from tests.unit.retrieval.fakes import query_embedder

    connection = BotConnection(psycopg.connect(db_url, autocommit=True))
    embedder, provider, ledger = query_embedder()
    with PostgresStore(db_url, deadline=lambda: 15) as store:
        store._conn = connection
        result = retrieve(RetrievalRequest("합성 검색"), RetrievalDeps(store, embedder))
    # FR-026: 제공자 호출마다 사용량 기록도 1회 센다. 여기서는 메모리 장부로 그 기록을 관찰한다.
    assert len(ledger.rows) == len(provider.calls)
    assert result.summary.external_calls == len(connection.queries) + len(provider.calls) + len(ledger.rows)
    assert result.summary.external_calls <= 7
    assert connection.queries and all(query.startswith("SELECT qk.") for query in connection.queries)
