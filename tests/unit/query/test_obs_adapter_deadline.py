"""설정 왕복을 포함한 앞 길 절대 마감 취소."""

from threading import Event
from time import monotonic

import psycopg
import pytest

from qello_knowledge.adapters.postgres.query_log import PostgresQueryLog, QueryLogError


@pytest.mark.parametrize("stall", ["setting", "function"])
def test_setting_roundtrip_and_function_share_cancel_deadline(stall):
    class Connection:
        closed = False

        def __init__(self):
            self.cancelled = Event()
            self.settings = []
            self.function_started = False

        def execute(self, sql, args=()):
            if "set_config" in sql:
                self.settings.append(int(args[0]))
                if len(self.settings) == 1:
                    if stall == "setting":
                        if self.cancelled.wait(2):
                            raise psycopg.errors.QueryCanceled()
                    else:
                        self.cancelled.wait(0.6)
                return self
            self.function_started = True
            if self.cancelled.wait(2):
                raise psycopg.errors.QueryCanceled()
            return self

        def fetchone(self):
            return ("stored",)

        def cancel_safe(self, *, timeout):
            self.cancelled.set()

        def close(self):
            self.closed = True

    conn = Connection()
    port = PostgresQueryLog("synthetic", connector=lambda *a, **kw: conn)
    start = monotonic()
    port.set_deadline(start + 1)
    try:
        with pytest.raises(QueryLogError, match="^timeout$"):
            port.feedback("run", "user", "up")
        assert monotonic() - start < 0.95
        assert conn.cancelled.is_set()
        if stall == "function":
            assert conn.function_started
            assert 100 <= conn.settings[-1] <= 200
        else:
            assert not conn.function_started
    finally:
        port.close()
