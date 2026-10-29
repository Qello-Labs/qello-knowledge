"""질의 기록 타입의 계약과 repr 비노출."""

import json
from dataclasses import fields
from datetime import UTC, datetime

from qello_knowledge.discord.interactions import parse
from qello_knowledge.domain.discord import QueryRunLog, RenderedReply
from qello_knowledge.domain.query_log import (
    ComponentAction,
    FeedbackValue,
    PendingQuestion,
    QueryDelivery,
    QueryRecord,
    RecordStatus,
)
from tests.unit.discord.bot_builders import ask
from tests.unit.query.obs_builders import QUESTIONER, RUN


def test_enums_and_defaults():
    assert set(RecordStatus) == {
        "answered",
        "cannot_confirm",
        "retrieval_failed",
        "generation_failed",
        "outgoing_blocked",
        "timed_out",
        "not_started",
        "failed",
        "undelivered",
        "busy",
    }
    assert set(FeedbackValue) == {"up", "down"}
    assert set(ComponentAction) == {"up", "down", "keep", "skip"}
    assert RenderedReply(("합성 답변",), False).components == ()
    assert QueryDelivery(RUN).final_status is None
    item = parse(ask("합성 질문 1"))
    assert item.user_id is None and item.component_action is None and item.component_run_id is None
    log = json.loads(QueryRunLog(RUN, "allowed", False, "answered").to_json())
    assert log.pop("record") == "off"
    assert set(log) == {f.name for f in fields(QueryRunLog)} - {"record"}


def test_sensitive_repr():
    record = QueryRecord(RUN, datetime.now(UTC), QUESTIONER, False, RecordStatus.ANSWERED)
    pending = PendingQuestion(RUN, QUESTIONER, "합성 질문 1", "waiting", 10)
    assert QUESTIONER not in repr(record) + repr(pending)
    assert "합성 질문 1" not in repr(pending)
