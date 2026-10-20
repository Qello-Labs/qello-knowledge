"""한 커밋의 GitHub 저장소 파일을 읽는 어댑터."""

import json
import re
from dataclasses import dataclass, field
from datetime import UTC, datetime
from hashlib import sha1
from pathlib import PurePosixPath
from urllib.parse import quote

from qello_knowledge.domain.source import (
    AccessInfo,
    AccessStatus,
    ChangeKeyKind,
    ContentFormat,
    FailureType,
    InvalidResponse,
    ListPage,
    OriginState,
    RateLimitHint,
    ResponseClass,
    ResponseOutcome,
    SourceContent,
    SourceFailure,
    SourceItem,
    SourceRequest,
    SourceResponse,
    default_classify,
    default_rate_limit_hint,
)
from qello_knowledge.domain.source_config import SourceConfig
from qello_knowledge.ports.source import SourceSession


@dataclass(frozen=True)
class ListSnapshot:
    commit_sha: str
    visibility: str | None = field(repr=False)
    truncated: bool | None


def _sha(value: object) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{40}", value) is None:
        raise ValueError
    return value


def _object(response: SourceResponse) -> dict:
    try:
        value = json.loads(response.body)
        if not isinstance(value, dict):
            raise ValueError
        return value
    except (ValueError, UnicodeError):
        raise InvalidResponse() from None


def _repo_path(config: SourceConfig) -> str:
    owner, name = dict(config.scope.extra)["repo"].split("/")
    return quote(owner, safe="") + "/" + quote(name, safe="")


def _base(config: SourceConfig) -> str:
    return "https://api.github.com/repos/" + _repo_path(config)


def _json_request(url: str) -> SourceRequest:
    return SourceRequest("GET", url, {"Accept": "application/vnd.github+json"})


class GitHubRepoFilesAdapter:
    kind = "github_repo_files"

    def __init__(self) -> None:
        self._last_snapshot: ListSnapshot | None = None

    @property
    def last_snapshot(self) -> ListSnapshot | None:
        return self._last_snapshot

    def list_page(self, session: SourceSession, config: SourceConfig, cursor: str | None) -> ListPage:
        self._last_snapshot = None
        base = _base(config)
        repo = _object(session.send(_json_request(base)))
        visibility = repo.get("visibility")
        if not isinstance(visibility, str):
            visibility = None
        if type(repo.get("archived")) is not bool:
            raise InvalidResponse()
        try:
            commit = _object(
                session.send(_json_request(base + "/commits/" + quote(dict(config.scope.extra)["ref"], safe="")))
            )
        except SourceFailure as error:
            if error.http_status in {404, 422}:
                raise SourceFailure(FailureType.NOT_FOUND, error.http_status) from None
            raise
        try:
            commit_sha = _sha(commit["sha"])
            tree_sha = _sha(commit["commit"]["tree"]["sha"])
        except (KeyError, TypeError, ValueError):
            raise InvalidResponse() from None
        self._last_snapshot = ListSnapshot(commit_sha, visibility, None)
        tree = _object(session.send(_json_request(base + f"/git/trees/{tree_sha}?recursive=1")))
        try:
            if type(tree["truncated"]) is not bool or not isinstance(tree["tree"], list):
                raise ValueError
            items = []
            for row in tree["tree"]:
                path, mode, kind = row["path"], row["mode"], row["type"]
                if (
                    not isinstance(path, str)
                    or not path
                    or path.startswith("/")
                    or ".." in path.split("/")
                    or not isinstance(mode, str)
                    or not isinstance(kind, str)
                ):
                    raise ValueError
                if kind == "blob":
                    sha = _sha(row["sha"])
                    size = row["size"]
                    if type(size) is not int or size < 0:
                        raise ValueError
                    if mode in {"100644", "100755"}:
                        items.append(
                            SourceItem(
                                config.name,
                                self.kind,
                                path,
                                f"https://github.com/{_repo_path(config)}/blob/{commit_sha}/" + quote(path, safe="/"),
                                sha,
                                ChangeKeyKind.VERSION,
                                commit_sha,
                                None,
                                "repo_file",
                                None,
                                path,
                                size,
                                (
                                    AccessInfo(AccessStatus.PROVIDED, (("visibility", visibility),))
                                    if visibility is not None
                                    else AccessInfo(AccessStatus.UNKNOWN)
                                ),
                                OriginState.ARCHIVED if repo["archived"] else OriginState.ACTIVE,
                            )
                        )
            self._last_snapshot = ListSnapshot(commit_sha, visibility, tree["truncated"])
            return ListPage(tuple(sorted(items, key=lambda item: item.location)), None, not tree["truncated"])
        except (KeyError, TypeError, ValueError):
            raise InvalidResponse() from None

    def fetch_content(self, session: SourceSession, config: SourceConfig, item: SourceItem) -> SourceContent:
        response = session.send(
            SourceRequest(
                "GET", _base(config) + "/git/blobs/" + item.change_key, {"Accept": "application/vnd.github.raw+json"}
            )
        )
        raw = response.body
        digest = sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw, usedforsecurity=False).hexdigest()
        if digest != item.change_key:
            raise InvalidResponse()
        try:
            body = raw.decode("utf-8", errors="strict")
        except UnicodeError:
            raise InvalidResponse() from None
        extension = PurePosixPath(item.location).suffix.lower().removeprefix(".")
        content_format = ContentFormat.TEXT
        if extension in {"md", "mdx", "markdown"}:
            content_format = ContentFormat.MARKDOWN
        elif extension == "json":
            content_format = ContentFormat.JSON
        elif extension in {
            "py",
            "java",
            "kt",
            "js",
            "ts",
            "tsx",
            "jsx",
            "go",
            "rs",
            "c",
            "h",
            "cpp",
            "cs",
            "rb",
            "sh",
            "sql",
            "swift",
        }:
            content_format = ContentFormat.CODE
        return SourceContent(item.source_id, body, content_format, item.version, item.location, None)

    def classify(self, response: SourceResponse) -> ResponseClass:
        if response.status in {403, 429} and (
            response.headers.get("x-ratelimit-remaining") == "0" or "retry-after" in response.headers
        ):
            return ResponseClass(ResponseOutcome.TRANSIENT, FailureType.RATE_LIMITED)
        return default_classify(response)

    def rate_limit_hint(self, response: SourceResponse) -> RateLimitHint | None:
        remaining = _integer_header(response, "x-ratelimit-remaining")
        reset = _integer_header(response, "x-ratelimit-reset")
        retry = default_rate_limit_hint(response)
        retry_at = None
        if remaining == 0 and reset is not None:
            try:
                retry_at = datetime.fromtimestamp(reset, UTC)
            except (ValueError, OverflowError, OSError):
                pass
        if retry is not None:
            if retry.retry_at is not None:
                retry_at = max(retry_at, retry.retry_at) if retry_at is not None else retry.retry_at
            return RateLimitHint(0, retry.retry_after_seconds, retry_at)
        if remaining is not None:
            return RateLimitHint(remaining, retry_at=retry_at)
        return None


def _integer_header(response: SourceResponse, name: str) -> int | None:
    value = response.headers.get(name, "")
    if re.fullmatch(r"[0-9]+", value):
        try:
            return int(value)
        except ValueError:
            pass
    return None
