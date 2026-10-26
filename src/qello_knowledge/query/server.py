"""`qk-query`: 질의응답 진입점의 로컬 실행. 루프백에만 묶는다."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from time import monotonic

from qello_knowledge.adapters.discord.webhook import DiscordWebhook
from qello_knowledge.config.check import CheckReport, build_report
from qello_knowledge.config.cli import add_check_options, run_check
from qello_knowledge.config.loader import Settings, SettingStatus, load
from qello_knowledge.config.registry import Entrypoint
from qello_knowledge.discord.signature import require_backend
from qello_knowledge.domain.retrieval import RetrievalSettings
from qello_knowledge.query.app import DiscordApp, handle

HOST = "127.0.0.1"


def write_run_log(record):
    sys.stderr.write(record.to_json() + "\n")


def _register_commands(args):
    settings = load(Entrypoint.REGISTER, env_file=args.env_file)
    if args.dry_run:
        # 전송하지 않을 때 누락된 토큰만 허용한다. 입력한 값의 형식 검사는 유지한다.
        settings = Settings(
            settings.entrypoint,
            tuple(
                item
                for item in settings.items
                if not (item.spec.name == "DISCORD_BOT_TOKEN" and item.status is SettingStatus.MISSING)
            ),
        )
    report = build_report(settings)
    if not report.ok:
        print(report.to_text(), file=sys.stderr)
        return 2
    commands = [
        {
            "name": "ask",
            "type": 1,
            "description": "팀 자료에서 찾아 출처와 함께 답합니다",
            "contexts": [0],
            "options": [
                {
                    "type": 3,
                    "name": "질문",
                    "description": "물어볼 내용",
                    "required": True,
                    "min_length": 1,
                    "max_length": RetrievalSettings().question_max_chars,
                },
                {"type": 5, "name": "나만_보기", "description": "켜면 답변을 나만 봅니다", "required": False},
            ],
        }
    ]
    if args.dry_run:
        print(json.dumps(commands, ensure_ascii=False))
        return 0
    result = DiscordWebhook(str(settings.get("DISCORD_APPLICATION_ID"))).register_commands(
        str(settings.get("QK_DISCORD_GUILD_ID")),
        settings.get("DISCORD_BOT_TOKEN").reveal(),
        commands,
        deadline=monotonic() + 3,
    )
    if result.failure is not None:
        print(f"Discord status: {result.status if result.status is not None else 'unavailable'}", file=sys.stderr)
        return 3
    return 0


class _Handler(BaseHTTPRequestHandler):
    def __init__(self, *args, report: Callable[[], CheckReport], app=None, **kwargs) -> None:
        self._report = report
        self._app = app
        super().__init__(*args, **kwargs)

    def _respond(self) -> None:
        raw = b""
        if self.command == "POST" and self.path in ("/discord/interactions", "/discord/interactions/start"):
            try:
                length = int(self.headers.get("Content-Length", "-1"))
            except ValueError:
                length = -1
            if not 0 <= length <= 65536:
                self.send_response(413 if length > 65536 else 400)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            raw = self.rfile.read(length)
        response = handle(self.command, self.path, self._report, body=raw, headers=self.headers, app=self._app)
        status, body = response[:2]
        headers = response[2] if len(response) == 3 else {}
        payload = body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        for name, value in headers.items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(payload)

    do_GET = _respond
    do_POST = _respond
    do_PUT = _respond
    do_DELETE = _respond

    def log_message(self, format: str, *args: object) -> None:  # noqa: A002 - 표준 라이브러리 시그니처
        return  # 서명 거부는 무기록, 나머지 질의는 QueryRunLog 한 줄로만 쓴다.


def make_server(port: int, env_file: Path | None, *, app=None, report=None) -> ThreadingHTTPServer:
    if report is None:

        def report() -> CheckReport:
            return build_report(load(Entrypoint.QUERY, env_file=env_file))

    return ThreadingHTTPServer((HOST, port), partial(_Handler, report=report, app=app))


def create_app(settings):
    from qello_knowledge.adapters.discord.webhook import DiscordWebhook
    from qello_knowledge.config.loader import SecretValue
    from qello_knowledge.discord.access import AccessPolicy
    from qello_knowledge.indexer.embedding import security_outgoing_check
    from qello_knowledge.query.jobs import QueryJobs
    from qello_knowledge.query.pipeline import configured_pipeline
    from qello_knowledge.security.policy import load_policy
    from qello_knowledge.sources.config import load_sources

    configs, issues = load_sources(Path("config/sources.toml"))
    policy, policy_issues = (
        load_policy(Path("config/security_exceptions.toml"), configs) if not issues else (None, issues)
    )
    if issues or policy_issues:
        raise ValueError("질의 정책 설정 오류")
    source = {}
    for name in ("DATABASE_URL", "CLOUDFLARE_ACCOUNT_ID"):
        value = settings.get(name)
        source[name] = value.reveal() if isinstance(value, SecretValue) else str(value)
    pipeline = configured_pipeline(settings, source, policy)
    webhook = DiscordWebhook(str(settings.get("DISCORD_APPLICATION_ID")))
    jobs = QueryJobs(
        pipeline=pipeline,
        deliver=lambda job, reply: webhook.deliver(job.interaction.token, reply, deadline=job.notice_deadline),
        workers=int(settings.get("QK_QUERY_WORKERS")),
        queue_size=int(settings.get("QK_QUERY_QUEUE_SIZE")),
        start_wait=int(settings.get("QK_QUERY_START_WAIT_SECONDS")),
        min_start=int(settings.get("QK_QUERY_MIN_START_SECONDS")),
        deadline_seconds=int(settings.get("QK_QUERY_DEADLINE_SECONDS")),
        notice_grace=int(settings.get("QK_QUERY_NOTICE_GRACE_SECONDS")),
        on_finished=write_run_log,
    )
    access = AccessPolicy(
        settings.get("QK_DISCORD_GUILD_ID"),
        tuple(filter(None, settings.get("QK_DISCORD_ALLOWED_CHANNELS").split(","))),
        tuple(filter(None, settings.get("QK_DISCORD_ALLOWED_ROLES").split(","))),
    )
    check = security_outgoing_check(policy)
    return DiscordApp(
        str(settings.get("DISCORD_PUBLIC_KEY")),
        jobs,
        access_check=access.check,
        outgoing_check=lambda item: not check(item.question or "", None),
        on_response=write_run_log,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="qk-query", description="질의응답 진입점")
    sub = parser.add_subparsers(dest="command", required=True)
    add_check_options(sub.add_parser("check", help="설정만 점검한다. 외부 호출 없음"))
    register = sub.add_parser("register-commands", help="서버 한정 명령을 덮어써 등록한다")
    register.add_argument("--env-file", type=Path, default=Path(".env"))
    register.add_argument("--dry-run", action="store_true")
    serve = sub.add_parser("serve", help=f"로컬 HTTP 서버를 {HOST}에 띄운다")
    serve.add_argument("--port", type=int, default=8787)
    serve.add_argument("--env-file", type=Path, default=Path(".env"))
    args = parser.parse_args(argv)

    if args.command == "check":
        code, _ = run_check(Entrypoint.QUERY, args)
        return code
    if args.command == "register-commands":
        return _register_commands(args)

    settings = load(Entrypoint.QUERY, env_file=args.env_file)
    report = build_report(settings)
    if not report.ok:
        print(report.to_text(), file=sys.stderr)
        return 2
    for warning in report.warnings:
        print(f"WARNING {warning}", file=sys.stderr)
    try:
        require_backend()
        app = create_app(settings)
    except (RuntimeError, ValueError, OSError):
        print("질의 서비스 시작 설정 오류", file=sys.stderr)
        return 2
    server = None
    try:
        server = make_server(args.port, args.env_file, app=app, report=lambda: report)
        print(f"qk-query: http://{HOST}:{server.server_port}/healthz", flush=True)
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        if server is not None:
            server.server_close()
        app.jobs.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
