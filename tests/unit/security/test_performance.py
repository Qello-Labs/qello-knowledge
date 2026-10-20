"""Phase 1 규모(Markdown 81개, 약 1.1 MB, 0.2 인벤토리) 필터 처리 시간(SC-008)."""

import time

from qello_knowledge.adapters.fake import FakeSourceAdapter
from qello_knowledge.adapters.replay import ReplayTransport
from qello_knowledge.security.policy import SecurityPolicy
from qello_knowledge.security.screen import screen_source
from qello_knowledge.sources.session import DefaultSourceSession
from tests.unit.security.helpers import FakeClock, fake_config

BASE = "https://fake.invalid"
DOCS = 81
BODY = ("## 절 제목\n\n설명 문장과 `code.sample()` 호출, 버전 1.2.3, 경로 docs/guide.md를 담은 줄이다.\n" * 120)[
    :13_600
]


def _exchanges():
    items = [
        {"id": str(n), "url": f"{BASE}/view/{n}", "version": "v1", "modified_at": None, "item_type": "markdown_file",
         "title": f"Doc {n}", "location": f"docs/{n}.md", "size_bytes": None, "access": {"visibility": "public"},
         "origin_state": "ACTIVE"}
        for n in range(DOCS)
    ]  # fmt: skip
    listing = {"items": items, "next_cursor": None}
    exchanges = [
        {
            "method": "GET",
            "url": f"{BASE}/items?cursor=",
            "responses": [{"status": 200, "headers": {}, "body": listing}],
        }
    ]
    for n in range(DOCS):
        body = {
            "body": BODY,
            "content_format": "MARKDOWN",
            "version": "v1",
            "location": f"docs/{n}.md",
            "title": f"Doc {n}",
        }
        exchanges.append(
            {"method": "GET", "url": f"{BASE}/items/{n}", "responses": [{"status": 200, "headers": {}, "body": body}]}
        )
    return exchanges


def test_phase1_scale_finishes_within_a_minute():
    config = fake_config(limits=fake_config().limits.__class__(max_requests_per_minute=10_000))
    transport = ReplayTransport(_exchanges())
    adapter = FakeSourceAdapter()
    session = DefaultSourceSession(transport, adapter, config, FakeClock(), jitter=lambda cap: cap / 2)
    total = DOCS * len(BODY.encode("utf-8"))
    started = time.perf_counter()
    result = screen_source(adapter, config, session, SecurityPolicy())
    elapsed = time.perf_counter() - started
    print(f"SC-008 docs={DOCS} bytes={total} elapsed={elapsed:.3f}s")
    assert len(result.passed) == DOCS
    assert 1_000_000 <= total <= 1_300_000
    assert elapsed < 60
