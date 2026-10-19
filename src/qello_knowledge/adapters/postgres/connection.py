"""PostgreSQL 연결. 오류 메시지에 호스트·사용자·비밀번호를 넣지 않는다(AGENTS.md 6절)."""

from __future__ import annotations

from collections.abc import Mapping

import psycopg
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from qello_knowledge.devtools.db import LOOPBACK_HOSTS, local_port
from qello_knowledge.domain.store import StoreUnavailable

# compose.yaml의 POSTGRES_PASSWORD와 같은 로컬 컨테이너 전용 기본값이다. 운영 비밀번호가 아니다.
LOCAL_DEV_PASSWORD = "postgres"  # noqa: S105 - 로컬 개발 DB 전용 공개 기본값


def database_url(source: Mapping[str, str]) -> str:
    """`DATABASE_URL`이 없으면 로컬 개발 DB를 쓴다. 반환값은 psycopg 접속 문자열이다."""
    url = source.get("DATABASE_URL", "").strip()
    if url:
        return url
    return make_conninfo(
        host="127.0.0.1", port=local_port(source), user="postgres", password=LOCAL_DEV_PASSWORD, dbname="postgres"
    )


def with_database(conninfo: str, dbname: str) -> str:
    """같은 서버의 다른 데이터베이스를 가리키는 접속 문자열. URL과 키-값 형식 모두 받는다."""
    return make_conninfo(**{**conninfo_to_dict(conninfo), "dbname": dbname})


def is_local(source: Mapping[str, str]) -> bool:
    """`DATABASE_URL`이 없거나 루프백 호스트의 로컬 DB 포트를 가리킬 때만 참이다.

    QK-FND-001 `is_local_target`과 같은 규칙이고, URL과 키-값 형식을 모두 해석한다. 해석할 수 없으면 원격으로 본다.
    """
    url = source.get("DATABASE_URL", "").strip()
    if not url:
        return True
    try:
        params = conninfo_to_dict(url)
        port = int(params.get("port") or 5432)
    except (psycopg.ProgrammingError, ValueError):
        return False
    return params.get("host") in LOOPBACK_HOSTS and port == local_port(source)


def target_label(source: Mapping[str, str]) -> str:
    return "local" if is_local(source) else "remote"


def connect(url: str, *, autocommit: bool = True) -> psycopg.Connection:
    try:
        return psycopg.connect(url, autocommit=autocommit, connect_timeout=10)
    except psycopg.OperationalError as exc:
        raise StoreUnavailable("저장소에 연결할 수 없다") from exc
