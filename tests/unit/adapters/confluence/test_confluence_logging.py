"""비노출(QK-ING-003 FR-011·FR-027, SC-004). 로그·예외·요약에 제목·이름·계정 ID·주소·토큰이 없다."""

import base64
import logging

from qello_knowledge.config.loader import load
from qello_knowledge.config.registry import Entrypoint
from qello_knowledge.domain.source import SourceRequest
from qello_knowledge.indexer.sync_cli import TARGET_PARTS
from qello_knowledge.security.policy import SecurityPolicy
from qello_knowledge.security.screen import screen_source
from tests.unit.adapters import confluence_scenarios as cf
from tests.unit.fakes import valid_environ

SECRETS = ("비밀 제목", "팀원A", "acct-000", "site.invalid", "cloud-test", "숨은 본문")


def _pages():
    pages = cf.tree(
        ("2", "비밀 제목", "1", {"body": cf.doc(cf.paragraph("숨은 본문 팀원A"))}),
        ("3", "막힌 비밀 제목", "1", {"restriction": "VIEW_RESTRICTED"}),
        ("4", "실패 비밀 제목", "1", {"body": {"type": "paragraph"}}),
    )
    pages[0]["body"] = cf.doc(cf.paragraph("홈"))
    return pages


def test_logs_summaries_and_verdict_records_carry_no_sensitive_values(caplog):
    caplog.set_level(logging.DEBUG)
    config = cf.config(doc_types={"2": "설계 문서", "3": "설계 문서", "4": "설계 문서"})
    adapter = cf.adapter()
    scenario = cf.Scenario(pages=_pages())
    for _ in range(4):  # 일시적 실패는 재시도를 다 쓴다
        scenario.queue(f"{cf.BASE}/pages/2?body-format=atlas_doc_format", status=500)
    scenario.exchanges = [
        e
        for e in scenario.exchanges
        if not (e["url"].endswith("/pages/2?body-format=atlas_doc_format") and e["responses"][0]["status"] == 200)
    ]
    result = screen_source(adapter, config, cf.session(adapter, scenario.transport(), config), SecurityPolicy())
    context = SecurityPolicy().output_context("confluence_pages")
    outputs = [
        caplog.text,
        str(result.summary.to_dict()),
        str(result.fetch.to_dict()),
        *(str(v.to_dict(context)) for v in result.verdicts),
    ]
    for output in outputs:
        for secret in SECRETS:
            assert secret not in output


def test_target_parts_use_gateway_and_basic_auth_without_leaking_values():
    environ = valid_environ() | {"ATLASSIAN_CLOUD_ID": "11111111-2222-3333-4444-555555555555"}
    settings = load(Entrypoint.INDEX, environ=environ, env_file=None)
    adapter, transport = TARGET_PARTS["confluence_pages"](cf.config(), settings, {"site_review_valid": {}})
    assert adapter._root == "https://api.atlassian.com/ex/confluence/11111111-2222-3333-4444-555555555555"
    expected = base64.b64encode((environ["ATLASSIAN_EMAIL"] + ":" + environ["ATLASSIAN_API_TOKEN"]).encode()).decode()
    assert transport._authorization() == "Basic " + expected
    assert transport._default_headers == {"accept": "application/json"}
    assert environ["ATLASSIAN_API_TOKEN"] not in repr(adapter) + repr(transport)
    assert "github.com" in adapter._public_link_hosts


def test_request_repr_hides_url():
    request = SourceRequest("GET", f"{cf.BASE}/pages/2?body-format=atlas_doc_format")
    assert "cloud-test" not in repr(request)
