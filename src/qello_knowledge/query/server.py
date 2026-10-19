"""`qk-query`: 질의응답 진입점의 로컬 실행. 루프백에만 묶는다."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from qello_knowledge.config.check import CheckReport, build_report
from qello_knowledge.config.cli import add_check_options, run_check
from qello_knowledge.config.loader import load
from qello_knowledge.config.registry import Entrypoint
from qello_knowledge.query.app import handle

HOST = "127.0.0.1"


class _Handler(BaseHTTPRequestHandler):
    def __init__(self, *args, report: Callable[[], CheckReport], **kwargs) -> None:
        self._report = report
        super().__init__(*args, **kwargs)

    def _respond(self) -> None:
        status, body = handle(self.command, self.path, self._report)
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    do_GET = _respond
    do_POST = _respond
    do_PUT = _respond
    do_DELETE = _respond

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - 표준 라이브러리 시그니처
        sys.stderr.write(f"{self.command} {self.path}\n")


def make_server(port: int, env_file: Path | None) -> ThreadingHTTPServer:
    def report() -> CheckReport:
        return build_report(load(Entrypoint.QUERY, env_file=env_file))

    return ThreadingHTTPServer((HOST, port), partial(_Handler, report=report))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="qk-query", description="질의응답 진입점")
    sub = parser.add_subparsers(dest="command", required=True)
    add_check_options(sub.add_parser("check", help="설정만 점검한다. 외부 호출 없음"))
    serve = sub.add_parser("serve", help=f"로컬 HTTP 서버를 {HOST}에 띄운다")
    serve.add_argument("--port", type=int, default=8787)
    serve.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args(argv)

    if args.command == "check":
        code, _ = run_check(Entrypoint.QUERY, args)
        return code

    server = make_server(args.port, args.env_file)
    print(f"qk-query: http://{HOST}:{server.server_port}/healthz", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
