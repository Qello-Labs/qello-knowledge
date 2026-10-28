"""합성 Confluence REST v2 응답(QK-ING-003). 실제 원본을 읽거나 저장하지 않는다.

이름·계정 ID·사이트 주소는 모두 합성 값이다. 요청 주소 형식은 contracts/confluence-adapter.md를 그대로 옮긴다.
"""

import json
from copy import deepcopy

from qello_knowledge.adapters.replay import ReplayTransport
from qello_knowledge.domain.source_config import SourceConfig, SourceScope
from qello_knowledge.sources.kinds import canonical_json
from qello_knowledge.sources.session import DefaultSourceSession
from tests.unit.sources.conftest import FakeClock

ROOT = "https://api.atlassian.com/ex/confluence/cloud-test"
BASE = ROOT + "/wiki/api/v2"
SITE = "https://site.invalid/wiki"
STATUS_QUERY = "status=current&status=archived&status=trashed&status=deleted"


def doc(*blocks):
    return {"type": "doc", "version": 1, "content": list(blocks)}


def paragraph(text):
    return {"type": "paragraph", "content": [{"type": "text", "text": text}]}


def config(*, space_key="SCRUM", space_id="100", judge_mode="site_users", team_group_id=None, doc_types=None,
           exclude_trees=(), enabled=True, max_content_bytes=1_000_000):  # fmt: skip
    extra = [("space_key", space_key), ("space_id", space_id), ("judge_mode", judge_mode)]
    if team_group_id is not None:
        extra.append(("team_group_id", team_group_id))
    extra += [("doc_types", canonical_json(doc_types or {})), ("exclude_trees", canonical_json(sorted(exclude_trees)))]
    return SourceConfig(
        "confluence-scrum",
        "confluence_pages",
        enabled,
        "ATLASSIAN_API_TOKEN",
        SourceScope(("**",), (), tuple(extra)),
        max_content_bytes=max_content_bytes,
        allowed_hosts=("api.atlassian.com",),
    )


def _restriction(state):
    # 공식 v2 응답 모양(state, createdBy, createdAt). createdBy는 계정 ID라 어디에도 남으면 안 된다.
    return {"state": state, "createdBy": "acct-000", "createdAt": "2026-10-01T00:00:00.000Z"}


class Scenario:
    """`pages`의 항목: id, title, parent_id, parent_type("page"), version(1), body(ADF), restriction("OPEN")."""

    def __init__(
        self,
        *,
        space_key="SCRUM",
        space_id="100",
        space_type="global",
        space_status="current",
        homepage_id="1",
        pages=None,
        folders=(),
        permissions=None,
        page_size=250,
        base_link=True,
    ):
        self.exchanges = []
        self.space_id = space_id
        self.base_link = base_link
        pages = list(pages) if pages is not None else [{"id": "1", "title": "홈", "parent_id": None}]
        self.pages = pages
        self.override(
            f"{BASE}/spaces?keys={space_key}",
            body=self._links(
                {
                    "results": [
                        {
                            "id": space_id,
                            "key": space_key,
                            "type": space_type,
                            "status": space_status,
                            "homepageId": homepage_id,
                        }
                    ]
                }
            ),
        )
        if permissions is not None:
            self.override(
                f"{BASE}/spaces/{space_id}/permissions?limit=250", body={"results": permissions, "_links": {}}
            )
        results = [self._page(page) for page in pages]
        chunks = [results[i : i + page_size] for i in range(0, len(results), page_size)] or [[]]
        url = f"{BASE}/spaces/{space_id}/pages?status=current&limit=250"
        for index, chunk in enumerate(chunks):
            links = {}
            if index + 1 < len(chunks):
                links["next"] = f"/wiki/api/v2/spaces/{space_id}/pages?status=current&limit=250&cursor=c{index + 1}"
            body = self._links({"results": chunk, "_links": links})
            self.override(url, body=body)
            if "next" in links:
                url = ROOT + links["next"]
        for page in pages:
            self.override(
                f"{BASE}/pages/{page['id']}/restriction-state",
                body=_restriction(page.get("restriction", "OPEN")),
            )
            if "body" in page:
                body = dict(self._page(page))
                body["body"] = {
                    "atlas_doc_format": {"value": json.dumps(page["body"], ensure_ascii=False), "representation": "x"}
                }
                self.override(f"{BASE}/pages/{page['id']}?body-format=atlas_doc_format", body=body)
        for folder in folders:
            self.override(
                f"{BASE}/folders/{folder['id']}",
                body={
                    "id": folder["id"],
                    "type": "folder",
                    "title": folder.get("title", "폴더"),
                    "parentId": folder.get("parent_id"),
                    "parentType": folder.get("parent_type", "page"),
                },
            )
            self.override(
                f"{BASE}/folders/{folder['id']}/restriction-state",
                body=_restriction(folder.get("restriction", "OPEN")),
            )

    def _links(self, body):
        if self.base_link:
            body.setdefault("_links", {})["base"] = SITE
        return body

    def _page(self, page):
        return {
            "id": page["id"],
            "status": page.get("status", "current"),
            "title": page.get("title", "페이지 " + page["id"]),
            "spaceId": page.get("space_id", self.space_id),
            "parentId": page.get("parent_id", "1"),
            "parentType": page.get("parent_type", "page"),
            "version": {"number": page.get("version", 1), "createdAt": "2026-10-01T00:00:00.000Z"},
            "_links": {"webui": f"/spaces/SCRUM/pages/{page['id']}"},
        }

    def missing(self, page_id, status=200, body=None):
        return self.override(f"{BASE}/pages/{page_id}?{STATUS_QUERY}", status=status, body=body or {})

    def override(self, url, status=200, headers=None, body=""):
        self.exchanges = [entry for entry in self.exchanges if entry["url"] != url]
        return self.queue(url, status, headers, body)

    def queue(self, url, status=200, headers=None, body=""):
        self.exchanges.append(
            {"method": "GET", "url": url, "responses": [{"status": status, "headers": headers or {}, "body": body}]}
        )
        return self

    def transport(self):
        return ReplayTransport(deepcopy(self.exchanges))


def session(adapter, transport, source_config, clock=None):
    return DefaultSourceSession(transport, adapter, source_config, clock or FakeClock(), jitter=lambda cap: cap / 2)


def adapter(**changes):
    from qello_knowledge.adapters.confluence import ConfluencePagesAdapter

    values = dict(gateway_root=ROOT, site_review_valid=True, public_link_hosts=("github.com",))
    return ConfluencePagesAdapter(**(values | changes))


def tree(*children, home="1"):
    """(id, title, parent_id, extra) 줄 목록을 페이지 사전 목록으로 만든다. 홈 페이지를 앞에 붙인다."""
    pages = [{"id": home, "title": "홈", "parent_id": None}]
    for child in children:
        page_id, title, parent, *rest = child
        pages.append({"id": page_id, "title": title, "parent_id": parent, **(rest[0] if rest else {})})
    return pages
