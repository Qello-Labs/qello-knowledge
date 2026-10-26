"""Discord 질의 경계의 불변 값. SDK와 전송 계층을 모른다."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum
from types import MappingProxyType


class InteractionKind(StrEnum):
    PING = "ping"
    COMMAND = "command"
    OTHER = "other"


class ChannelKind(StrEnum):
    TEXT = "text"
    THREAD = "thread"
    DM = "dm"
    OTHER = "other"


class AccessDecision(StrEnum):
    ALLOWED = "allowed"
    GUILD_OUTSIDE = "guild_outside"
    CHANNEL_OUTSIDE = "channel_outside"
    THREAD = "thread"
    DM = "dm"
    ROLE_MISSING = "role_missing"
    NOT_CONFIGURED = "not_configured"


class QueryStage(StrEnum):
    AWAITING_START = "awaiting_start"
    QUEUED = "queued"
    RETRIEVING = "retrieving"
    GENERATING = "generating"
    RENDERING = "rendering"
    DELIVERING = "delivering"
    DONE = "done"
    NOT_STARTED = "not_started"
    TIMED_OUT = "timed_out"
    FAILED = "failed"
    UNDELIVERED = "undelivered"


class DedupStage(StrEnum):
    IN_PROGRESS = "in_progress"
    DONE = "done"


@dataclass(frozen=True)
class Interaction:
    interaction_id: str
    token: str = field(repr=False)
    kind: InteractionKind
    command: str | None
    question: str | None = field(repr=False)
    private: bool
    guild_id: str | None
    channel_id: str | None
    channel_kind: ChannelKind
    member_roles: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "member_roles", tuple(self.member_roles))


def _freeze(value: object) -> object:
    if isinstance(value, Mapping):
        return MappingProxyType({k: _freeze(v) for k, v in value.items()})
    if isinstance(value, (list, tuple)):
        return tuple(_freeze(v) for v in value)
    return value


def _json_value(value: object) -> object:
    if isinstance(value, Mapping):
        return {k: _json_value(value[k]) for k in sorted(value)}
    if isinstance(value, tuple):
        return [_json_value(v) for v in value]
    return value


@dataclass(frozen=True)
class FirstResponse:
    type: int
    data: Mapping[str, object] = field(default_factory=dict, repr=False)
    run_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "data", _freeze(self.data))

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {"type": self.type}
        if self.data:
            result["data"] = _json_value(self.data)
        return result


@dataclass(frozen=True)
class QueryJob:
    run_id: str
    interaction: Interaction = field(repr=False)
    received_at: float
    query_deadline: float
    notice_deadline: float


@dataclass(frozen=True)
class RenderedReply:
    messages: tuple[str, ...] = field(repr=False)
    ephemeral: bool
    body_truncated: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "messages", tuple(self.messages))

    @property
    def allowed_mentions(self) -> dict[str, list[str]]:
        return {"parse": []}


@dataclass(frozen=True)
class DedupEntry:
    interaction_id: str
    stage: DedupStage
    expires_at: float


@dataclass(frozen=True)
class QueryRunLog:
    run_id: str
    access: str
    private: bool
    status: str
    failure: str | None = None
    timings_ms: Mapping[str, object] = field(default_factory=dict)
    calls: Mapping[str, object] = field(default_factory=dict)
    deliver_retries: int = 0
    deliver_failure: str | None = None
    retrieval_summary: Mapping[str, object] = field(default_factory=dict)
    generation_summary: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("timings_ms", "calls", "retrieval_summary", "generation_summary"):
            object.__setattr__(self, name, _freeze(getattr(self, name)))

    def to_json(self) -> str:
        return json.dumps(
            {name: _json_value(getattr(self, name)) for name in self.__dataclass_fields__},
            ensure_ascii=False,
            separators=(",", ":"),
            allow_nan=False,
        )
