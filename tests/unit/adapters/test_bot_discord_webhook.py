import json
import threading
from dataclasses import fields
from time import monotonic

import pytest

from qello_knowledge.adapters.discord.webhook import DiscordWebhook, UrllibTransport
from qello_knowledge.domain.discord import QueryStage, RenderedReply
from tests.unit.discord.bot_builders import APPLICATION, GUILD, TOKEN, FakeClock, FakeDiscord
from tests.unit.synthetic_secrets import SYNTHETIC


def bot_sender(responses=(), start=0):
    clock = FakeClock(start)
    fake = FakeDiscord(responses, clock=clock)
    sender = DiscordWebhook(APPLICATION, transport=fake, clock=clock.now, sleep=clock.advance)
    return sender, fake, clock


@pytest.mark.parametrize("private", [True, False])
def test_bot_webhook_order_body_headers_and_privacy(private):
    sender, fake, _ = bot_sender([(200, {}), (204, {})])
    result = sender.deliver(TOKEN, RenderedReply(("first", "next"), private), deadline=60)
    assert result.stage is QueryStage.DONE and result.calls == 2 and result.retries == 0
    assert [(r.method, r.path) for r in fake.requests] == [
        ("PATCH", f"/api/v10/webhooks/{APPLICATION}/{TOKEN}/messages/@original"),
        ("POST", f"/api/v10/webhooks/{APPLICATION}/{TOKEN}"),
    ]
    for i, request in enumerate(fake.requests):
        expected = {"content": ("first", "next")[i], "allowed_mentions": {"parse": []}}
        if i and private:
            expected["flags"] = 64
        assert request.body == expected
        assert "Authorization" not in request.headers
        assert request.headers["User-Agent"].startswith("DiscordBot (https://github.com/Qello-Labs/qello-knowledge, ")
        assert request.headers["User-Agent"].endswith(")")
        assert request.timeout == 3


@pytest.mark.parametrize(
    "response,delay",
    [
        ((429, {"retry_after": 2}), 2),
        ((503, {}), 1),
        (OSError("synthetic secret error"), 1),
        ((404, {}), 1),
        (TimeoutError("synthetic timeout"), 1),
    ],
)
def test_bot_retry_once(response, delay):
    sender, fake, clock = bot_sender([response, (200, {})])
    result = sender.deliver(TOKEN, RenderedReply(("one",), False), deadline=60)
    assert result.stage is QueryStage.DONE and result.retries == 1 and result.calls == 2
    assert len(fake.requests) == 2 and clock.now() == delay


@pytest.mark.parametrize("response", [(400, {}), (401, {}), (403, {}), (404, {}), (429, {}), (500, {})])
def test_bot_first_message_failure_stops_followups_and_sanitizes_result(response):
    sender, fake, _ = bot_sender([response, response])
    result = sender.deliver(TOKEN, RenderedReply(("one", "two"), True), deadline=60)
    assert result.stage is QueryStage.UNDELIVERED
    assert all(r.method == "PATCH" for r in fake.requests)
    assert {f.name for f in fields(result)} == {"stage", "failure", "retries", "calls"}
    assert TOKEN not in repr(result) and "/api/" not in repr(result)
    assert result.calls <= 2 and result.retries <= 1


def test_bot_followup_404_no_retry():
    sender, fake, _ = bot_sender([(200, {}), (404, {}), (200, {})])
    result = sender.deliver(TOKEN, RenderedReply(("one", "two", "three"), True), deadline=60)
    assert result.stage is QueryStage.UNDELIVERED and result.calls == 2 and result.retries == 0
    assert len(fake.requests) == 2


@pytest.mark.parametrize("remaining,calls", [(0, 0), (0.99, 0), (1, 1), (2.75, 1)])
def test_bot_remaining_time_and_call_timeout(remaining, calls):
    sender, fake, _ = bot_sender()
    result = sender.deliver(TOKEN, RenderedReply(("one",), False), deadline=remaining)
    assert result.calls == calls
    if calls:
        assert fake.requests[0].timeout == remaining
    else:
        assert result.stage is QueryStage.UNDELIVERED


@pytest.mark.parametrize("retry_after,deadline,calls", [(2, 2.99, 1), (2, 3, 2), (900, 60, 1)])
def test_bot_retry_wait_needs_one_second_for_call(retry_after, deadline, calls):
    sender, fake, _ = bot_sender([(429, {"retry_after": retry_after}), (200, {})])
    result = sender.deliver(TOKEN, RenderedReply(("one",), False), deadline=deadline)
    assert result.calls == calls and len(fake.requests) == calls


@pytest.mark.parametrize("retry_after", ["secret-text", -1, float("nan"), float("inf"), True, None])
def test_bot_invalid_retry_after_is_not_used(retry_after):
    sender, _, clock = bot_sender([(429, {"retry_after": retry_after})])
    result = sender.deliver(TOKEN, RenderedReply(("one",), False), deadline=60)
    assert result.stage is QueryStage.UNDELIVERED and result.calls == 1 and clock.now() == 0


def test_bot_slow_attempts_stop_by_deadline():
    sender, fake, clock = bot_sender([(503, {}, 2), (200, {}, 3)])
    result = sender.deliver(TOKEN, RenderedReply(("one", "two"), False), deadline=4)
    assert result.stage is QueryStage.UNDELIVERED and clock.now() == 4
    assert result.calls == 2 and fake.requests[-1].timeout == 1


def test_bot_register_put_with_token_and_no_retry():
    sender, fake, _ = bot_sender([(204, {})])
    token = SYNTHETIC["discord-bot"]
    result = sender.register_commands(GUILD, token, [{"name": "ask"}], deadline=10)
    assert result.status == 204 and result.failure is None
    request = fake.requests[0]
    assert request.method == "PUT"
    assert request.path == f"/api/v10/applications/{APPLICATION}/guilds/{GUILD}/commands"
    assert request.headers["Authorization"] == "Bot " + token
    assert request.body == [{"name": "ask"}]
    assert token not in repr(result)


def test_bot_register_transport_error_is_sanitized(capsys):
    token = SYNTHETIC["discord-bot"]
    sender, _, _ = bot_sender([OSError(TOKEN + token)])
    result = sender.register_commands(GUILD, token, [], deadline=10)
    assert result.failure == "connection"
    assert token not in repr(result) and TOKEN not in repr(result)
    assert capsys.readouterr() == ("", "")


class BotHttpResponse:
    status = 200

    def __init__(self, release=None):
        self.closed = threading.Event()
        self.release = release

    def read(self, size):
        if self.release is not None:
            self.release.wait(0.8)
        return b"{}"

    def close(self):
        self.closed.set()


class BotOpener:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request, timeout))
        return self.response


def test_bot_urllib_serialization_and_cleanup():
    response = BotHttpResponse()
    opener = BotOpener(response)
    transport = UrllibTransport(opener=opener)
    result = transport.request(
        "PATCH", "/api/v10/test", {"User-Agent": "test"}, {"content": "synthetic"}, timeout=3, deadline=monotonic() + 3
    )
    assert result.status == 200 and result.body == {}
    request, timeout = opener.requests[0]
    assert request.full_url == "https://discord.com/api/v10/test"
    assert json.loads(request.data) == {"content": "synthetic"}
    assert request.get_method() == "PATCH" and timeout <= 3
    assert response.closed.wait(0.2)


def test_bot_urllib_whole_call_deadline_includes_body_read():
    release = threading.Event()
    response = BotHttpResponse(release)
    transport = UrllibTransport(opener=BotOpener(response))
    started = monotonic()
    try:
        with pytest.raises(TimeoutError):
            transport.request("PATCH", "/api/v10/test", {}, {}, timeout=3, deadline=started + 0.04)
        assert monotonic() - started < 0.3
    finally:
        release.set()
    assert response.closed.wait(0.5)


def test_bot_transport_rejects_paths_outside_discord_api():
    opener = BotOpener(BotHttpResponse())
    transport = UrllibTransport(opener=opener)
    with pytest.raises(ValueError, match="path"):
        transport.request("PATCH", "//outside.invalid/test", {}, {}, timeout=1, deadline=monotonic() + 1)
    assert opener.requests == []


@pytest.mark.parametrize("phase", ["open", "close"])
def test_bot_unexpected_transport_errors_cannot_escape_thread_or_expose_values(monkeypatch, phase):
    leaked = []
    monkeypatch.setattr(threading, "excepthook", lambda args: leaked.append(str(args.exc_value)))
    response = BotHttpResponse()
    opener = BotOpener(response)

    def bot_failure(*args, **kwargs):
        raise RuntimeError(TOKEN)

    monkeypatch.setattr(opener if phase == "open" else response, "open" if phase == "open" else "close", bot_failure)
    transport = UrllibTransport(opener=opener)
    with pytest.raises(OSError, match="connection"):
        transport.request("PATCH", "/api/v10/test", {}, {}, timeout=0.05, deadline=monotonic() + 0.1)
    assert leaked == []
