import io
from types import SimpleNamespace

import pytest

from qello_knowledge.config.loader import load
from qello_knowledge.config.registry import Entrypoint
from qello_knowledge.query import server
from tests.unit.fakes import valid_environ


class BotServer:
    server_port = 1234

    def __init__(self):
        self.served = False
        self.closed = False

    def serve_forever(self):
        self.served = True

    def server_close(self):
        self.closed = True


@pytest.mark.parametrize("invalid", [{}, {**valid_environ(), "QK_QUERY_CALL_LIMIT": "11"}])
def test_bot_serve_rejects_invalid_settings_before_start(monkeypatch, invalid, capsys):
    settings = load(Entrypoint.QUERY, environ=invalid, env_file=None)
    monkeypatch.setattr(server, "load", lambda *a, **k: settings)
    fake = BotServer()
    monkeypatch.setattr(server, "make_server", lambda *a, **k: fake)
    assert server.main(["serve"]) == 2
    assert not fake.served
    assert "secret" not in capsys.readouterr().err


def test_bot_serve_checks_backend_starts_and_closes_runtime(monkeypatch, capsys):
    settings = load(Entrypoint.QUERY, environ=valid_environ(), env_file=None)
    monkeypatch.setattr(server, "load", lambda *a, **k: settings)
    fake = BotServer()
    calls = []
    monkeypatch.setattr(server, "require_backend", lambda: calls.append("backend"), raising=False)
    monkeypatch.setattr(
        server,
        "create_app",
        lambda *a: SimpleNamespace(jobs=SimpleNamespace(close=lambda: calls.append("close"))),
        raising=False,
    )
    monkeypatch.setattr(server, "make_server", lambda *a, **k: fake)
    assert server.main(["serve"]) == 0
    assert calls == ["backend", "close"] and fake.served and fake.closed
    assert "QK_DISCORD_ALLOWED_CHANNELS" in capsys.readouterr().err


def bot_handler(body, length=None):
    handler = object.__new__(server._Handler)
    handler.command, handler.path = "POST", "/discord/interactions"
    handler.headers = {
        "Content-Length": str(len(body)) if length is None else length,
        "X-Signature-Ed25519": "synthetic-signature",
    }
    handler.rfile, handler.wfile = io.BytesIO(body), io.BytesIO()
    handler._report = lambda: None
    handler._app = object()
    handler.send_response = lambda status: setattr(handler, "bot_status", status)
    handler.send_header = lambda *args: None
    handler.end_headers = lambda: None
    return handler


def test_bot_handler_preserves_original_bytes_headers_and_response_headers(monkeypatch):
    handler = bot_handler(b'{ "type" : 1 }')
    calls = []

    def handle(method, path, report, **kwargs):
        calls.append(kwargs)
        return 200, '{"type":5}', {"X-QK-Run": "run"}

    sent = []
    handler.send_header = lambda name, value: sent.append((name, value))
    monkeypatch.setattr(server, "handle", handle)
    handler._respond()
    assert handler.bot_status == 200 and calls[0]["body"] == b'{ "type" : 1 }'
    assert calls[0]["headers"]["X-Signature-Ed25519"] == "synthetic-signature"
    assert ("X-QK-Run", "run") in sent


@pytest.mark.parametrize("length,status", [("65537", 413), ("-1", 400), ("invalid", 400)])
def test_bot_handler_does_not_read_invalid_or_large_body(length, status):
    handler = bot_handler(b"synthetic", length)
    handler._respond()
    assert handler.bot_status == status and handler.rfile.tell() == 0
