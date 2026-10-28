"""Confluence Cloud 페이지 수집기(QK-ING-003, contracts/confluence-adapter.md). REST v2 `GET`만 보낸다.

제목·본문·사람 이름·계정 ID는 항목과 본문에만 담고 예외 문구·로그에 넣지 않는다.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
from urllib.parse import urlencode, urlsplit

from qello_knowledge.adapters.atlassian_adf import RULES_VERSION, convert_adf
from qello_knowledge.domain.source import (
    AccessInfo,
    AccessStatus,
    ChangeKeyKind,
    ContentFormat,
    InvalidResponse,
    ListPage,
    MissingCheck,
    RateLimitHint,
    ResponseClass,
    SourceContent,
    SourceFailure,
    SourceItem,
    SourceOrigin,
    SourceRequest,
    SourceResponse,
    default_classify,
    default_rate_limit_hint,
)
from qello_knowledge.domain.source_config import SourceConfig
from qello_knowledge.ports.source import SourceSession
from qello_knowledge.sources.kinds import canonical_json

KIND = "confluence_pages"
ITEM_TYPE = "confluence_page"
PAGE_LIMIT = 250
TEAM_SPACE_TYPES = frozenset({"global", "collaboration", "knowledge_base"})
VIEW_RESTRICTED = "VIEW_RESTRICTED"
OPEN_STATES = frozenset({"OPEN", "EDIT_RESTRICTED"})
LOOKUP_FAILED = "LOOKUP_FAILED"
UNKNOWN_STATE = "UNKNOWN"
MISSING_STATUSES = ("current", "archived", "trashed", "deleted")


@dataclass
class _Node:
    """목록에서 본 페이지나 사슬을 잇는 폴더. 실행 안에서만 쓴다."""

    content_id: str
    kind: str  # page, folder
    title: str
    parent_id: str | None
    parent_type: str | None
    raw: Mapping = field(default_factory=dict, repr=False)


def _segment(title: str | None) -> str:
    """제목 한 조각을 위치 경로 조각으로 바꾼다(research R-06). 구분자로 오해되지 않게 한다."""
    text = (title or "").strip().replace("/", "／")
    if not text:
        return "(제목 없음)"
    if set(text) == {"."} and len(text) <= 2:
        return "．" * len(text)
    return text


def _json(response: SourceResponse):
    try:
        return json.loads(response.body)
    except ValueError:
        raise InvalidResponse() from None


def _modified(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


class ConfluencePagesAdapter:
    kind = KIND

    def __init__(
        self,
        *,
        gateway_root: str,
        site_base: str | None = None,
        site_review_valid: bool | None = None,
        public_link_hosts: Sequence[str] = (),
    ) -> None:
        """`gateway_root`는 `https://api.atlassian.com/ex/confluence/<cloudId>`다. 값은 기록에 남기지 않는다."""
        self._root = gateway_root.rstrip("/")
        # 설정값이 `/wiki` 없이 오면 붙인다. `_links.base`는 `…/wiki`다(구현 검토 C10).
        base = site_base.rstrip("/") if site_base else None
        self._site_base = base if base is None or base.endswith("/wiki") else base + "/wiki"
        self._site_review_valid = site_review_valid
        self._public_link_hosts = tuple(public_link_hosts)
        self._space_id: str | None = None
        self._site: str | None = None
        self._doc_types: dict[str, str | None] = {}

    # ---- 요청 -----------------------------------------------------------------------------------

    def _api(self, path: str, query: Sequence[tuple[str, str]] = ()) -> str:
        return f"{self._root}/wiki/api/v2{path}" + ("?" + urlencode(query) if query else "")

    def _get(self, session: SourceSession, url: str):
        return _json(session.send(SourceRequest("GET", url)))

    def _next(self, link) -> str | None:
        """`_links.next`는 경로와 쿼리만 게이트웨이 기준 주소 뒤에 잇는다(research R-02)."""
        if not isinstance(link, str) or not link:
            return None
        parts = urlsplit(link)
        path = parts.path + ("?" + parts.query if parts.query else "")
        return self._root + path if path.startswith("/") else None

    def _remember_site(self, data) -> None:
        base = (data.get("_links") or {}).get("base") if isinstance(data, dict) else None
        if self._site is None and isinstance(base, str) and urlsplit(base).scheme == "https":
            self._site = base.rstrip("/")

    # ---- 목록 -----------------------------------------------------------------------------------

    def list_page(self, session: SourceSession, config: SourceConfig, cursor: str | None) -> ListPage:
        extra = dict(config.scope.extra)
        self._site = None
        self._doc_types = {}
        try:
            data = self._get(session, self._api("/spaces", (("keys", extra["space_key"]),)))
        except SourceFailure as failure:
            reason = "space_not_found" if failure.http_status in {403, 404} else "listing_failed"
            return ListPage((), None, False, None, reason)
        results = data.get("results") if isinstance(data, dict) else None
        if not results or not isinstance(results[0], dict):
            return ListPage((), None, False, None, "space_not_found")
        self._remember_site(data)
        space = results[0]
        origin = SourceOrigin(str(space.get("id") or "-"), str(space.get("key") or "-"), None)
        if str(space.get("id")) != extra.get("space_id"):
            # 첫 실행에서 틀린 ID가 기준값으로 등록되지 않게 한다(FR-002a).
            return ListPage((), None, False, origin, "space_id_mismatch")
        if space.get("type") == "personal":
            return ListPage((), None, False, origin, "personal_space")
        self._space_id = origin.origin_id
        team_group_read = None
        if extra.get("judge_mode") == "team_group":
            team_group_read = self._team_group_read(session, origin.origin_id, extra.get("team_group_id"))
        nodes, complete = self._list_pages(session, origin.origin_id)
        site = self._site or self._site_base
        if site is None:
            return ListPage((), None, False, origin, "site_base_missing")
        failed = self._load_folders(session, nodes)
        states = self._restrictions(session, nodes, nodes.keys(), failed)
        base = (
            ("judge_mode", str(extra.get("judge_mode"))),
            ("space_type", str(space.get("type"))),
            ("space_status", str(space.get("status"))),
        )
        if extra.get("judge_mode") == "team_group":
            permission = (
                None if team_group_read is None else ("team_group_read", "true" if team_group_read else "false")
            )
        else:
            permission = ("site_review_valid", "true" if self._site_review_valid else "false")
        items = self._items(config, extra, space, nodes, site, states, base, permission, complete)
        return ListPage(tuple(items), None, complete, origin, None if complete else "listing_failed")

    def _team_group_read(self, session: SourceSession, space_id: str, group_id: str | None) -> bool | None:
        """설정한 팀 그룹 ID의 스페이스 보기 권한 여부. 조회 실패면 `None`(조회 실패, FR-031)."""
        url: str | None = self._api(f"/spaces/{space_id}/permissions", (("limit", str(PAGE_LIMIT)),))
        found = False
        while url is not None:
            try:
                data = self._get(session, url)
            except SourceFailure:
                return None
            if not isinstance(data, dict) or not isinstance(data.get("results"), list):
                return None
            for assignment in data["results"]:
                principal = (assignment or {}).get("principal") or {}
                operation = (assignment or {}).get("operation") or {}
                found = found or (
                    principal.get("type") == "group"
                    and principal.get("id") == group_id
                    and operation.get("key") == "read"
                    and operation.get("targetType") == "space"
                )
            url = self._next((data.get("_links") or {}).get("next"))
        return found

    def _load_folders(self, session: SourceSession, nodes: dict[str, _Node]) -> set[str]:
        """페이지 상위 사슬에 있는 폴더를 한 번씩 읽어 잇는다. 읽지 못한 폴더 ID를 돌려준다."""
        failed: set[str] = set()
        pending = [n.parent_id for n in list(nodes.values()) if n.parent_type == "folder" and n.parent_id]
        while pending:
            folder_id = pending.pop()
            if folder_id in nodes or folder_id in failed:
                continue
            try:
                data = self._get(session, self._api(f"/folders/{folder_id}"))
            except SourceFailure:
                failed.add(folder_id)
                continue
            if not isinstance(data, dict):
                failed.add(folder_id)
                continue
            parent = str(data["parentId"]) if data.get("parentId") else None
            nodes[folder_id] = _Node(folder_id, "folder", data.get("title") or "", parent, data.get("parentType"), data)
            if parent and data.get("parentType") == "folder":
                pending.append(parent)
        return failed

    def _restrictions(self, session, nodes, wanted, failed) -> dict[str, str]:
        """콘텐츠마다 보기 제한 상태를 한 번씩 묻는다. 하위 페이지는 실행 안에서 이 결과를 다시 쓴다."""
        needed: set[str] = set()
        for node_id in wanted:
            needed.update(n.content_id for n in self._chain(node_id, nodes))
        states = {folder_id: LOOKUP_FAILED for folder_id in failed}
        for node_id in sorted(needed):
            node = nodes[node_id]
            kind = "folders" if node.kind == "folder" else "pages"
            try:
                data = self._get(session, self._api(f"/{kind}/{node_id}/restriction-state"))
            except SourceFailure:
                states[node_id] = LOOKUP_FAILED
                continue
            values = [data] if isinstance(data, str) else list(data.values()) if isinstance(data, dict) else []
            known = [v for v in values if isinstance(v, str) and (v == VIEW_RESTRICTED or v in OPEN_STATES)]
            states[node_id] = known[0] if known else UNKNOWN_STATE
        return states

    def _access(self, node_id, nodes, states, base, permission, complete=True) -> tuple[AccessInfo, int]:
        chain = self._chain(node_id, nodes)
        top = chain[-1]
        broken = top.parent_id is not None  # 목록에 없는 상위나 페이지·폴더가 아닌 상위에서 끊김
        values = [states.get(n.content_id, UNKNOWN_STATE) for n in chain]
        failed_folder = top.parent_type == "folder" and states.get(top.parent_id) == LOOKUP_FAILED
        if broken and (failed_folder or not complete):
            # 읽지 못한 폴더나 다 받지 못한 목록에서 끊긴 사슬은 조회 실패다(구현 검토 C1). 규칙상 미확인과 구분한다.
            values.append(LOOKUP_FAILED)
            broken = False
        if values[0] == VIEW_RESTRICTED:
            restricted = "self"
        elif VIEW_RESTRICTED in values[1:]:
            restricted = "ancestor"
        elif permission is None or LOOKUP_FAILED in values:
            return AccessInfo(AccessStatus.UNKNOWN), len(chain) - 1
        elif broken or UNKNOWN_STATE in values:
            restricted = "unknown"
        else:
            restricted = "none"
        if permission is None:
            return AccessInfo(AccessStatus.UNKNOWN), len(chain) - 1
        raw = (*base, permission, ("read_restricted", restricted), ("ancestor_count", str(len(chain) - 1)))
        return AccessInfo(AccessStatus.PROVIDED, raw), len(chain) - 1

    def _list_pages(self, session: SourceSession, space_id: str) -> tuple[dict[str, _Node], bool]:
        nodes: dict[str, _Node] = {}
        url: str | None = self._api(f"/spaces/{space_id}/pages", (("status", "current"), ("limit", str(PAGE_LIMIT))))
        while url is not None:
            try:
                data = self._get(session, url)
            except SourceFailure:
                return nodes, False
            if not isinstance(data, dict) or not isinstance(data.get("results"), list):
                return nodes, False
            self._remember_site(data)
            for page in data["results"]:
                if not isinstance(page, dict) or not page.get("id") or page.get("status", "current") != "current":
                    continue
                page_id = str(page["id"])
                if page_id not in nodes:
                    nodes[page_id] = _Node(
                        page_id,
                        "page",
                        page.get("title") or "",
                        str(page["parentId"]) if page.get("parentId") else None,
                        page.get("parentType"),
                        page,
                    )
            url = self._next((data.get("_links") or {}).get("next"))
        return nodes, True

    def _chain(self, node_id: str, nodes: Mapping[str, _Node]) -> list[_Node]:
        """자신부터 위로 올라가는 사슬. 목록에 없는 상위에서 멈춘다."""
        chain, seen = [], set()
        current = nodes.get(node_id)
        while current is not None and current.content_id not in seen:
            seen.add(current.content_id)
            chain.append(current)
            current = nodes.get(current.parent_id) if current.parent_id else None
        return chain

    def _location(self, space_key: str, chain: list[_Node], home_id: str | None) -> str:
        ids = [node.content_id for node in chain]
        below_home = chain[: ids.index(home_id)] if home_id in ids and ids[0] != home_id else chain
        return "/".join([space_key, *(_segment(node.title) for node in reversed(below_home))])

    def _classify(self, page_id, nodes, home_id, doc_types, trees) -> tuple[str | None, str | None]:
        """(문서 종류, 제외 사유). 첫 단계 콘텐츠 ID로 정한다(FR-020·FR-020a·FR-021a, research R-07).

        사슬이 끊겨 홈까지 닿지 못한 페이지는 제외하지 않고 권한 판정(미확인·조회 실패)에 맡긴다(구현 검토 C1).
        """
        nodes_in_chain = self._chain(page_id, nodes)
        chain = [node.content_id for node in nodes_in_chain]
        if page_id == home_id:
            return None, "space-home"
        if trees.intersection(chain):
            return None, "excluded-tree"
        if home_id not in chain:
            return None, "outside-home" if nodes_in_chain[-1].parent_id is None else None
        doc_type = doc_types.get(chain[chain.index(home_id) - 1])
        if doc_type is None:
            return None, "unclassified"
        if doc_type == "색인 안 함":
            return None, "not-indexed-type"
        return doc_type, None

    def _items(self, config, extra, space, nodes, site, states, base, permission, complete) -> list[SourceItem]:
        home_id = str(space.get("homepageId")) if space.get("homepageId") else None
        doc_types = json.loads(extra.get("doc_types") or "{}")
        trees = set(json.loads(extra.get("exclude_trees") or "[]"))
        items = []
        for page_id in sorted(n.content_id for n in nodes.values() if n.kind == "page"):
            node = nodes[page_id]
            doc_type, exclusion = self._classify(page_id, nodes, home_id, doc_types, trees)
            self._doc_types[page_id] = doc_type
            raw = node.raw
            version = (raw.get("version") or {}).get("number")
            title = raw.get("title") or ""
            webui = (raw.get("_links") or {}).get("webui") or f"/pages/{page_id}"
            items.append(
                SourceItem(
                    config.name,
                    KIND,
                    page_id,
                    site + webui,
                    f"{version}:{sha256(title.encode('utf-8')).hexdigest()[:12]}",
                    ChangeKeyKind.VERSION,
                    None if version is None else str(version),
                    _modified((raw.get("version") or {}).get("createdAt")),
                    ITEM_TYPE,
                    title,
                    self._location(extra["space_key"], self._chain(page_id, nodes), home_id),
                    None,
                    self._access(page_id, nodes, states, base, permission, complete)[0],
                    None,
                    exclusion,
                )
            )
        return items

    # ---- 분류 -----------------------------------------------------------------------------------

    def classify(self, response: SourceResponse) -> ResponseClass:
        return default_classify(response)

    def rate_limit_hint(self, response: SourceResponse) -> RateLimitHint | None:
        return default_rate_limit_hint(response)

    def fetch_content(self, session: SourceSession, config: SourceConfig, item: SourceItem) -> SourceContent:
        """팀 공용 판정을 통과한 페이지만 받는다(보안 필터가 부른다). ADF를 Markdown으로 바꾼다(research R-08)."""
        data = self._get(session, self._api(f"/pages/{item.source_id}", (("body-format", "atlas_doc_format"),)))
        value = (
            (((data.get("body") or {}).get("atlas_doc_format") or {}).get("value")) if isinstance(data, dict) else None
        )
        try:
            adf = json.loads(value) if isinstance(value, str) else value
            site = urlsplit(self._site or self._site_base or "").hostname
            doc_type = self._doc_types.get(item.source_id)
            result = convert_adf(
                adf,
                title=item.title or "",
                site_host=site,
                public_link_hosts=self._public_link_hosts,
                doc_type=doc_type,
            )
        except (ValueError, TypeError, AttributeError, KeyError, IndexError, RecursionError):
            # 형식이 어긋난 본문은 그 페이지만 실패시킨다(구현 검토 C6). 예외 문구에는 원문을 넣지 않는다.
            raise InvalidResponse() from None
        meeting = None
        if result.meeting is not None:
            meeting = {
                "date": result.meeting.date,
                "kind": result.meeting.kind,
                "spec_ids": list(result.meeting.spec_ids),
            }
        return SourceContent(
            item.source_id,
            result.markdown,
            ContentFormat.MARKDOWN,
            item.version,
            item.location,
            item.title,
            locator_extra={"confluence": {"page_id": item.source_id, "doc_type": doc_type, "meeting": meeting}},
            fingerprint_extra=canonical_json({"rules": RULES_VERSION, "doc_type": doc_type, "meeting": meeting}),
            conversion_warnings=result.warnings,
        )

    def check_missing(
        self, session: SourceSession, config: SourceConfig, source_ids: Sequence[str]
    ) -> Mapping[str, MissingCheck]:
        """목록에서 사라진 페이지를 단건으로 다시 본다(FR-030). `RunStopped`는 호출자가 처리한다."""
        space_id = dict(config.scope.extra).get("space_id")
        results = {}
        for page_id in source_ids:
            url = self._api(f"/pages/{page_id}", tuple(("status", status) for status in MISSING_STATUSES))
            try:
                data = self._get(session, url)
            except SourceFailure as failure:
                results[page_id] = MissingCheck.GONE if failure.http_status in {403, 404} else MissingCheck.UNCERTAIN
                continue
            status = data.get("status") if isinstance(data, dict) else None
            if not isinstance(data, dict):
                results[page_id] = MissingCheck.UNCERTAIN
            elif str(data.get("spaceId")) != space_id:
                results[page_id] = MissingCheck.GONE
            elif status == "current":
                results[page_id] = MissingCheck.PRESENT
            elif status in {"archived", "trashed", "deleted"}:
                results[page_id] = MissingCheck.ARCHIVED
            else:
                results[page_id] = MissingCheck.UNCERTAIN
        return results
