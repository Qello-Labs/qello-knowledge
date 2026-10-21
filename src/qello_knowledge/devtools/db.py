"""`qk-dev db up|down|reset`: 로컬 개발 DB 관리(FR-010~013). `qk-dev store bench`: 저장소 측정(QK-STO-001).

- `up`은 재실행해도 안전하다. 떠 있으면 그대로 두고 볼륨을 지우지 않는다.
- `reset`은 연결 대상이 로컬 compose DB일 때만 볼륨을 지운다. DB에 접속하지 않고 문자열로만 판단한다.
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from urllib.parse import urlsplit

from qello_knowledge.adapters.http import HttpsTransport
from qello_knowledge.config.check import build_report
from qello_knowledge.config.cli import add_check_options
from qello_knowledge.config.loader import SecretValue, load, merge_sources, read_env_file
from qello_knowledge.config.registry import Entrypoint
from qello_knowledge.devtools.measure import PreparedSource, measure_source, prepare_source, render_measurement
from qello_knowledge.sources.clock import SystemClock

DEFAULT_PORT = 54322
EXTENSIONS = ("vector", "pgroonga")
LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}
COMPOSE = ("docker", "compose")
PSQL = (*COMPOSE, "exec", "-T", "db", "psql", "-U", "postgres", "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-qtA")


def local_port(source: Mapping[str, str]) -> int:
    raw = source.get("QK_LOCAL_DB_PORT", "").strip()
    return int(raw) if raw.isdigit() else DEFAULT_PORT


def is_local_target(source: Mapping[str, str]) -> bool:
    """`DATABASE_URL`이 없거나 루프백 호스트의 로컬 DB 포트를 가리킬 때만 참이다(FR-013)."""
    url = source.get("DATABASE_URL", "").strip()
    if not url:
        return True
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        return False
    return parts.hostname in LOOPBACK_HOSTS and port == local_port(source)


def _run(args: Sequence[str], **kwargs) -> subprocess.CompletedProcess[str]:
    return subprocess.run(list(args), text=True, capture_output=True, check=False, **kwargs)  # noqa: S603


def _container_running() -> bool:
    result = _run((*COMPOSE, "ps", "--status", "running", "--quiet", "db"))
    return result.returncode == 0 and bool(result.stdout.strip())


def _port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


def enable_extensions() -> list[str]:
    """확장을 켜고, 켜지지 않은 확장 이름을 돌려준다."""
    missing = []
    for name in EXTENSIONS:
        result = _run((*PSQL, "-c", f"CREATE EXTENSION IF NOT EXISTS {name}"))
        if result.returncode != 0:
            missing.append(name)
    return missing


def up(source: Mapping[str, str]) -> int:
    port = local_port(source)
    env = {**os.environ, "QK_LOCAL_DB_PORT": str(port)}
    if not _container_running() and _port_in_use(port):
        print(
            f"포트 {port}를 다른 프로그램이 쓰고 있다. QK_LOCAL_DB_PORT=<다른 포트>를 지정해 다시 실행한다.",
            file=sys.stderr,
        )
        return 1
    result = _run((*COMPOSE, "up", "-d", "--wait", "db"), env=env)
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        print("로컬 DB를 시작하지 못했다. 위 docker compose 출력을 확인한다.", file=sys.stderr)
        return 1
    missing = enable_extensions()
    if missing:
        print(f"확장을 켜지 못했다: {', '.join(missing)}", file=sys.stderr)
        return 1
    print(f"로컬 DB 준비 완료: 127.0.0.1:{port}, 확장 {', '.join(EXTENSIONS)}")
    return 0


def down() -> int:
    result = _run((*COMPOSE, "down"))
    sys.stderr.write(result.stderr)
    return 0 if result.returncode == 0 else 1


def reset(source: Mapping[str, str]) -> int:
    if not is_local_target(source):
        print("DATABASE_URL이 로컬 개발 DB가 아니어서 재설정을 거부한다.", file=sys.stderr)
        return 1
    result = _run((*COMPOSE, "down", "--volumes"))
    if result.returncode != 0:
        sys.stderr.write(result.stderr)
        return 1
    return up(source)


def _source_failure(errors: Sequence[dict[str, str]], json_output: bool) -> int:
    print(
        json.dumps({"ok": False, "issues": errors}, ensure_ascii=False)
        if json_output
        else "자료원 수집 점검: 실패\n" + "\n".join(f"  {i['code']} {i['field']}" for i in errors)
    )
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="qk-dev", description="로컬 개발 도구")
    sub = parser.add_subparsers(dest="group", required=True)
    db = sub.add_parser("db", help="로컬 개발 DB")
    db.add_argument("action", choices=("up", "down", "reset"))
    db.add_argument("--env-file", type=Path, default=Path(".env"))
    store = sub.add_parser("store", help="저장소 측정(로컬 전용)")
    store.add_argument("action", choices=("bench",))
    store.add_argument("--env-file", type=Path, default=Path(".env"))
    store.add_argument("--text-bytes", type=int, default=1_100_000)
    store.add_argument("--repeat", type=int, default=100)
    store.add_argument("--top-n", type=int, default=20)
    source_command = sub.add_parser("source", help="자료원 수집 측정")
    source_sub = source_command.add_subparsers(dest="source_action", required=True)
    measure = source_sub.add_parser("measure", help="사전 검증 뒤 원본을 읽어 측정한다")
    add_check_options(measure)
    measure.add_argument("--name", required=True)
    measure.add_argument("--chunk", action="store_true", help="필터 통과 Markdown의 청킹 결과를 함께 측정한다")
    measure.add_argument("--sources", type=Path, default=Path("config/sources.toml"))
    measure.add_argument("--reviews", type=Path, default=Path("config/source_reviews"))
    measure.add_argument("--exceptions", type=Path, default=Path("config/security_exceptions.toml"))
    args = parser.parse_args(argv)
    if args.group == "source":
        settings = load(Entrypoint.INDEX, env_file=args.env_file)
        report = build_report(settings)
        if not report.ok:
            print(report.to_json() if args.json else report.to_text())
            return 1
        prepared = prepare_source(args.name, args.sources, args.reviews, args.exceptions)
        if not isinstance(prepared, PreparedSource):
            errors = [{"field": issue.field, "code": issue.code} for issue in prepared]
            return _source_failure(errors, args.json)
        token = settings.get(prepared.config.auth)
        if not isinstance(token, SecretValue):
            return _source_failure([{"field": "auth", "code": "MISSING"}], args.json)
        transport = HttpsTransport(prepared.config.allowed_hosts, token)
        measurement = measure_source(prepared, transport, SystemClock(), chunk=args.chunk)
        print(render_measurement(measurement, args.json))
        return 0 if measurement.ok else 1

    source = merge_sources(os.environ, read_env_file(args.env_file))
    if args.group == "store":
        # psycopg는 postgres 선택 의존성이라 이 명령에서만 가져온다.
        from qello_knowledge.devtools.bench import run_bench

        return run_bench(source, text_bytes=args.text_bytes, repeat=args.repeat, top_n=args.top_n)
    if args.action == "up":
        return up(source)
    if args.action == "down":
        return down()
    return reset(source)


if __name__ == "__main__":
    raise SystemExit(main())
