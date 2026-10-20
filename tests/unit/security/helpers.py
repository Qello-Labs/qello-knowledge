"""보안 필터 시험 도우미. conftest와 시험 파일이 함께 쓴다. 토큰 형식 값은 실행 중에 만든다(research R-12)."""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from qello_knowledge.adapters.replay import ReplayTransport
from qello_knowledge.domain.security import AccessScope
from qello_knowledge.domain.source_config import SourceConfig, SourceScope
from qello_knowledge.security.kinds import KindSecurityPolicy
from qello_knowledge.security.policy import SecurityPolicy
from tests.unit.synthetic_secrets import SYNTHETIC

FIXTURES = Path("tests/fixtures/responses/fake")


class FakeClock:
    def __init__(self):
        self.start = datetime(2026, 1, 1, tzinfo=UTC)
        self.elapsed = 0.0
        self.sleeps = []

    def now(self):
        return self.start + timedelta(seconds=self.elapsed)

    def monotonic(self):
        return self.elapsed

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.elapsed += seconds


def load_transport(name: str, secrets: dict[str, str] | None = None) -> ReplayTransport:
    """응답 샘플의 `{{SECRET:<종류>}}` 자리표시를 합성값으로 바꿔 재생 전송을 만든다."""
    text = (FIXTURES / f"{name}.json").read_text(encoding="utf-8")
    for kind, value in {**SYNTHETIC, **(secrets or {})}.items():
        text = text.replace("{{SECRET:" + kind + "}}", json.dumps(value)[1:-1])
    assert "{{SECRET:" not in text
    data = json.loads(text)
    assert {"source_api", "saved_at", "redactions"} <= data["_meta"].keys()
    return ReplayTransport(data["body"]["exchanges"])


def team_policy(**changes) -> SecurityPolicy:
    """모든 자료를 팀 공용으로 보는 시험용 정책. US1 시험을 접근 판정과 떼어 놓는다."""
    kinds = {
        "fake": KindSecurityPolicy("fake", "test-all-team", lambda access: AccessScope.TEAM, ("fake.invalid",), False)
    }
    return SecurityPolicy(**{"kinds": kinds, **changes})


def fake_config(**changes) -> SourceConfig:
    config = SourceConfig("docs", "fake", True, scope=SourceScope(("**/*.md",)), allowed_hosts=("fake.invalid",))
    return replace(config, **changes)


def content_requests(transport: ReplayTransport) -> list[str]:
    """목록 요청을 뺀 본문 요청 URL. 가짜 어댑터의 본문 URL은 `items/<id>`다."""
    return [r.url for r in transport.requests if "/items/" in r.url]
