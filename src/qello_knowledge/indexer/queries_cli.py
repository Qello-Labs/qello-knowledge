"""관리 연결만 쓰는 queries 명령. 입력 값을 오류 문구에 넣지 않는다."""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

from qello_knowledge.config.loader import merge_sources, read_env_file

PENDING_NOTICE = (
    "질의 서비스 메모리의 원문 대기(최대 1시간)는 이 명령이 지우지 못합니다. "
    "1시간 뒤 다시 실행하거나 질의 서비스를 다시 시작하세요."
)


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        self.exit(2, "질의 기록 명령 인자 오류\n")


def postgres_queries(source):
    from qello_knowledge.adapters.postgres.connection import database_url
    from qello_knowledge.adapters.postgres.query_log_admin import PostgresQueryLogAdmin

    return PostgresQueryLogAdmin(database_url(source))


def main(argv, *, stdin=None, factory=postgres_queries):
    parser = _Parser(prog="qk-index queries")
    sub = parser.add_subparsers(dest="action", required=True)
    for name in ("erase-user", "erase-texts", "report", "export"):
        command = sub.add_parser(name)
        if name.startswith("erase-"):
            command.add_argument("--confirm", action="store_true")
        elif name == "report":
            command.add_argument("--since", required=True)
            command.add_argument("--until", required=True)
            command.add_argument("--json", action="store_true")
        else:
            command.add_argument("--out", type=Path, required=True)
            command.add_argument("--all", action="store_true")
        command.add_argument("--env-file", type=Path, default=Path(".env"))
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code)
    since = until = None
    try:
        if args.action == "report":
            since, until = _date(args.since), _date(args.until)
            if since > until:
                raise ValueError("date_order")
        if args.action == "export":
            _check_destination(args.out)
    except (ValueError, OSError):
        print("질의 기록 명령 인자 오류", file=sys.stderr)
        return 2
    user = None
    if args.action == "erase-user":
        try:
            user = (stdin if stdin is not None else sys.stdin).readline(23).removesuffix("\n").removesuffix("\r")
        except (OSError, UnicodeError, ValueError):
            print("사용자 식별자를 읽을 수 없습니다.", file=sys.stderr)
            return 2
        if re.fullmatch(r"[0-9]{17,20}", user) is None:
            print("사용자 식별자 형식 오류", file=sys.stderr)
            return 2
    admin = None
    code = 4
    try:
        source = merge_sources(os.environ, read_env_file(args.env_file))
        admin = factory(source)
        code = _execute(args, source, admin, user, since, until)
    except Exception:
        print("질의 기록 저장소를 사용할 수 없습니다.", file=sys.stderr)
    if admin is not None:
        try:
            admin.close()
        except Exception:
            print("질의 기록 저장소 연결 정리 실패", file=sys.stderr)
            code = 4
    return code


def _execute(args, source, admin, user, since, until):
    if args.action == "report":
        try:
            retain = _date(source["QK_QUERY_TEXT_RETAIN_UNTIL"]) if source.get("QK_QUERY_TEXT_RETAIN_UNTIL") else None
            reserve = int(source.get("QK_EMBED_QUERY_RESERVE", "3000"))
            if reserve <= 0:
                raise ValueError("reserve")
        except ValueError:
            print("질의 기록 설정 오류", file=sys.stderr)
            return 2
        result = admin.report(since, until, query_reserve=reserve, retain_until=retain)
        print(json.dumps(result, ensure_ascii=False, separators=(",", ":")) if args.json else _report_text(result))
    elif args.action == "export":
        rows = admin.export_rows(all_rows=args.all)
        try:
            _write_export(args.out, rows)
        except OSError:
            print("내보내기 파일을 만들 수 없습니다.", file=sys.stderr)
            return 2
        print(f"exported={len(rows)}")
        print(
            "저장소에 커밋하지 마세요. 평가 세트로 옮길 때 개인 정보와 비공개 문서 원문을 지우세요. "
            "원문 기록을 지울 때 이 파일도 지우세요."
        )
    else:
        result = (
            admin.erase_user(user, confirm=args.confirm)
            if args.action == "erase-user"
            else admin.erase_texts(confirm=args.confirm)
        )
        print(json.dumps(result, separators=(",", ":")))
        print(PENDING_NOTICE)
        if args.action == "erase-texts":
            print("내보낸 파일도 지우세요.")
    return 0


def _date(value):
    if re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
        raise ValueError("date_format")
    return date.fromisoformat(value)


def _check_destination(path):
    # git 읽기 전용 조회. 현재 작업 트리 밖이어야 하며 심볼릭 링크의 대상도 확인한다.
    result = subprocess.run(
        ["/usr/bin/git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise ValueError("worktree_unknown")
    root = Path(result.stdout.strip()).resolve()
    if path.resolve().is_relative_to(root) or path.exists() or path.is_symlink():
        raise ValueError("destination")


def _write_export(path, rows):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as out:
            for row in rows:
                out.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _report_text(report):
    return "\n".join(f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in report.items())
