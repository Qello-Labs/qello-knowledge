"""평가 버튼은 답변 마지막 메시지에만 붙는다."""

import pytest

from qello_knowledge.adapters.discord.webhook import DiscordWebhook
from qello_knowledge.discord.components import feedback_buttons
from qello_knowledge.domain.discord import RenderedReply
from qello_knowledge.query.pipeline import QueryReply
from qello_knowledge.query.recorder import QueryRecorder
from tests.unit.discord.bot_builders import FakeDiscord
from tests.unit.query.bot_runtime import bot_runtime
from tests.unit.query.obs_builders import RUN, FakeQueryLog
from tests.unit.query.test_obs_query_record import run_query


@pytest.mark.parametrize("private", [False, True])
@pytest.mark.parametrize("count", [1, 3])
def test_webhook_last_message_only(private, count):
    contents = tuple("합성 답변 " + str(n) for n in range(count))
    bodies = []
    for buttons in [(), feedback_buttons(RUN)]:
        fake = FakeDiscord()
        DiscordWebhook("100000000000000003", transport=fake).deliver(
            "synthetic", RenderedReply(contents, private, components=buttons), deadline=10**12
        )
        bodies.append([request.body for request in fake.requests])
    assert len(bodies[1]) == count
    assert "components" not in bodies[1][0] if count > 1 else "components" in bodies[1][0]
    assert all("components" not in body for body in bodies[1][:-1])
    assert bodies[1][-1].pop("components") == list(feedback_buttons(RUN))
    assert bodies[0] == bodies[1]


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("status", ["answered", "cannot_confirm", "generation_failed", "outgoing_blocked"])
def test_jobs_attach_buttons_only_for_answer_status(enabled, status):
    port = FakeQueryLog()
    with QueryRecorder(lambda: port, (lambda: port) if enabled else None) as recorder:
        runtime = bot_runtime(
            recorder=recorder, pipeline=lambda *args: QueryReply(("합성 답변",), False, status=status)
        )
        run_query(runtime)
        assert ("components" in runtime.fake.requests[-1].body) == (
            enabled and status in ("answered", "cannot_confirm")
        )
        runtime.jobs.close()
