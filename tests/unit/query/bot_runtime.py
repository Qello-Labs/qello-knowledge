"""US1의 대기열·첫 응답 시험. 외부 연결 없이 명시적으로 작업을 실행한다."""

from concurrent.futures import Future
from types import SimpleNamespace

from qello_knowledge.adapters.discord.webhook import DiscordWebhook
from qello_knowledge.config.check import build_report
from qello_knowledge.config.loader import load
from qello_knowledge.config.registry import Entrypoint
from qello_knowledge.domain.discord import QueryStage, RenderedReply
from qello_knowledge.query.app import DiscordApp, handle
from qello_knowledge.query.jobs import QueryJobs
from tests.unit.discord.bot_builders import APPLICATION, CHANNEL, FakeClock, FakeDiscord, signing_key
from tests.unit.fakes import valid_environ


class BotExecutor:
    def __init__(self):
        self.pending = []

    def submit(self, function, *args):
        future = Future()
        self.pending.append((future, function, args))
        return future

    def run_next(self):
        future, function, args = self.pending.pop(0)
        result = function(*args)
        future.set_result(result)
        return result

    def shutdown(self, **kwargs):
        pass


def bot_runtime(*, script=(), pipeline=None, **options):
    clock = FakeClock()
    compute, deliveries = BotExecutor(), BotExecutor()
    fake = FakeDiscord(script, clock=clock)
    webhook = DiscordWebhook(APPLICATION, transport=fake, clock=clock.now, sleep=clock.advance)
    calls = []

    def run(job, stage):
        calls.append(job.run_id)
        stage(QueryStage.GENERATING)
        return RenderedReply(("합성 답변",), job.interaction.private)

    jobs = QueryJobs(
        pipeline=pipeline or run,
        deliver=lambda job, reply: webhook.deliver(job.interaction.token, reply, deadline=job.notice_deadline),
        clock=clock.now,
        executor=compute,
        delivery_executor=deliveries,
        autostart=False,
        **options,
    )
    key = signing_key()
    app = DiscordApp(key.public_key, jobs, wall_clock=lambda: 1000)
    settings = load(
        Entrypoint.QUERY, environ={**valid_environ(), "QK_DISCORD_ALLOWED_CHANNELS": CHANNEL}, env_file=None
    )
    return SimpleNamespace(
        clock=clock,
        compute=compute,
        deliveries=deliveries,
        fake=fake,
        jobs=jobs,
        app=app,
        key=key,
        calls=calls,
        report=build_report(settings),
    )


def bot_request(runtime, body, path="/discord/interactions", headers=None):
    return handle(
        "POST",
        path,
        lambda: runtime.report,
        body=body,
        headers=headers or runtime.key.sign(body, "1000"),
        app=runtime.app,
    )
