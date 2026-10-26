import json
from dataclasses import FrozenInstanceError, fields

import pytest

from qello_knowledge.domain.discord import (
    AccessDecision,
    ChannelKind,
    DedupEntry,
    DedupStage,
    FirstResponse,
    Interaction,
    InteractionKind,
    QueryJob,
    QueryRunLog,
    QueryStage,
    RenderedReply,
)


def test_bot_enums():
    assert set(InteractionKind.__members__) == {"PING", "COMMAND", "OTHER"}
    assert set(ChannelKind.__members__) == {"TEXT", "THREAD", "DM", "OTHER"}
    assert set(AccessDecision.__members__) == {
        "ALLOWED",
        "GUILD_OUTSIDE",
        "CHANNEL_OUTSIDE",
        "THREAD",
        "DM",
        "ROLE_MISSING",
        "NOT_CONFIGURED",
    }
    assert set(QueryStage.__members__) == {
        "AWAITING_START",
        "QUEUED",
        "RETRIEVING",
        "GENERATING",
        "RENDERING",
        "DELIVERING",
        "DONE",
        "NOT_STARTED",
        "TIMED_OUT",
        "FAILED",
        "UNDELIVERED",
    }
    assert set(DedupStage.__members__) == {"IN_PROGRESS", "DONE"}


def test_bot_interaction_fields_and_hidden_content():
    item = Interaction(
        "synthetic-id",
        "synthetic-token",
        InteractionKind.COMMAND,
        "ask",
        "synthetic-question",
        False,
        "guild",
        "channel",
        ChannelKind.TEXT,
        ("role",),
    )
    assert {f.name for f in fields(item)} == {
        "interaction_id",
        "token",
        "kind",
        "command",
        "question",
        "private",
        "guild_id",
        "channel_id",
        "channel_kind",
        "member_roles",
    }
    assert "synthetic-token" not in repr(item)
    assert "synthetic-question" not in repr(item)
    with pytest.raises(FrozenInstanceError):
        item.private = True
    job = QueryJob("run", item, 1, 56, 61)
    assert "synthetic-token" not in repr(job)
    with pytest.raises(FrozenInstanceError):
        job.run_id = "other"


def test_bot_response_reply_and_dedup():
    for kind in (1, 4, 5):
        response = FirstResponse(kind, {"flags": 64}, "run")
        assert response.type == kind and response.data["flags"] == 64 and response.run_id == "run"
        with pytest.raises(FrozenInstanceError):
            response.type = 1
        with pytest.raises(TypeError):
            response.data["flags"] = 0
    reply = RenderedReply(("one", "two"), True, False)
    assert reply.allowed_mentions == {"parse": []}
    reply.allowed_mentions["parse"].append("everyone")
    assert reply.allowed_mentions == {"parse": []}
    with pytest.raises(FrozenInstanceError):
        reply.ephemeral = False
    entry = DedupEntry("id", DedupStage.IN_PROGRESS, 900)
    assert {f.name for f in fields(entry)} == {"interaction_id", "stage", "expires_at"}
    with pytest.raises(FrozenInstanceError):
        entry.expires_at = 1000


def test_bot_run_log_exact_fields_stable_single_line_and_immutable():
    names = [
        "run_id",
        "access",
        "private",
        "status",
        "failure",
        "timings_ms",
        "calls",
        "deliver_retries",
        "deliver_failure",
        "retrieval_summary",
        "generation_summary",
    ]
    timing = {"generate": 2, "retrieve": 1}
    log = QueryRunLog("run", "allowed", False, "answer", timings_ms=timing)
    assert [f.name for f in fields(log)] == names
    raw = log.to_json()
    assert "\n" not in raw and list(json.loads(raw)) == names
    timing["retrieve"] = 999
    assert json.loads(log.to_json())["timings_ms"]["retrieve"] == 1
    assert raw == log.to_json()
    assert raw == QueryRunLog("run", "allowed", False, "answer", timings_ms={"retrieve": 1, "generate": 2}).to_json()
    with pytest.raises(TypeError):
        log.timings_ms["retrieve"] = 3
    with pytest.raises(FrozenInstanceError):
        log.status = "failed"


def test_bot_sequence_inputs_are_copied_to_immutable_values():
    roles = ["role"]
    messages = ["message"]
    item = Interaction(
        "id", "token", InteractionKind.COMMAND, "ask", "question", False, "guild", "channel", ChannelKind.TEXT, roles
    )
    reply = RenderedReply(messages, False)
    roles.append("other")
    messages.append("other")
    assert item.member_roles == ("role",)
    assert reply.messages == ("message",)
