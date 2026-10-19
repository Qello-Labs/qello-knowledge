import importlib.util
import json
import logging
from pathlib import Path

from qello_knowledge.adapters.fake import FakeSourceAdapter
from qello_knowledge.adapters.replay import ReplayTransport
from qello_knowledge.config.loader import SecretValue
from qello_knowledge.domain.source_config import SourceConfig, SourceScope
from qello_knowledge.sources.collect import fetch_contents, list_all
from qello_knowledge.sources.session import DefaultSourceSession


def test_result_and_logs_never_serialize_secret_body_headers_or_query(clock, jitter, caplog):
    marker = "ghp" + "_" + "synthetic" * 5
    secret = SecretValue(marker)
    data = json.loads(Path("tests/fixtures/responses/fake/basic.json").read_text())
    exchange = data["body"]["exchanges"][2]
    good = exchange["responses"][0]
    good["headers"]["x-marker"] = marker
    good["body"]["body"] = marker
    redirected = "https://fake.invalid/moved/1?credential=" + marker
    exchange["responses"] = [
        dict(status=502, headers={"x-marker": marker}, body=marker),
        dict(status=302, headers={"Location": redirected}, body=marker),
    ]
    data["body"]["exchanges"].append(dict(method="GET", url=redirected, responses=[good]))

    class AuthenticatedReplay(ReplayTransport):
        def send(self, request):
            assert secret.reveal() == marker
            return super().send(request)

    transport = AuthenticatedReplay(data["body"]["exchanges"])
    adapter = FakeSourceAdapter()
    config = SourceConfig("docs", "fake", True, scope=SourceScope(("**/*.md",)), allowed_hosts=("fake.invalid",))
    session = DefaultSourceSession(transport, adapter, config, clock, jitter=jitter)
    caplog.set_level(logging.INFO, logger="qello_knowledge.sources.collect")
    result = fetch_contents(adapter, config, session, list_all(adapter, config, session))
    assert result.processed == 5 and result.items[0].retries == 1
    assert result.contents[0].body == marker  # 본문은 후속 처리에 넘기되 요약에는 넣지 않는다.
    report = json.dumps(result.to_dict(), ensure_ascii=False)
    assert caplog.records
    assert marker not in report + caplog.text
    assert all(forbidden not in report for forbidden in ('"body"', '"headers"', '"contents"', "?credential="))
    spec = importlib.util.spec_from_file_location("preflight_rules", Path("scripts/preflight.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # main을 호출하지 않고 RULES만 읽는다.
    for _, pattern in module.RULES:
        assert not pattern.search(report)
        assert not pattern.search(caplog.text)
