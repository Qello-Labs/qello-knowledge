"""질의 서비스의 수명 자리 C와 Discord HTTP 전송 자리가 같은지 확인한다."""

from types import SimpleNamespace

from qello_knowledge.config.loader import load
from qello_knowledge.config.registry import Entrypoint
from qello_knowledge.query.server import create_app
from tests.unit.fakes import valid_environ


def test_bot_create_app_passes_configured_lifetime_capacity_to_webhook(monkeypatch):
    captured = []
    monkeypatch.setattr("qello_knowledge.sources.config.load_sources", lambda path: ((), ()))
    monkeypatch.setattr("qello_knowledge.security.policy.load_policy", lambda path, configs: (object(), ()))
    monkeypatch.setattr("qello_knowledge.query.pipeline.configured_pipeline", lambda *args: None)
    monkeypatch.setattr("qello_knowledge.indexer.embedding.security_outgoing_check", lambda policy: lambda *args: False)
    monkeypatch.setattr(
        "qello_knowledge.adapters.discord.webhook.DiscordWebhook",
        lambda *args: captured.append(args) or SimpleNamespace(),
    )
    settings = load(
        Entrypoint.QUERY,
        environ={**valid_environ(), "QK_QUERY_WORKERS": "8", "QK_QUERY_QUEUE_SIZE": "16"},
        env_file=None,
    )
    app = create_app(settings)
    try:
        assert len(captured) == 1
        assert captured[0][1] == 24
    finally:
        app.jobs.close()
