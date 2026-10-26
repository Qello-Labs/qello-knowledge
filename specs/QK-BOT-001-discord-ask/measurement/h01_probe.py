"""H01(M-01)·H04(M-02) 시험 질의 서비스. Worker 중계 경로만 확인하고 검색·생성·DB·Workers AI를 부르지 않는다.

질의 서비스와 같은 `127.0.0.1:8787`에서 받는다. `/ask` 요청에는 나만 보기 지연 응답과 `X-QK-Run`을 주고,
그 실행의 시작 확인이 오면 `204` 뒤 원 메시지를 연결 확인 문구로 한 번 갱신한다. 서명은 다시 검사한다(research R-04).
`나만_보기`를 켠 요청에는 허용 밖 채널처럼 시작 확인 없는 즉시 안내(type 4)로 답한다(H04 거부 경로 흉내).
기록에는 경로·상태·경과 시간만 남기고 본문·토큰·서명을 남기지 않는다.

실행(공유 인스턴스, 비특권 임시 실행. 값은 기록하지 않는다):

    systemd-run --unit qk-h01-probe --uid nobody --gid nogroup \\
      --setenv DISCORD_PUBLIC_KEY=<discord-public-key> --setenv DISCORD_APPLICATION_ID=<application-id> \\
      /usr/bin/python3 <h01_probe.py>

서명 검사에는 시스템 `python3-cryptography`를 쓴다. 없으면 시작하지 않는다.
"""

from __future__ import annotations

import json
import os
import secrets
import sys
import threading
from http.client import HTTPSConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from time import monotonic, time

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

HOST, PORT = "127.0.0.1", 8787
MAX_BODY_BYTES = 65536
MAX_RUNS = 40
NOTICE = "H01 연결 확인: Worker → Tunnel → 시험 서비스 중계와 시작 확인이 동작했습니다. (시험 응답)"
DENY_NOTICE = "H04 거부 경로 시험: 시작 확인 없는 즉시 안내입니다. (시험 응답)"


def log(**fields) -> None:
    print(json.dumps(fields, ensure_ascii=False), flush=True)


class Probe:
    def __init__(self, public_key: str, application_id: str):
        self.key = Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key))
        self.application_id = application_id
        self.runs: dict[str, dict] = {}
        self.lock = threading.Lock()

    def verify(self, signature: str, timestamp: str, body: bytes) -> bool:
        try:
            if not timestamp.isdigit() or abs(time() - int(timestamp)) > 300:
                return False
            self.key.verify(bytes.fromhex(signature), timestamp.encode() + body)
            return True
        except (InvalidSignature, ValueError):
            return False

    def interaction(self, body: bytes, signature: str, timestamp: str) -> tuple[int, dict | None, dict]:
        if not self.verify(signature, timestamp, body):
            return 401, None, {}
        payload = json.loads(body)
        if payload.get("type") == 1:
            return 200, {"type": 1}, {}
        if payload.get("type") != 2 or str(payload.get("application_id")) != self.application_id:
            return 200, {"type": 4, "data": {"content": "지원하지 않는 요청입니다.", "flags": 64}}, {}
        options = (payload.get("data") or {}).get("options") or []
        if any(item.get("name") == "나만_보기" and item.get("value") is True for item in options):
            return 200, {"type": 4, "data": {"content": DENY_NOTICE, "flags": 64}}, {}
        run_id = f"h01-{secrets.token_hex(4)}"
        with self.lock:
            if len(self.runs) >= MAX_RUNS:
                return 200, {"type": 4, "data": {"content": "H01 시험 한도를 넘었습니다.", "flags": 64}}, {}
            self.runs[run_id] = {"token": payload["token"], "signature": signature, "started": False}
        return 200, {"type": 5, "data": {"flags": 64}}, {"X-QK-Run": run_id}

    def start(self, body: bytes, signature: str) -> int:
        try:
            run_id = json.loads(body).get("run_id")
        except (ValueError, AttributeError):
            return 409
        with self.lock:
            run = self.runs.get(run_id) if isinstance(run_id, str) else None
            if run is None or run["started"] or not secrets.compare_digest(run["signature"], signature):
                return 409
            run["started"] = True
            token = run.pop("token")
        threading.Thread(target=self.update, args=(run_id, token), daemon=True).start()
        return 204

    def update(self, run_id: str, token: str) -> None:
        started = monotonic()
        status = None
        try:
            connection = HTTPSConnection("discord.com", timeout=10)
            connection.request(
                "PATCH",
                f"/api/v10/webhooks/{self.application_id}/{token}/messages/@original",
                body=json.dumps({"content": NOTICE, "allowed_mentions": {"parse": []}}).encode(),
                headers={"Content-Type": "application/json", "User-Agent": "DiscordBot (qello-knowledge h01 probe, 0)"},
            )
            status = connection.getresponse().status
            connection.close()
        except OSError as exc:
            status = type(exc).__name__
        log(kind="update", run_id=run_id, status=status, elapsed_ms=int((monotonic() - started) * 1000))


def make_handler(probe: Probe):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *args):
            # 기본 접근 로그(경로·주소)를 끈다.
            return

        def reply(self, status: int, payload: dict | None = None, headers: dict | None = None) -> None:
            data = b"" if payload is None else json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(status)
            for name, value in (headers or {}).items():
                self.send_header(name, value)
            if payload is not None:
                self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/healthz":
                self.reply(200, {"probe": "h01"})
            else:
                self.reply(404)

        def do_POST(self):
            started = monotonic()
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_BODY_BYTES:
                self.reply(413)
                return
            body = self.rfile.read(length)
            signature = self.headers.get("X-Signature-Ed25519") or ""
            timestamp = self.headers.get("X-Signature-Timestamp") or ""
            if self.path == "/discord/interactions":
                try:
                    status, payload, headers = probe.interaction(body, signature, timestamp)
                except (ValueError, KeyError, TypeError):
                    status, payload, headers = 400, None, {}
                self.reply(status, payload, headers)
                kind = f"interaction_{payload.get('type')}" if payload else "interaction"
            elif self.path == "/discord/interactions/start":
                status = probe.start(body, signature)
                self.reply(status)
                kind = "start"
            else:
                status, kind = 404, "unknown"
                self.reply(status)
            log(kind=kind, status=status, elapsed_ms=int((monotonic() - started) * 1000))

    return Handler


def main() -> int:
    public_key = os.environ.get("DISCORD_PUBLIC_KEY", "")
    application_id = os.environ.get("DISCORD_APPLICATION_ID", "")
    if len(public_key) != 64 or not application_id.isdigit():
        print("DISCORD_PUBLIC_KEY와 DISCORD_APPLICATION_ID가 필요합니다", file=sys.stderr)
        return 2
    server = ThreadingHTTPServer((HOST, PORT), make_handler(Probe(public_key, application_id)))
    log(kind="listening", port=PORT)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
