"""관리 연결 전용 질의 관측 조회·지우기. 대상 식별자는 결과에 넣지 않는다."""

from contextlib import contextmanager

import psycopg

from qello_knowledge.adapters.postgres.query_log import QueryLogError


class PostgresQueryLogAdmin:
    def __init__(self, url):
        self._url = url
        self._conn = None

    @contextmanager
    def _db(self):
        try:
            if self._conn is None or self._conn.closed:
                self._conn = psycopg.connect(self._url, autocommit=True, connect_timeout=1)
            yield self._conn
        except psycopg.Error:
            self.close()
            raise QueryLogError("unavailable") from None

    def close(self):
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def erase_user(self, user, *, confirm=False):
        with self._db() as conn, conn.transaction():
            # 동의 저장과 동시에 지울 때도 새 원문이 삭제 단계 뒤 끼어들지 않게 기록을 잠근다.
            conn.execute("SELECT run_id FROM qk.query_record WHERE questioner_id=%s FOR UPDATE", (user,)).fetchall()
            texts = conn.execute(
                "SELECT count(*) FROM qk.query_text t JOIN qk.query_record r USING(run_id) WHERE r.questioner_id=%s",
                (user,),
            ).fetchone()[0]
            records = conn.execute("SELECT count(*) FROM qk.query_record WHERE questioner_id=%s", (user,)).fetchone()[0]
            feedback = conn.execute("SELECT count(*) FROM qk.query_feedback WHERE rater_id=%s", (user,)).fetchone()[0]
            if confirm:
                conn.execute(
                    "DELETE FROM qk.query_text t USING qk.query_record r "
                    "WHERE t.run_id=r.run_id AND r.questioner_id=%s",
                    (user,),
                )
                conn.execute("UPDATE qk.query_record SET questioner_id=NULL WHERE questioner_id=%s", (user,))
                conn.execute("UPDATE qk.query_feedback SET rater_id=NULL WHERE rater_id=%s", (user,))
                conn.execute(
                    "INSERT INTO qk.query_erasure_run(kind,texts_deleted,records_cleared,feedback_cleared) "
                    "VALUES('user',%s,%s,%s)",
                    (texts, records, feedback),
                )
            return dict(texts_deleted=texts, records_cleared=records, feedback_cleared=feedback)

    def erase_texts(self, *, confirm=False):
        with self._db() as conn, conn.transaction():
            if confirm:
                count = conn.execute(
                    "WITH removed AS (DELETE FROM qk.query_text RETURNING 1) SELECT count(*) FROM removed"
                ).fetchone()[0]
                conn.execute(
                    "INSERT INTO qk.query_erasure_run(kind,texts_deleted,records_cleared,feedback_cleared) "
                    "VALUES('all_texts',%s,0,0)",
                    (count,),
                )
            else:
                count = conn.execute("SELECT count(*) FROM qk.query_text").fetchone()[0]
            return dict(texts_deleted=count, records_cleared=0, feedback_cleared=0)

    def report(self, since, until, *, query_reserve=3000, retain_until=None):
        from collections import Counter
        from datetime import UTC, datetime

        params = (since, until)
        with self._db() as conn, conn.transaction():
            conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
            rows = conn.execute(
                "SELECT status,failure,private,consented,retrieval,generation,index_version,model_id,"
                "prompt_version FROM qk.query_record WHERE "
                "received_at >= %s::date AND received_at < %s::date + interval '1 day'",
                params,
            ).fetchall()
            timing = conn.execute(
                "SELECT percentile_cont(.5) WITHIN GROUP(ORDER BY first_response_ms),"
                "percentile_cont(.95) WITHIN GROUP(ORDER BY first_response_ms),"
                "percentile_cont(.5) WITHIN GROUP(ORDER BY total_ms),"
                "percentile_cont(.95) WITHIN GROUP(ORDER BY total_ms) "
                "FROM qk.query_record WHERE "
                "received_at >= %s::date AND received_at < %s::date + interval '1 day'",
                params,
            ).fetchone()
            feedback = conn.execute(
                "SELECT f.value,count(*),count(*) FILTER(WHERE f.rater_id IS NULL) "
                "FROM qk.query_feedback f JOIN qk.query_record r USING(run_id) "
                "WHERE "
                "received_at >= %s::date AND received_at < %s::date + interval '1 day'"
                " GROUP BY f.value",
                params,
            ).fetchall()
            rated = conn.execute(
                "SELECT count(*) FROM qk.query_record r WHERE "
                "received_at >= %s::date AND received_at < %s::date + interval '1 day'"
                " AND EXISTS(SELECT 1 FROM qk.query_feedback f WHERE f.run_id=r.run_id)",
                params,
            ).fetchone()[0]
            usage = [
                row[0]
                for row in conn.execute(
                    "SELECT qk.generation_usage_today(%s,d::date) "
                    "FROM generate_series(%s::date,%s::date,interval '1 day') d",
                    (query_reserve, since, until),
                )
            ]
            has_text = conn.execute("SELECT EXISTS(SELECT 1 FROM qk.query_text)").fetchone()[0]
        count = len(rows)
        neurons = {"measured": 0, "estimated": 0}
        for row in rows:
            for summary in (row[4], row[5]):
                key = "measured" if summary.get("measured") is True else "estimated"
                value = (
                    summary.get("neurons", 0)
                    if key == "measured"
                    else summary.get("estimated_neurons", summary.get("neurons", 0))
                )
                neurons[key] += value
        votes = {"up": 0, "down": 0, "anonymous": 0}
        for value, n, anonymous in feedback:
            votes[value] = n
            votes["anonymous"] += anonymous
        warnings = []
        if retain_until is not None and retain_until < datetime.now(UTC).date() and has_text:
            warnings.append("원문 기록 보존 상한이 지났습니다. qk-index queries erase-texts를 확인하세요")
        return {
            "period": {"since": since.isoformat(), "until": until.isoformat()},
            "sample_size": count,
            "records": count,
            "by_status": dict(Counter(r[0] for r in rows)),
            "by_failure": dict(Counter(r[1] for r in rows if r[1] is not None)),
            "first_response_ms": dict(zip(("p50", "p95"), timing[:2], strict=True)),
            "total_ms": dict(zip(("p50", "p95"), timing[2:], strict=True)),
            "private_ratio": sum(r[2] for r in rows) / count if count else 0,
            "feedback": votes,
            "rated_ratio": rated / count if count else 0,
            "consented": sum(r[3] for r in rows),
            "neurons": neurons,
            "answer_usage_by_day": usage,
            "index_versions": dict(Counter(r[6] or "unknown" for r in rows)),
            "models": dict(Counter(r[7] or "unknown" for r in rows)),
            "prompt_versions": dict(Counter(r[8] or "unknown" for r in rows)),
            "measurement_boundary": "질의 서비스가 요청을 받은 때부터. Worker 서명 검사·중계 구간 제외",
            "relay_failures_note": "Worker 대체 응답은 Workers 로그의 relay_failed 줄로 센다",
            "warnings": warnings,
        }

    def export_rows(self, *, all_rows=False):
        with self._db() as conn:
            rows = conn.execute(
                "SELECT r.run_id,(r.received_at AT TIME ZONE 'UTC')::date,t.question,"
                "r.context_chunk_ids,r.context_block_sizes,r.cited_blocks,r.index_version,"
                "(SELECT count(*) FROM qk.query_feedback f WHERE f.run_id=r.run_id AND f.value='up'),"
                "(SELECT count(*) FROM qk.query_feedback f WHERE f.run_id=r.run_id AND f.value='down') "
                "FROM qk.query_record r JOIN qk.query_text t USING(run_id) WHERE %s OR EXISTS("
                "SELECT 1 FROM qk.query_feedback f WHERE f.run_id=r.run_id AND f.value='down') "
                "ORDER BY r.received_at,r.run_id",
                (all_rows,),
            ).fetchall()
        return [
            dict(
                run_id=r[0],
                received_date=r[1].isoformat(),
                question=r[2],
                context_chunk_ids=r[3],
                context_block_sizes=r[4],
                cited_blocks=r[5],
                index_version=r[6],
                feedback={"up": r[7], "down": r[8]},
            )
            for r in rows
        ]
