"""자료 목록 표시·길이 제한·허용 범위·저장소 실패."""

import json
from datetime import UTC, datetime

import pytest

from qello_knowledge.discord.sources import render_sources
from qello_knowledge.domain.query_log import SourceSummary, SourcesView
from qello_knowledge.query.recorder import QueryRecorder
from tests.unit.query.bot_runtime import bot_request
from tests.unit.query.obs_builders import FakeQueryLog, sources
from tests.unit.query.test_obs_feedback_flow import feedback_runtime

STAMP = datetime(2026, 10, 29, 0, 0, tzinfo=UTC)


def test_render_kst_kind_neutralization_and_truncation():
    view = SourcesView(
        "v1",
        STAMP,
        (SourceSummary("alpha", "github_repo_files", 3, STAMP), SourceSummary("beta", "confluence_pages", 2, STAMP)),
    )
    text = render_sources(view)
    assert text == "자료 기준: 인덱스 v1 (활성화 2026-10-29 09:00 KST)\n" + (
        "- alpha · 저장소 파일 · 문서 3개 · 마지막 확인 2026-10-29 09:00 KST\n"
        "- beta · Confluence 페이지 · 문서 2개 · 마지막 확인 2026-10-29 09:00 KST"
    )
    many = SourcesView("v1", STAMP, tuple(SourceSummary("source" + str(n), "other", 1, STAMP) for n in range(100)))
    output = render_sources(many)
    shown = sum(line.startswith("- ") for line in output.splitlines())
    assert len(output) <= 2000 and output.endswith(f"(자료원 {100 - shown}개 더 있음)")
    hostile = render_sources(SourcesView("v1", STAMP, (SourceSummary("@everyone **x**\nnext", "other", 1, STAMP),)))
    assert r"\*\*x\*\*" in hostile and "**x**" not in hostile


@pytest.mark.parametrize("mode", ["ok", "off", "empty", "denied", "failed", "timeout"])
def test_sources_response(mode):
    value = SourcesView("v1", STAMP, (SourceSummary("alpha", "github_repo_files", 1, STAMP),))
    if mode == "empty":
        value = SourcesView(None, None)
    if mode == "failed":
        value = ValueError("합성 질문 1")
    port = FakeQueryLog(sources=value)
    with QueryRecorder(lambda: port, (lambda: port) if mode != "off" else None) as recorder:
        runtime = feedback_runtime(recorder)
        if mode == "denied":
            runtime.app.access_check = lambda item: False
        if mode == "timeout":
            runtime.app.component_timeout_ms = 200
        result = json.loads(bot_request(runtime, sources())[1])
        assert result["type"] == 4 and result["data"]["flags"] == 64
        text = result["data"]["content"]
        if mode == "denied":
            assert text == "여기서는 `/sources`를 쓸 수 없습니다."
        elif mode in ("failed", "timeout"):
            assert text == "지금은 자료 목록을 볼 수 없습니다. 잠시 후 다시 시도해 주세요."
        elif mode == "empty":
            assert text == "검색할 자료가 아직 준비되지 않았습니다. 운영 담당자에게 알려 주세요."
        else:
            assert "alpha" in text
        assert not any(name == "insert" for name, args in port.calls)
        assert not runtime.calls and not runtime.fake.requests
        runtime.jobs.close()
