"""QK-ING-003 plan 측정(research R-01). Confluence 스페이스 하나를 읽기 전용으로 읽어 집계만 출력한다.

Confluence REST API v2에 `GET` 요청만 보낸다. 범위 지정 토큰이라 `api.atlassian.com` 게이트웨이로 부른다(ADR-026).
출력에는 개수·크기·상태 코드·원본이 정한 열거값(스페이스 종류, 보기 제한 상태, 매크로 키, 노드 종류)만 담는다.
페이지 제목·제목 경로·본문·사람 이름·계정 ID·메일·Cloud ID·사이트 주소·토큰은 출력하지 않는다(spec FR-027).
첫 단계 콘텐츠는 ID와, 제목이 작성 규칙(`docs/sdd/clickup-writing-rules.md` 1.1)의 종류 이름과
정확히 같을 때만 그 이름을 낸다.

설정은 `.env`의 `ATLASSIAN_API_TOKEN`·`ATLASSIAN_EMAIL`·`ATLASSIAN_CLOUD_ID`를 읽고
(환경 변수가 있으면 그쪽이 이긴다), 값은 출력하지 않는다.

실행(저장소 루트):
    uv run python specs/QK-ING-003-confluence-pages/measurement/measure_confluence.py --space-key SCRUM [--dry-run]

`--max-requests`(기본 1500)를 넘을 요청은 보내지 않고 그 단계를 건너뛴다.
분위수는 정렬한 값의 `index = min(n - 1, floor(n * q))` 원소다.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
import platform
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import UTC, datetime
from pathlib import Path

from qello_knowledge.config.loader import merge_sources, read_env_file
from qello_knowledge.domain.embedding import MODELS
from qello_knowledge.embedding.estimate import estimated_neurons

GATEWAY = "https://api.atlassian.com/ex/confluence/"
NAMES = ("ATLASSIAN_API_TOKEN", "ATLASSIAN_EMAIL", "ATLASSIAN_CLOUD_ID")
MODEL = MODELS["@cf/baai/bge-m3"]
KNOWN_TYPES = (
    "회의록",
    "용어집",
    "Qello 기능명세서",
    "설계 문서",
    "API Docs",
    "Design Docs",
    "개발 규칙 문서",
    "ADR",
    "관리자용",
)
GLOSSARY_HEADER = ["용어", "정의", "동의어·약어·영문", "코드 식별자·API 경로", "관련 문서"]
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RESTRICTION_STATES = {"OPEN", "EDIT_RESTRICTED", "VIEW_RESTRICTED"}
FAILURES_BEFORE_SKIP = 3


class AuthFailure(Exception):
    pass


class Client:
    def __init__(self, cloud_id: str, email: str, token: str, max_requests: int):
        self._root = GATEWAY + urllib.parse.quote(cloud_id, safe="")
        self._auth = "Basic " + base64.b64encode(f"{email}:{token}".encode()).decode()
        self.max_requests = max_requests
        self.sent = 0
        self.statuses: dict[str, Counter] = defaultdict(Counter)
        self.retries = Counter()
        self.site_host: str | None = None

    def remaining(self) -> int:
        return self.max_requests - self.sent

    def get(self, endpoint: str, path: str) -> tuple[int, dict | None]:
        """`endpoint`는 집계용 이름(ID 없는 경로 틀), `path`는 `/wiki/api/v2/...`로 시작하는 실제 경로."""
        for attempt in range(4):
            if self.sent >= self.max_requests:
                raise RuntimeError("max_requests")
            self.sent += 1
            # 주소는 고정된 https 게이트웨이 + API가 돌려준 경로뿐이라 다른 스킴이 들어올 수 없다.
            request = urllib.request.Request(  # noqa: S310
                self._root + path, headers={"Authorization": self._auth, "Accept": "application/json"}, method="GET"
            )
            try:
                with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
                    status, body = response.status, response.read()
                    retry_after = None
            except urllib.error.HTTPError as error:
                status, body = error.code, b""
                retry_after = error.headers.get("Retry-After")
            except urllib.error.URLError:
                status, body, retry_after = 0, b"", None
            self.statuses[endpoint][status] += 1
            if status == 429 and attempt < 3:
                self.retries[endpoint] += 1
                time.sleep(min(int(retry_after) if (retry_after or "").isdigit() else 5, 60))
                continue
            if status == 401:
                raise AuthFailure(endpoint)
            if status != 200:
                return status, None
            data = json.loads(body)
            base = (data.get("_links") or {}).get("base") if isinstance(data, dict) else None
            if base and self.site_host is None:
                self.site_host = urllib.parse.urlsplit(base).hostname
            return status, data
        return 429, None

    def paged(self, endpoint: str, path: str):
        """`_links.next`를 따라 끝까지 받는다. 완전히 받았는지와 결과를 돌려준다."""
        results, complete = [], True
        while path:
            status, data = self.get(endpoint, path)
            if data is None:
                return results, False, status
            results.extend(data.get("results", []))
            path = (data.get("_links") or {}).get("next")
        return results, complete, 200


def quantile(values, q):
    if not values:
        return None
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.floor(len(ordered) * q))]


def spread(values):
    return {
        "n": len(values),
        "p50": quantile(values, 0.5),
        "p95": quantile(values, 0.95),
        "max": max(values, default=None),
    }


def node_text(node) -> str:
    if not isinstance(node, dict):
        return ""
    if node.get("type") == "text":
        return node.get("text", "")
    return "".join(node_text(child) for child in node.get("content", []) or [])


def host_class(url: str, site_host: str | None) -> str:
    try:
        parts = urllib.parse.urlsplit(url)
    except ValueError:
        return "invalid"
    if parts.scheme == "mailto":
        return "mailto"
    if not parts.scheme and not parts.netloc:
        return "relative"
    if site_host and parts.hostname == site_host:
        return "same_site"
    return "other"


class Census:
    """ADF 노드 종류·표식·매크로 키와 변환에 영향을 주는 구조를 센다. 글자는 크기만 잰다."""

    def __init__(self, site_host_ref):
        self.nodes = Counter()
        self.marks = Counter()
        self.extension_keys = Counter()
        self.link_hosts = Counter()
        self.card_hosts = Counter()
        self.merged_cell_tables = 0
        self.nested_tables = 0
        self.mentions = 0
        self.media = 0
        self._site = site_host_ref

    def walk(self, node, in_table=False):
        if not isinstance(node, dict):
            return
        kind = node.get("type", "?")
        self.nodes[kind] += 1
        attrs = node.get("attrs") or {}
        if kind in {"extension", "bodiedExtension", "inlineExtension"}:
            self.extension_keys[str(attrs.get("extensionKey", "?"))] += 1
        if kind == "mention":
            self.mentions += 1
        if kind in {"media", "mediaInline"}:
            self.media += 1
        if kind in {"inlineCard", "blockCard", "embedCard"} and attrs.get("url"):
            self.card_hosts[host_class(attrs["url"], self._site())] += 1
        if kind == "table":
            if in_table:
                self.nested_tables += 1
            if any(
                (cell.get("attrs") or {}).get("colspan", 1) > 1 or (cell.get("attrs") or {}).get("rowspan", 1) > 1
                for row in node.get("content", []) or []
                for cell in row.get("content", []) or []
                if isinstance(cell, dict)
            ):
                self.merged_cell_tables += 1
        for mark in node.get("marks", []) or []:
            self.marks[mark.get("type", "?")] += 1
            if mark.get("type") == "link":
                self.link_hosts[host_class((mark.get("attrs") or {}).get("href", ""), self._site())] += 1
        for child in node.get("content", []) or []:
            self.walk(child, in_table or kind == "table")


def assignment_kind(assignment) -> str:
    """권한 할당의 주체 종류와 작업만 남긴다. 주체 ID는 버린다."""
    principal, operation = assignment.get("principal") or {}, assignment.get("operation") or {}
    return f"{principal.get('type')}|{operation.get('key')}|{operation.get('targetType')}"


def first_table(doc):
    for node in doc.get("content", []) or []:
        if isinstance(node, dict) and node.get("type") == "table":
            return node
    return None


def rows(table):
    return [
        [node_text(cell).strip() for cell in row.get("content", []) or []] for row in table.get("content", []) or []
    ]


def meeting_fields(doc) -> tuple[bool, bool]:
    """첫 표에 `일시` 필드가 있는지, 그 값이 YYYY-MM-DD인지."""
    table = first_table(doc)
    if table is None:
        return False, False
    for cells in rows(table):
        if len(cells) >= 2 and cells[0] == "일시":
            return True, bool(DATE.match(cells[1]))
    return False, False


def glossary_rows(doc) -> int | None:
    for node in doc.get("content", []) or []:
        if isinstance(node, dict) and node.get("type") == "table":
            table_rows = rows(node)
            if table_rows and table_rows[0] == GLOSSARY_HEADER:
                return len(table_rows) - 1
    return None


def measure(args) -> dict:
    values = merge_sources(os.environ, read_env_file(Path(args.env_file)))
    missing = [name for name in NAMES if not values.get(name)]
    if missing:
        return {"error": "missing_settings", "names": missing}
    client = Client(
        values["ATLASSIAN_CLOUD_ID"], values["ATLASSIAN_EMAIL"], values["ATLASSIAN_API_TOKEN"], args.max_requests
    )
    started = time.monotonic()
    result: dict = {"space_key": args.space_key}
    skipped: dict[str, str] = {}
    try:
        status, data = client.get(
            "GET /spaces", "/wiki/api/v2/spaces?" + urllib.parse.urlencode({"keys": args.space_key})
        )
        spaces = (data or {}).get("results", [])
        if not spaces:
            result["space"] = {"found": False, "status_code": status}
            return finish(result, client, started, skipped)
        space = spaces[0]
        space_id, homepage_id = space["id"], space.get("homepageId")
        result["space"] = {
            "found": True,
            "type": space.get("type"),
            "status": space.get("status"),
            "has_homepage": bool(homepage_id),
        }

        perms, perms_complete, perms_status = client.paged(
            "GET /spaces/{id}/permissions", f"/wiki/api/v2/spaces/{space_id}/permissions?limit=250"
        )
        result["space_permissions"] = {
            "complete": perms_complete,
            "status_code": perms_status,
            "assignments": len(perms),
            "by_principal_operation": sorted(Counter(map(assignment_kind, perms)).items()),
        }

        pages, pages_complete, pages_status = client.paged(
            "GET /spaces/{id}/pages",
            f"/wiki/api/v2/spaces/{space_id}/pages?"
            + urllib.parse.urlencode({"limit": 250, "body-format": "atlas_doc_format", "status": "current"}),
        )
        result["listing"] = {"complete": pages_complete, "status_code": pages_status, "pages": len(pages)}
        by_id = {p["id"]: p for p in pages}

        census = Census(lambda: client.site_host)
        texts, adf_bytes, text_bytes, versions = {}, [], [], []
        meeting, glossary = {}, {}
        empty_bodies = 0
        for page in pages:
            raw = ((page.get("body") or {}).get("atlas_doc_format") or {}).get("value") or ""
            raw = raw if isinstance(raw, str) else json.dumps(raw, ensure_ascii=False)
            adf_bytes.append(len(raw.encode("utf-8")))
            versions.append((page.get("version") or {}).get("number") or 0)
            doc = json.loads(raw) if raw else {}
            census.walk(doc)
            text = "\n".join(node_text(block) for block in doc.get("content", []) or [])
            texts[page["id"]] = text
            text_bytes.append(len(text.encode("utf-8")))
            empty_bodies += not text.strip()
            meeting[page["id"]] = meeting_fields(doc)
            glossary[page["id"]] = glossary_rows(doc)
        result["bodies"] = {
            "adf_bytes": spread(adf_bytes) | {"total": sum(adf_bytes)},
            "text_bytes": spread(text_bytes) | {"total": sum(text_bytes)},
            "empty_text_pages": empty_bodies,
            "version_number": spread(versions),
            "estimated_neurons_text_only": round(estimated_neurons(list(texts.values()), MODEL), 2),
        }
        result["adf"] = {
            "node_types": sorted(census.nodes.items()),
            "mark_types": sorted(census.marks.items()),
            "extension_keys": sorted(census.extension_keys.items()),
            "link_mark_hosts": sorted(census.link_hosts.items()),
            "card_hosts": sorted(census.card_hosts.items()),
            "tables_with_merged_cells": census.merged_cell_tables,
            "nested_tables": census.nested_tables,
            "mentions": census.mentions,
            "media": census.media,
        }

        folder_ids = {p["parentId"] for p in pages if p.get("parentType") == "folder" and p.get("parentId")}
        folders: dict[str, dict] = {}
        pending = list(folder_ids)
        while pending:
            folder_id = pending.pop()
            if folder_id in folders:
                continue
            if client.remaining() < 1:
                skipped["GET /folders/{id}"] = "max_requests"
                break
            status, data = client.get("GET /folders/{id}", f"/wiki/api/v2/folders/{folder_id}")
            folders[folder_id] = data or {"status_code": status}
            if data and data.get("parentType") == "folder" and data.get("parentId"):
                pending.append(data["parentId"])
        parent = {pid: (p.get("parentId"), p.get("parentType")) for pid, p in by_id.items()}
        parent |= {fid: (f.get("parentId"), f.get("parentType")) for fid, f in folders.items() if "id" in f}
        result["tree"] = tree_summary(by_id, folders, parent, homepage_id, texts, meeting, glossary)

        probe = next((p["id"] for p in pages if p.get("parentId") and p["parentId"] != homepage_id), None)
        if probe:
            status, _ = client.get("GET /pages/{id}/ancestors", f"/wiki/api/v2/pages/{probe}/ancestors?limit=1")
            result["ancestors_probe_status"] = status

        page_states = restriction_states(client, "GET /pages/{id}/restriction-state", "pages", by_id, skipped)
        folder_states = restriction_states(client, "GET /folders/{id}/restriction-state", "folders", folders, skipped)
        result["restrictions"] = restriction_summary(page_states, folder_states, parent)
    except AuthFailure as failure:
        result["error"] = f"auth_failure:{failure}"
    except RuntimeError as failure:
        result["error"] = str(failure)
    return finish(result, client, started, skipped)


def restriction_states(client, endpoint, kind, items, skipped) -> dict[str, str]:
    states, failures = {}, 0
    for item_id in sorted(items):
        if client.remaining() < 1:
            skipped[endpoint] = "max_requests"
            break
        status, data = client.get(endpoint, f"/wiki/api/v2/{kind}/{item_id}/restriction-state")
        if data is None:
            failures += 1
            states[item_id] = f"error:{status}"
            if failures >= FAILURES_BEFORE_SKIP and not any(not s.startswith("error:") for s in states.values()):
                skipped[endpoint] = f"first_{FAILURES_BEFORE_SKIP}_failed:{status}"
                break
            continue
        found = (
            [v for v in data.values() if isinstance(v, str) and v in RESTRICTION_STATES]
            if isinstance(data, dict)
            else []
        )
        states[item_id] = (
            found[0]
            if found
            else "unrecognized:" + ",".join(sorted(data))
            if isinstance(data, dict)
            else "unrecognized"
        )
    return states


def restriction_summary(page_states, folder_states, parent) -> dict:
    """페이지별 상태 분포와, 상위가 VIEW_RESTRICTED인데 자신은 아닌 경우(상속을 반영하지 않는다는 신호) 수."""
    states = page_states | folder_states
    inherited_gap = Counter()
    for item_id, state in page_states.items():
        current = parent.get(item_id, (None, None))[0]
        while current:
            if states.get(current) == "VIEW_RESTRICTED":
                inherited_gap[state] += 1
                break
            current = parent.get(current, (None, None))[0]
    return {
        "page_states": sorted(Counter(page_states.values()).items()),
        "folder_states": sorted(Counter(folder_states.values()).items()),
        "pages_under_view_restricted_ancestor_by_own_state": sorted(inherited_gap.items()),
    }


def tree_summary(by_id, folders, parent, homepage_id, texts, meeting, glossary) -> dict:
    def chain(item_id):
        path, current, seen = [], item_id, set()
        while current and current not in seen:
            seen.add(current)
            path.append(current)
            current = parent.get(current, (None, None))[0]
        return path

    depth = Counter()
    first_level: dict[str, dict] = {}
    outside_home = 0
    for page_id in by_id:
        path = chain(page_id)
        if homepage_id not in path:
            outside_home += 1
            continue
        level = path.index(homepage_id)
        depth[level] += 1
        if level == 0:
            continue
        top = path[level - 1]
        entry = first_level.setdefault(
            top,
            {
                "pages": 0,
                "text_bytes": 0,
                "meeting_date_field": 0,
                "meeting_date_valid": 0,
                "glossary_tables": 0,
                "glossary_rows": 0,
            },
        )
        entry["pages"] += 1
        entry["text_bytes"] += len(texts[page_id].encode("utf-8"))
        has_field, valid = meeting[page_id]
        entry["meeting_date_field"] += has_field
        entry["meeting_date_valid"] += valid
        if glossary[page_id] is not None:
            entry["glossary_tables"] += 1
            entry["glossary_rows"] += glossary[page_id]
    first = []
    for top_id, entry in sorted(first_level.items()):
        item = by_id.get(top_id) or folders.get(top_id) or {}
        title = item.get("title")
        first.append(
            {
                "id": top_id,
                "kind": "folder" if top_id in folders else "page",
                "known_type_name": title if title in KNOWN_TYPES else None,
            }
            | entry
        )
    return {
        "parent_types": sorted(Counter(str(p.get("parentType")) for p in by_id.values()).items()),
        "depth_from_home": sorted(depth.items()),
        "pages_outside_home": outside_home,
        "folders": len(folders),
        "first_level": first,
    }


def finish(result, client, started, skipped) -> dict:
    result["requests"] = {
        "sent": client.sent,
        "by_endpoint_status": {k: sorted(v.items()) for k, v in sorted(client.statuses.items())},
        "retries_429": dict(client.retries),
        "skipped": skipped,
        "elapsed_seconds": round(time.monotonic() - started, 1),
    }
    result["run"] = {
        "measured_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%MZ"),
        "script_sha256_12": hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:12],
        "python": platform.python_version(),
    }
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--space-key", default="SCRUM")
    parser.add_argument("--env-file", default=".env")
    parser.add_argument("--max-requests", type=int, default=1500)
    parser.add_argument("--dry-run", action="store_true", help="요청 없이 단계와 상한만 출력한다")
    args = parser.parse_args()
    if args.dry_run:
        print(
            json.dumps(
                {
                    "steps": [
                        "GET /spaces?keys=<space> (1)",
                        "GET /spaces/{id}/permissions (ceil(assignments/250))",
                        "GET /spaces/{id}/pages?body-format=atlas_doc_format&status=current (ceil(N/250))",
                        "GET /folders/{id} (folders)",
                        "GET /pages/{id}/ancestors?limit=1 (1, scope probe)",
                        "GET /pages/{id}/restriction-state (N)",
                        "GET /folders/{id}/restriction-state (folders)",
                    ],
                    "max_requests": args.max_requests,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    print(json.dumps(measure(args), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
