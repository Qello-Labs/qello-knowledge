"""기한 지난 Discord HTTP 시도가 스레드를 무한히 쌓지 않는지 확인한다."""

import threading
from time import monotonic

import pytest

from qello_knowledge.adapters.discord import webhook
from qello_knowledge.adapters.discord.webhook import DiscordWebhook, UrllibTransport


class BotHeldOpener:
    def __init__(self):
        self.release = threading.Event()
        self.started = []
        self.condition = threading.Condition()

    def open(self, request, timeout):
        with self.condition:
            self.started.append(timeout)
            self.condition.notify_all()
        self.release.wait()
        return BotResponse()


class BotResponse:
    status = 200

    def read(self, size):
        return b"{}"

    def close(self):
        pass


def test_bot_repeated_deadlines_bound_live_http_threads_and_new_calls():
    opener = BotHeldOpener()
    transport = UrllibTransport(opener=opener)
    before = set(threading.enumerate())
    try:
        for _ in range(12):
            with pytest.raises(TimeoutError):
                transport.request("PATCH", "/api/v10/test", {}, {}, timeout=0.02, deadline=monotonic() + 0.02)
        alive = {thread for thread in threading.enumerate() if thread.name == "discord-http" and thread not in before}
        assert len(alive) <= 6
        assert len(opener.started) <= 6
    finally:
        opener.release.set()
        for thread in threading.enumerate():
            if thread.name == "discord-http" and thread not in before:
                thread.join(timeout=0.5)
    assert all(not thread.is_alive() for thread in alive)
    result = transport.request("PATCH", "/api/v10/test", {}, {}, timeout=1, deadline=monotonic() + 1)
    assert result.status == 200


def test_bot_configured_capacity_accepts_twenty_fourth_delivery_with_time_left():
    release = threading.Event()
    condition = threading.Condition()
    calls = []
    outcomes = []

    class BotCapacityOpener:
        def open(self, request, timeout):
            with condition:
                calls.append(timeout)
                number = len(calls)
                condition.notify_all()
            if number < 24:
                release.wait()
            return BotResponse()

    def bot_send_blocked():
        try:
            response = transport.request("PATCH", "/api/v10/test", {}, {}, timeout=5, deadline=monotonic() + 5)
            outcomes.append(response.status)
        except Exception as error:
            outcomes.append(error)

    before = set(threading.enumerate())
    requests = []
    try:
        transport = UrllibTransport(opener=BotCapacityOpener(), max_in_flight=24)
        for _ in range(23):
            request = threading.Thread(target=bot_send_blocked)
            requests.append(request)
            request.start()
        with condition:
            assert condition.wait_for(lambda: len(calls) == 23, timeout=2)
        reply = transport.request("PATCH", "/api/v10/test", {}, {}, timeout=1, deadline=monotonic() + 59)
        assert reply.status == 200 and len(calls) == 24
    finally:
        release.set()
        for request in requests:
            request.join(timeout=1)
        for thread in threading.enumerate():
            if thread.name == "discord-http" and thread not in before:
                thread.join(timeout=0.5)
    assert len(outcomes) == 23 and all(outcome == 200 for outcome in outcomes)


def test_bot_webhook_passes_capacity_to_default_transport(monkeypatch):
    capacities = []
    monkeypatch.setattr(
        webhook,
        "UrllibTransport",
        lambda *, clock, max_in_flight: capacities.append(max_in_flight) or object(),
    )
    DiscordWebhook("synthetic", 24)
    assert capacities == [24]


def test_bot_uninterruptible_http_calls_are_bounded_by_configured_c():
    opener = BotHeldOpener()
    transport = UrllibTransport(opener=opener, max_in_flight=24)
    before = set(threading.enumerate())
    try:
        for _ in range(25):
            with pytest.raises(TimeoutError):
                transport.request("PATCH", "/api/v10/test", {}, {}, timeout=0.001, deadline=monotonic() + 0.001)
        with opener.condition:
            assert opener.condition.wait_for(lambda: len(opener.started) == 24, timeout=0.5)
        alive = [thread for thread in threading.enumerate() if thread.name == "discord-http" and thread not in before]
        assert len(alive) == len(opener.started) == 24
    finally:
        opener.release.set()
        for thread in threading.enumerate():
            if thread.name == "discord-http" and thread not in before:
                thread.join(timeout=0.5)


@pytest.mark.parametrize("phase", ["headers", "body"])
def test_bot_default_transport_shuts_socket_and_finishes_worker_at_deadline(monkeypatch, phase):
    sockets = []

    class BotSocket:
        def __init__(self):
            self.shutdown_called = threading.Event()
            sockets.append(self)

        def shutdown(self, how):
            self.shutdown_called.set()

        def close(self):
            pass  # HTTPResponse의 본문 파일 참조는 이 시점에도 남아 있다.

    class BotResponse:
        status = 200
        code = 200
        reason = "OK"

        def __init__(self, sock):
            self.sock = sock

        def read(self, size):
            self.sock.shutdown_called.wait(0.5)
            raise OSError("synthetic closed socket")

        def close(self):
            pass

        def info(self):
            return {}

    class BotConnection:
        def __init__(self, host, timeout, context):
            self.sock = BotSocket()

        def set_debuglevel(self, level):
            pass

        def connect(self):
            pass

        def request(self, *args, **kwargs):
            self.connect()
            if phase == "headers":
                self.sock.shutdown_called.wait(0.5)
                raise OSError("synthetic closed socket")

        def getresponse(self):
            return BotResponse(self.sock)

        def close(self):
            pass

    monkeypatch.setattr(webhook, "HTTPSConnection", BotConnection)
    before = set(threading.enumerate())
    with pytest.raises(TimeoutError):
        UrllibTransport().request("PATCH", "/api/v10/test", {}, {}, timeout=0.02, deadline=monotonic() + 0.02)
    assert sockets and sockets[0].shutdown_called.is_set()
    workers = [thread for thread in threading.enumerate() if thread.name == "discord-http" and thread not in before]
    for worker in workers:
        worker.join(timeout=0.05)
    assert all(not worker.is_alive() for worker in workers)
