import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

from qello_knowledge.query.server import make_server


def test_serve_answers_healthz_on_loopback(tmp_path: Path, monkeypatch) -> None:
    for name in ("DATABASE_URL", "DISCORD_APPLICATION_ID", "DISCORD_PUBLIC_KEY", "DISCORD_BOT_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    server = make_server(0, tmp_path / ".env")
    assert server.server_address[0] == "127.0.0.1"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/healthz"
        try:
            urllib.request.urlopen(url, timeout=5)  # noqa: S310 - 루프백 테스트 서버
            raise AssertionError("설정이 없으므로 503이어야 한다")
        except urllib.error.HTTPError as error:
            assert error.code == 503
            assert json.loads(error.read())["entrypoint"] == "query"
    finally:
        server.shutdown()
        server.server_close()
