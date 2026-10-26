"""Worker 중계 판단. Workers SDK 없이 표준 라이브러리만 쓴다."""

import json
import math
import re
from dataclasses import dataclass, field

MAX_BODY_BYTES = 65536
SIGNATURE_HEADERS = ("X-Signature-Ed25519", "X-Signature-Timestamp")


def signature_headers(headers) -> dict[str, str]:
    lowered = {k.lower(): v for k, v in headers.items()}
    return {name: lowered.get(name.lower(), "") for name in SIGNATURE_HEADERS}


def precheck(body: bytes, headers, now: float) -> int | None:
    if len(body) > MAX_BODY_BYTES:
        return 413
    values = signature_headers(headers)
    timestamp = values[SIGNATURE_HEADERS[1]]
    if not isinstance(timestamp, str) or not re.fullmatch(r"[0-9]{1,20}", timestamp):
        return 401
    signature = values[SIGNATURE_HEADERS[0]]
    if not isinstance(signature, str) or not re.fullmatch(r"[0-9a-fA-F]{128}", signature):
        return 401
    if not math.isfinite(now) or abs(now - int(timestamp)) > 300:
        return 401
    return None


def _ping(body: bytes) -> bool:
    try:
        payload = json.loads(body)
        return isinstance(payload, dict) and type(payload.get("type")) is int and payload["type"] == 1
    except (ValueError, UnicodeError, RecursionError):
        return False


def fallback() -> dict:
    return {
        "type": 4,
        "data": {
            "content": "지금은 답할 수 없습니다. 잠시 후 다시 질문해 주세요.",
            "flags": 64,
            "allowed_mentions": {"parse": []},
        },
    }


@dataclass(frozen=True)
class RelayRequest:
    path: str
    body: bytes = field(repr=False)
    headers: dict = field(repr=False)


@dataclass(frozen=True)
class RelayResult:
    body: dict = field(repr=False)
    log_kind: str
    run_id: str | None = None

    def log(self, elapsed_ms: int) -> dict:
        return {"kind": self.log_kind, "elapsed_ms": elapsed_ms}


def relay_plan(body: bytes, headers) -> tuple[RelayRequest, ...]:
    return () if _ping(body) else (RelayRequest("/discord/interactions", body, signature_headers(headers)),)


def relay_response(original: bytes, status: int | None, body: bytes, headers) -> RelayResult:
    if _ping(original):
        return RelayResult({"type": 1}, "relayed")
    if status == 200:
        try:
            payload = json.loads(body)
            if isinstance(payload, dict) and payload.get("type") in (1, 4, 5):
                run_id = next((v for k, v in headers.items() if k.lower() == "x-qk-run"), None)
                return RelayResult(payload, "relayed", run_id if payload["type"] == 5 else None)
        except (ValueError, UnicodeError, RecursionError):
            pass
    return RelayResult(fallback(), "relay_failed")


def start_request(result: RelayResult, headers) -> RelayRequest | None:
    if result.run_id is None:
        return None
    return RelayRequest(
        "/discord/interactions/start", json.dumps({"run_id": result.run_id}).encode(), signature_headers(headers)
    )
