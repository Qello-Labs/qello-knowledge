"""세션 전용 로컬 시험 DB의 OBS 자료와 역할 연결."""

from contextlib import contextmanager

import psycopg
from psycopg.types.json import Jsonb

from tests.unit.query.obs_builders import QUESTIONER, RUN


@contextmanager
def query_connection(url):
    with psycopg.connect(url, autocommit=True) as conn:
        with conn.transaction(force_rollback=True):
            conn.execute("GRANT qk_query TO CURRENT_USER WITH SET TRUE, INHERIT FALSE")
            conn.execute("SET LOCAL ROLE qk_query")
            yield conn


@contextmanager
def obs_connection(url):
    with psycopg.connect(url, autocommit=True) as conn:
        # 이 연결은 기존 fixture가 만든 세션 전용 qk_test DB다.
        conn.execute("TRUNCATE qk.query_text, qk.query_feedback, qk.query_record, qk.query_erasure_run")
        yield conn


def record_payload(**changes):
    return {
        "run_id": RUN,
        "received_at": "2026-10-29T01:02:03+00:00",
        "questioner_id": QUESTIONER,
        "private": False,
        "status": "answered",
        "first_response_ms": 10,
        **changes,
    }


def seed_record(conn, **changes):
    payload = record_payload(**changes)
    conn.execute("SELECT qk.query_record_insert(%s)", (Jsonb(payload),))
    return payload["run_id"]


def seed_feedback(conn, *, run_id=RUN, rater_id=QUESTIONER, value="down"):
    return conn.execute("SELECT qk.query_feedback_set(%s,%s,%s)", (run_id, rater_id, value)).fetchone()[0]


def seed_text(conn, *, run_id=RUN, user=QUESTIONER, question="합성 질문 1"):
    return conn.execute("SELECT qk.query_text_store(%s,%s,%s)", (run_id, user, question)).fetchone()[0]
