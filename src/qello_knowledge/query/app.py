"""질의응답 요청 처리. 로컬 서버와 Workers 겉껍질이 같은 함수를 부른다(research R-11)."""

from __future__ import annotations

import json
from collections.abc import Callable
from time import time

from qello_knowledge.config.check import CheckReport
from qello_knowledge.discord.interactions import notice, parse, pong
from qello_knowledge.discord.notices import FIXED_NOTICES
from qello_knowledge.discord.relay import MAX_BODY_BYTES, signature_headers
from qello_knowledge.discord.signature import verify
from qello_knowledge.domain.discord import InteractionKind

Response = tuple[int, str]


def handle(method: str, path: str, report: Callable[[], CheckReport], *, body: bytes = b"", headers=None, app=None):
    """`GET /healthz`만 처리한다. 실제 질의응답은 후속 명세(QK-BOT-001 등)가 채운다."""
    if path in ("/discord/interactions", "/discord/interactions/start"):
        if method != "POST":
            return 405, "", {}
        return app.respond(path, body, headers or {}) if app is not None else (503, "", {})
    if path != "/healthz":
        return 404, '{"error": "not found"}'
    if method != "GET":
        return 405, '{"error": "method not allowed"}'
    result = report()
    return (200 if result.ok else 503), result.to_json()


class DiscordApp:
    def __init__(
        self, public_key, jobs, *, wall_clock=time, access_check=lambda item: True, outgoing_check=lambda item: True
    ):
        self.public_key, self.jobs, self.wall_clock = public_key, jobs, wall_clock
        # US1의 조립 자리. 실제 접근 제어와 처리 전 질문 검사는 T041에서 연결한다.
        self.access_check, self.outgoing_check = access_check, outgoing_check

    def respond(self, path, body, headers):
        if len(body) > MAX_BODY_BYTES:
            return 413, "", {}
        signed = signature_headers(headers)
        signature, timestamp = signed["X-Signature-Ed25519"], signed["X-Signature-Timestamp"]
        if path.endswith("/start"):
            try:
                payload = json.loads(body)
                run_id = payload.get("run_id") if isinstance(payload, dict) else None
                started = isinstance(run_id, str) and self.jobs.start(run_id, signature, timestamp)
            except (ValueError, UnicodeError, RecursionError, TypeError):
                started = False
            return (204 if started else 409), "", {}
        if not verify(self.public_key, signature, timestamp, body, self.wall_clock()):
            return 401, "", {}
        item = parse(body)
        if item.kind is InteractionKind.PING:
            response = pong()
        elif item.kind is not InteractionKind.COMMAND:
            response = notice(FIXED_NOTICES["unsupported"])
        elif not self.access_check(item):
            response = notice(FIXED_NOTICES["access"])
        elif not self.outgoing_check(item):
            response = notice(FIXED_NOTICES["secret"])
        else:
            response = self.jobs.reserve(item, signature, timestamp)
        return (
            200,
            json.dumps(response.to_dict(), ensure_ascii=False),
            ({"X-QK-Run": response.run_id} if response.run_id else {}),
        )
