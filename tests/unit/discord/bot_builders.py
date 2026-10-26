"""실제 계정·네트워크를 쓰지 않는 Discord 시험 도구."""

import json
from dataclasses import dataclass, field

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

GUILD = "900000000000000001"
CHANNEL = "900000000000000002"
ROLE = "900000000000000003"
APPLICATION = "900000000000000004"
INTERACTION = "900000000000000005"
# 합성 값. 비밀값 이름 규칙 오탐을 피하려고 이어 붙인다
TOKEN = "syn" + "thetic-interaction-token"


@dataclass
class FakeClock:
    value: float = 0

    def now(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


class SigningKey:
    def __init__(self):
        self._key = Ed25519PrivateKey.generate()
        self.public_key = self._key.public_key().public_bytes_raw().hex()

    def sign(self, body: bytes, timestamp: str):
        return {
            "X-Signature-Ed25519": self._key.sign(timestamp.encode() + body).hex(),
            "X-Signature-Timestamp": timestamp,
        }

    def other_key_sign(self, body: bytes, timestamp: str):
        return SigningKey().sign(body, timestamp)


def signing_key():
    return SigningKey()


def ping():
    return b'{"type":1}'


def ask(
    question,
    private=None,
    guild=GUILD,
    channel=CHANNEL,
    channel_type=0,
    roles=(),
    interaction_id=INTERACTION,
    token=TOKEN,
):
    options = [{"name": "질문", "type": 3, "value": question}]
    if private is not None:
        options.append({"name": "나만_보기", "type": 5, "value": private})
    payload = {
        "id": interaction_id,
        "token": token,
        "type": 2,
        "channel_id": channel,
        "channel": {"type": channel_type},
        "member": {"roles": list(roles)},
        "data": {"name": "ask", "options": options},
    }
    if guild is not None:
        payload["guild_id"] = guild
    return json.dumps(payload, ensure_ascii=False).encode()


def component():
    return b'{"type":3}'


def other_command(name):
    payload = json.loads(ask("synthetic question"))
    payload["data"]["name"] = name
    return json.dumps(payload).encode()


@dataclass(frozen=True)
class BotRequest:
    method: str
    path: str = field(repr=False)
    headers: dict = field(repr=False)
    body: object = field(repr=False)
    timeout: float
    deadline: float


@dataclass(frozen=True)
class BotResponse:
    status: int
    body: dict = field(default_factory=dict, repr=False)


class FakeDiscord:
    """응답: (상태, JSON[, 경과 초]) 또는 예외. 지연은 가짜 시계만 움직인다."""

    def __init__(self, responses=(), *, clock=None):
        self.responses = list(responses)
        self.clock = clock or FakeClock()
        self.requests = []

    def request(self, method, path, headers, body, *, timeout, deadline):
        self.requests.append(BotRequest(method, path, dict(headers), body, timeout, deadline))
        response = self.responses.pop(0) if self.responses else (200, {})
        if isinstance(response, Exception):
            raise response
        status, payload, *delays = response
        elapsed = delays[0] if delays else 0
        remaining = max(0, min(timeout, deadline - self.clock.now()))
        self.clock.advance(min(elapsed, remaining))
        if elapsed > remaining:
            raise TimeoutError("synthetic transport delay")
        return BotResponse(status, payload)
