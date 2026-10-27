"""원본 바이트의 해석과 첫 응답 JSON. 허용 범위와 작업 상태를 판단하지 않는다."""

import json

from qello_knowledge.domain.discord import ChannelKind, FirstResponse, Interaction, InteractionKind

MAX_BODY_BYTES = 64 * 1024
SIGNATURE_HEADERS = ("X-Signature-Ed25519", "X-Signature-Timestamp")


def signature_headers(headers) -> dict[str, str]:
    """서명 헤더 두 개를 대소문자와 관계없이 꺼낸다. 없으면 빈 문자열이다."""
    lowered = {k.lower(): v for k, v in headers.items()}
    return {name: lowered.get(name.lower(), "") for name in SIGNATURE_HEADERS}


def _other() -> Interaction:
    return Interaction("", "", InteractionKind.OTHER, None, None, True, None, None, ChannelKind.OTHER, ())


def parse(body: bytes) -> Interaction:
    if len(body) > MAX_BODY_BYTES:
        return _other()
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeError, RecursionError):
        return _other()
    if not isinstance(payload, dict) or type(payload.get("type")) is not int:
        return _other()
    if payload["type"] == 1:
        return Interaction("", "", InteractionKind.PING, None, None, False, None, None, ChannelKind.OTHER, ())
    if payload["type"] != 2:
        return _other()
    data = payload.get("data")
    channel = payload.get("channel")
    member = payload.get("member", {})
    if not isinstance(data, dict) or data.get("name") != "ask":
        return _other()
    if not isinstance(channel, dict) or not isinstance(member, dict):
        return _other()
    if not all(isinstance(payload.get(k), str) and payload[k] for k in ("id", "token", "channel_id")):
        return _other()
    guild = payload.get("guild_id")
    if guild is not None and (not isinstance(guild, str) or not guild):
        return _other()
    options = data.get("options")
    if not isinstance(options, list):
        return _other()
    arguments = {}
    for option in options:
        if not isinstance(option, dict) or not isinstance(option.get("name"), str) or "value" not in option:
            return _other()
        name = option["name"]
        if name in arguments:
            return _other()
        arguments[name] = option["value"]
    question = arguments.get("질문")
    if not isinstance(question, str):
        return _other()
    private = arguments.get("나만_보기", False)
    private = private if type(private) is bool else True
    roles = member.get("roles", [])
    if not isinstance(roles, list) or not all(isinstance(role, str) for role in roles):
        return _other()
    kind = channel.get("type")
    if guild is None:
        channel_kind = ChannelKind.DM
    elif type(kind) is int and kind in (0, 5):
        channel_kind = ChannelKind.TEXT
    elif type(kind) is int and kind in (10, 11, 12):
        channel_kind = ChannelKind.THREAD
    else:
        channel_kind = ChannelKind.OTHER
    return Interaction(
        payload["id"],
        payload["token"],
        InteractionKind.COMMAND,
        "ask",
        question,
        private,
        guild,
        payload["channel_id"],
        channel_kind,
        tuple(roles),
    )


def pong() -> FirstResponse:
    return FirstResponse(1)


def notice(text: str) -> FirstResponse:
    return FirstResponse(4, {"content": text, "flags": 64, "allowed_mentions": {"parse": []}})


def deferred(private: bool, run_id: str | None = None) -> FirstResponse:
    return FirstResponse(5, {"flags": 64} if private else {}, run_id)
