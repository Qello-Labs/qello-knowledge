"""판정 기록·요약·로그에 비밀값과 내부 주소가 남지 않는다(SC-005, SC-010, FR-023).

다섯 판정 결과마다 식별자·위치·제목·원본 권한 원값·링크에 합성 비밀값과 내부 주소를 넣는다.
ING-001 로그와 `FetchResult.to_dict()`까지 함께 검사한다.
"""

import json
import logging

from qello_knowledge.adapters.fake import FakeSourceAdapter
from qello_knowledge.adapters.replay import ReplayTransport
from qello_knowledge.domain.secret_rules import find_secrets
from qello_knowledge.domain.security import Verdict
from qello_knowledge.security.policy import SecurityPolicy
from qello_knowledge.security.screen import screen_source
from qello_knowledge.sources.session import DefaultSourceSession
from tests.unit.security.helpers import FakeClock, fake_config
from tests.unit.synthetic_secrets import SYNTHETIC

TOKEN = SYNTHETIC["github-classic"]
INTERNAL = "db." + "corp" + ".internal"
COLLIDING = "intra" + "net-qk.md"
IP = "10.0." + "0.5"
HOST_PORT = "build" + "box:8080"
ADDRESSES = (INTERNAL, COLLIDING + "/", IP, HOST_PORT)
BASE = "https://fake.invalid"


def _item(id_, location, title, access, url=None):
    return {
        "id": id_,
        "url": url or f"{BASE}/view/{id_}",
        "version": "v1",
        "modified_at": None,
        "item_type": "markdown_file",
        "title": title,
        "location": location,
        "size_bytes": None,
        "access": access,
        "origin_state": "ACTIVE",
    }


def _content(id_, location, status=200):
    body = {"body": "# ok", "content_format": "MARKDOWN", "version": "v1", "location": location, "title": "ok"}
    return {
        "method": "GET",
        "url": f"{BASE}/items/{id_}",
        "responses": [{"status": status, "headers": {}, "body": body if status == 200 else {"m": "x"}}],
    }


ITEMS = [
    # 통과: 경로 파일 이름(확장자와 겹치는 호스트)은 남고, 제목·디렉터리·링크의 주소는 가린다.
    _item("p", f"docs/{INTERNAL}/{COLLIDING}", f"Guide {INTERNAL} {HOST_PORT}", {"visibility": "public"}),
    _item("u", "docs/u.md", "u", {"visibility": "public"}, url=f"https://{INTERNAL}/view/u"),
    # 경로 제외: 위치와 제목에 비밀값.
    _item("x", f"secrets/{TOKEN}.md", f"t {TOKEN}", {"visibility": "public"}),
    # 접근 보류: 원본 권한 원값에 비밀값과 IP.
    _item("a", "docs/a.md", "a", {"visibility": TOKEN}),
    _item("b", "docs/b.md", "b", {"visibility": f"http://{IP}/x"}),
    # 비밀값 차단: 제목 비밀값, 식별자 주소(경로 아닌 식별자이므로 확장자와 겹쳐도 막는다).
    _item("s", "docs/s.md", f"Setup {TOKEN}", {"visibility": "public"}),
    _item(COLLIDING, "docs/c.md", "c", {"visibility": "public"}),
    _item(INTERNAL, "docs/d.md", "d", {"visibility": "public"}),
    # 판정 실패: 본문 조회 404. 제목과 디렉터리에 주소.
    _item("e", f"{IP}/e.md", f"err {INTERNAL}", {"visibility": "public"}),
]
EXCHANGES = [
    {
        "method": "GET",
        "url": f"{BASE}/items?cursor=",
        "responses": [{"status": 200, "headers": {}, "body": {"items": ITEMS, "next_cursor": None}}],
    },
    _content("p", f"docs/{INTERNAL}/{COLLIDING}"),
    _content("u", "docs/u.md"),
    _content("e", f"{IP}/e.md", status=404),
]


def _run(caplog):
    caplog.set_level(logging.INFO)
    transport = ReplayTransport(json.loads(json.dumps(EXCHANGES)))
    config = fake_config(allowed_hosts=("fake.invalid", INTERNAL))
    adapter = FakeSourceAdapter()
    session = DefaultSourceSession(transport, adapter, config, FakeClock(), jitter=lambda cap: cap / 2)
    policy = SecurityPolicy()
    result = screen_source(adapter, config, session, policy)
    context = policy.output_context(config.kind)
    records = [v.to_dict(context) for v in result.verdicts]
    output = json.dumps(
        {"records": records, "summary": result.summary.to_dict(), "fetch": result.fetch.to_dict()}, ensure_ascii=False
    )
    return result, records, output + "\n" + caplog.text


def test_all_five_verdicts_are_exercised(caplog):
    result, _, _ = _run(caplog)
    assert {v.verdict for v in result.verdicts} == set(Verdict)


def test_no_secret_or_internal_address_in_records_summary_fetch_or_logs(caplog):
    _, _, output = _run(caplog)
    assert find_secrets(output) == ()
    assert TOKEN not in output
    for address in ADDRESSES:
        assert address not in output, address


def test_public_link_and_path_file_name_survive(caplog):
    _, records, _ = _run(caplog)
    passed = next(r for r in records if r["source_id"] == "p")
    assert passed["url"] == f"{BASE}/view/p"
    assert passed["location"] == f"docs/[가림:address]/{COLLIDING}"
    moved = next(r for r in records if r["source_id"] == "u")
    assert moved["url"] == "[가림:address]"
