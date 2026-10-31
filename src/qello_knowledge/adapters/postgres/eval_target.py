"""평가 대상과 운영 사용 장부의 PostgreSQL 구현(QK-EVL-001 research R-04·R-05·R-07).

- 평가 대상은 로컬 컨테이너의 `qk_eval_*` 데이터베이스뿐이다. 접속 정보는 `DATABASE_URL`이 아니라
  로컬 기본 주소와 데이터베이스 이름으로 만든다(`devtools/eval_index.py`와 같은 방식).
- 대상 설명·문서 표·장부는 읽기 전용 트랜잭션에서 읽는다. autocommit 연결에서는 psycopg가 트랜잭션을 열지 않아
  `read_only`가 걸리지 않으므로 `autocommit=False`로 연다.
- 오류 문구에 접속 정보를 넣지 않는다(AGENTS.md 6절).
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from contextlib import contextmanager

import psycopg
from psycopg.conninfo import conninfo_to_dict

from qello_knowledge.adapters.postgres.connection import connect, database_url, with_database
from qello_knowledge.adapters.postgres.generation_usage import answer_usage
from qello_knowledge.adapters.postgres.store import PostgresStore
from qello_knowledge.devtools.db import LOOPBACK_HOSTS, local_port
from qello_knowledge.domain.generation import AnswerUsageToday
from qello_knowledge.domain.keyword_rules import index_rule_for
from qello_knowledge.domain.store import StoreUnavailable
from qello_knowledge.ports.evaluation import LedgerUnavailable, TargetDescription, TargetDocument, TargetUnavailable

EVAL_PREFIX = "qk_eval_"
KEYWORD_INDEX = "chunk_search_text_pgroonga"

_TOKENIZER = (
    "SELECT c.reloptions FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace"
    " WHERE n.nspname = 'qk' AND c.relname = %s"
)
_COMMITS = (
    "SELECT DISTINCT ON (s.source_name) s.source_name, s.origin_version, r.finished_at"
    " FROM qk.sync_run_source s JOIN qk.sync_run r ON r.run_id = s.run_id"
    " WHERE s.status = 'succeeded' AND s.origin_version IS NOT NULL"
    " ORDER BY s.source_name, r.started_at DESC, r.run_id DESC"
)  # PostgresStore.source_revisions와 같은 질의에 완료 시각을 더한다
_DOCUMENTS = (
    "SELECT DISTINCT a.source_name, a.location, a.source_url FROM qk.chunk c JOIN qk.artifact a ON a.id = c.artifact_id"
    " WHERE qk.is_visible(c, a, (SELECT id FROM qk.index_version WHERE status = 'active'))"
    " AND a.source_name IS NOT NULL AND a.location IS NOT NULL"
    " ORDER BY 1, 2, 3"
)
_UNLOCATED = (
    "SELECT count(DISTINCT a.id) FROM qk.chunk c JOIN qk.artifact a ON a.id = c.artifact_id"
    " WHERE qk.is_visible(c, a, (SELECT id FROM qk.index_version WHERE status = 'active'))"
    " AND (a.source_name IS NULL OR a.location IS NULL)"
)
_CHUNK_TEXTS = (
    "SELECT a.source_name, a.location, c.body FROM qk.chunk c JOIN qk.artifact a ON a.id = c.artifact_id"
    " WHERE qk.is_visible(c, a, (SELECT id FROM qk.index_version WHERE status = 'active'))"
    " AND a.source_name IS NOT NULL AND a.location IS NOT NULL"
    " ORDER BY a.source_name, a.location, c.ordinal"
)


def eval_target_url(dbname: str, source_env: Mapping[str, str]) -> str:
    """로컬 컨테이너의 평가용 데이터베이스 접속 문자열. `DATABASE_URL`은 읽지 않는다."""
    if not dbname.startswith(EVAL_PREFIX):
        raise ValueError("평가 대상은 qk_eval_ 데이터베이스만 받는다")
    admin = database_url({k: v for k, v in source_env.items() if k == "QK_LOCAL_DB_PORT"})
    return with_database(admin, dbname)


def ledger_is_production(conninfo: str, source_env: Mapping[str, str], targets: Sequence[str]) -> bool:
    """장부 접속 정보가 운영을 가리키는지. 로컬 컨테이너나 평가 대상이면 거짓이다(research R-07).

    규칙은 `connection.is_local`과 같고, 호스트가 없거나 소켓 경로인 경우와 해석할 수 없는 경우도 운영으로 보지 않는다.
    """
    try:
        params = conninfo_to_dict(conninfo)
        port = int(params.get("port") or 5432)
    except (psycopg.ProgrammingError, ValueError):
        return False
    host = str(params.get("host") or "")
    if not host or host.startswith("/") or (host in LOOPBACK_HOSTS and port == local_port(source_env)):
        return False
    return params.get("dbname") not in set(targets)


@contextmanager
def _read_only(url: str, unavailable: type[Exception]) -> Iterator[psycopg.Connection]:
    try:
        conn = connect(url, autocommit=False)
    except StoreUnavailable as exc:
        raise unavailable("연결할 수 없다") from exc
    try:
        conn.read_only = True
        yield conn
    except psycopg.Error as exc:
        raise unavailable(f"읽기 오류: {exc.sqlstate or type(exc).__name__}") from exc
    finally:
        try:
            conn.rollback()
        finally:
            conn.close()


def _tokenizer(reloptions: Sequence[str] | None) -> str | None:
    for option in reloptions or ():
        key, _, value = option.partition("=")
        if key.strip() == "tokenizer" and value.strip():
            return value.strip().strip("'\"")
    return None


class PostgresEvalTarget:
    """`EvalTarget` 구현. `store`는 같은 데이터베이스의 `PostgresStore`다."""

    def __init__(self, dbname: str, source_env: Mapping[str, str]) -> None:
        self.database = dbname
        self._url = eval_target_url(dbname, source_env)
        self.store = PostgresStore(self._url)

    def close(self) -> None:
        self.store.close()

    def __enter__(self) -> PostgresEvalTarget:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def describe(self) -> TargetDescription:
        with _read_only(self._url, TargetUnavailable) as conn:
            active = conn.execute(
                "SELECT id, embedding_model, dimension FROM qk.index_version WHERE status = 'active'"
            ).fetchone()
            options = conn.execute(_TOKENIZER, (KEYWORD_INDEX,)).fetchone()
            revisions = conn.execute(_COMMITS).fetchall()
            sources = conn.execute("SELECT source_name FROM qk.sync_source ORDER BY source_name").fetchall()
            unlocated = conn.execute(_UNLOCATED).fetchone()
        version, model, dimension = active if active is not None else (None, None, None)
        finished = [row[2] for row in revisions if row[2] is not None]
        return TargetDescription(
            database=self.database,
            index_version=version,
            embedding_model=model,
            dimension=dimension,
            index_rule=index_rule_for(version),
            tokenizer=_tokenizer(options[0]) if options is not None else None,
            commits={str(name): str(revision) for name, revision, _ in revisions},
            synced_at=max(finished) if finished else None,
            sources=tuple(str(row[0]) for row in sources),
            unlocated_documents=int(unlocated[0]) if unlocated else 0,
        )

    def documents(self) -> tuple[TargetDocument, ...]:
        with _read_only(self._url, TargetUnavailable) as conn:
            rows = conn.execute(_DOCUMENTS).fetchall()
        return tuple(TargetDocument(source=str(s), location=str(loc), source_url=str(url)) for s, loc, url in rows)

    def visible_chunk_texts(self) -> Iterator[tuple[str, str, str]]:
        """활성 인덱스 버전의 노출 청크 `(자료원 이름, 위치, 본문)`. `eval identifiers`만 쓴다(research R-13)."""
        with _read_only(self._url, TargetUnavailable) as conn:
            rows = conn.execute(_CHUNK_TEXTS).fetchall()
        for source, location, body in rows:
            yield str(source), str(location), str(body)


class PostgresDayUsageReader:
    """`DayUsageReader` 구현. 장부 함수 `qk.generation_usage_today` 하나만 읽기 전용으로 부른다."""

    def __init__(self, url: str, query_reserve: int) -> None:
        self._url = url
        self._query_reserve = query_reserve

    @contextmanager
    def _open(self) -> Iterator[psycopg.Connection]:
        with _read_only(self._url, LedgerUnavailable) as conn:
            yield conn

    def today(self) -> AnswerUsageToday:
        with self._open() as conn:
            row = conn.execute("SELECT qk.generation_usage_today(%s)", (self._query_reserve,)).fetchone()
        if row is None or row[0] is None:
            raise LedgerUnavailable("장부가 비어 있다")
        try:
            return answer_usage(row[0])
        except (KeyError, TypeError, ValueError) as exc:
            raise LedgerUnavailable("장부 형식이 다르다") from exc


__all__ = [
    "EVAL_PREFIX",
    "KEYWORD_INDEX",
    "PostgresDayUsageReader",
    "PostgresEvalTarget",
    "eval_target_url",
    "ledger_is_production",
]
