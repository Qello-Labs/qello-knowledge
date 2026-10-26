"""질의응답 요청 처리. 로컬 서버와 Workers 겉껍질이 같은 함수를 부른다(research R-11)."""

from __future__ import annotations

import json
import secrets
from collections.abc import Callable
from datetime import UTC, datetime
from time import time

from qello_knowledge.config.check import CheckReport
from qello_knowledge.discord.interactions import notice, parse, pong
from qello_knowledge.discord.notices import FIXED_NOTICES, failure_notice
from qello_knowledge.discord.relay import MAX_BODY_BYTES, signature_headers
from qello_knowledge.discord.signature import verify
from qello_knowledge.domain.discord import AccessDecision, InteractionKind, QueryRunLog

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
        self,
        public_key,
        jobs,
        *,
        wall_clock=time,
        access_check=lambda item: True,
        outgoing_check=lambda item: True,
        on_response=None,
    ):
        self.public_key, self.jobs, self.wall_clock = public_key, jobs, wall_clock
        self.access_check, self.outgoing_check = access_check, outgoing_check
        self.on_response = on_response

    def respond(self, path, body, headers):
        started_at = self.jobs.now()
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
        access, status, run_id = "not_checked", "unsupported", None
        if item.kind is InteractionKind.PING:
            response = pong()
        elif item.kind is not InteractionKind.COMMAND:
            response = notice(FIXED_NOTICES["unsupported"])
        else:
            try:
                verdict = self.access_check(item)
                allowed = verdict in (True, AccessDecision.ALLOWED)
                access = verdict.value if isinstance(verdict, AccessDecision) else ("allowed" if allowed else "denied")
                if not allowed:
                    status = "access_denied"
                    response = notice(FIXED_NOTICES["access"])
                elif not self.outgoing_check(item):
                    status = "outgoing_blocked"
                    response = notice(FIXED_NOTICES["secret"])
                else:
                    response = self.jobs.reserve(item, signature, timestamp)
                    status = "duplicate" if response.data.get("content") == FIXED_NOTICES["duplicate"] else "busy"
            except Exception:
                status = "failed"
                run_id = f"q-{datetime.now(UTC):%Y%m%dT%H%M%S}-{secrets.token_hex(4)}"
                response = notice(failure_notice("unexpected", run_id))
        if response.type == 4 and self.on_response is not None:
            run_id = run_id or f"q-{datetime.now(UTC):%Y%m%dT%H%M%S}-{secrets.token_hex(4)}"
            try:
                self.on_response(
                    QueryRunLog(
                        run_id,
                        access,
                        True,
                        status,
                        failure=status,
                        timings_ms={
                            "first_response": max(0, int((self.jobs.now() - started_at) * 1000)),
                            "retrieve": 0,
                            "generate": 0,
                            "deliver": 0,
                        },
                        calls={"retrieve": 0, "generate": 0, "deliver": 0},
                    )
                )
            except Exception:
                return 200, json.dumps(response.to_dict(), ensure_ascii=False), {}
        if response.run_id:
            self.jobs.record_first_response(response.run_id, (self.jobs.now() - started_at) * 1000)
        return (
            200,
            json.dumps(response.to_dict(), ensure_ascii=False),
            ({"X-QK-Run": response.run_id} if response.run_id else {}),
        )
