#!/usr/bin/env python3
"""Create a Jira sub-task for a GitHub Issue opened from the work form. Writes to Jira and the Issue comments."""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field


PARENT_HEADING = "Jira 상위 이슈 키"
EXISTING_HEADING = "기존 Jira 이슈 키"
WORK_TYPE_HEADING = "작업 종류"
SUMMARY_HEADINGS = ("기능명세서 ID", "기능명세서 링크", "팀 스프린트 ID", WORK_TYPE_HEADING)
BLOCK_HEADINGS = ("이번 주 산출물·구현 범위", "완료 조건·검증 방법")
NO_RESPONSE = "_No response_"

CREATED_MARKER = "<!-- jira-subtask: {key} -->"
CREATED_MARKER_PATTERN = re.compile(r"<!-- jira-subtask: ([A-Z][A-Z0-9]*-[0-9]+) -->")
FAILED_MARKER = "<!-- jira-subtask-failed -->"

ALLOWED_AUTHORS = {"OWNER", "MEMBER", "COLLABORATOR"}
# 작업 종류 → 권장 브랜치 type. 구현은 feat, 조사는 docs, 도구·기술부채는 chore로 제안한다(/roadmap-explain과 같은 기준).
BRANCH_TYPES = {"feature": "feat", "bug": "fix", "tech-debt": "chore", "research": "docs"}


class ApiError(RuntimeError):
    pass


@dataclass
class Config:
    jira_base_url: str = ""
    jira_email: str = ""
    jira_token: str = ""
    project_key: str = "SCRUM"
    part_label: str = "team-backend"
    sprint_field: str = "customfield_10020"
    subtask_type: str = "Subtask"
    github_token: str = ""
    repository: str = ""
    github_api_url: str = "https://api.github.com"

    @classmethod
    def from_env(cls, env: dict[str, str]) -> "Config":
        def value(name: str, default: str = "") -> str:
            return (env.get(name) or default).strip()

        return cls(
            jira_base_url=value("JIRA_BASE_URL").rstrip("/"),
            jira_email=value("JIRA_USER_EMAIL"),
            jira_token=value("JIRA_API_TOKEN"),
            project_key=value("JIRA_PROJECT_KEY", "SCRUM"),
            part_label=value("JIRA_PART_LABEL", "team-backend"),
            sprint_field=value("JIRA_SPRINT_FIELD", "customfield_10020"),
            subtask_type=value("JIRA_SUBTASK_TYPE", "Subtask"),
            github_token=value("GITHUB_TOKEN"),
            repository=value("GITHUB_REPOSITORY"),
            github_api_url=value("GITHUB_API_URL", "https://api.github.com").rstrip("/"),
        )

    def has_jira(self) -> bool:
        return bool(self.jira_base_url and self.jira_email and self.jira_token)

    def browse_url(self, key: str) -> str:
        return f"{self.jira_base_url}/browse/{key}"


@dataclass
class Result:
    action: str  # created | skipped | failed
    message: str
    comment: str | None = None
    payload: dict | None = None
    created_key: str | None = None
    notes: list[str] = field(default_factory=list)


def call(method: str, url: str, headers: dict[str, str], payload: dict | None = None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method, headers={"Accept": "application/json", **headers})
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
    except urllib.error.HTTPError as error:
        raise ApiError(f"{method} {urllib.parse.urlsplit(url).path} → HTTP {error.code}: {error_detail(error)}") from None
    except urllib.error.URLError as error:
        raise ApiError(f"{method} {urllib.parse.urlsplit(url).path} → 연결 실패: {error.reason}") from None
    return json.loads(body) if body else {}


def error_detail(error: urllib.error.HTTPError) -> str:
    """Jira·GitHub 오류 본문에서 메시지만 꺼낸다. 요청 헤더나 토큰은 담지 않는다."""
    try:
        body = json.loads(error.read() or b"{}")
    except ValueError:
        return error.reason or ""
    parts = list(body.get("errorMessages") or [])
    parts += [f"{name}: {text}" for name, text in (body.get("errors") or {}).items()]
    if body.get("message"):
        parts.append(body["message"])
    return "; ".join(parts)[:300] or (error.reason or "")


class JiraClient:
    def __init__(self, config: Config) -> None:
        credentials = f"{config.jira_email}:{config.jira_token}".encode("utf-8")
        self._headers = {"Authorization": "Basic " + base64.b64encode(credentials).decode("ascii")}
        self._base = config.jira_base_url
        self._sprint_field = config.sprint_field

    def get_issue(self, key: str) -> dict | None:
        fields = f"summary,issuetype,project,{self._sprint_field}"
        url = f"{self._base}/rest/api/3/issue/{urllib.parse.quote(key)}?fields={fields}"
        try:
            return call("GET", url, self._headers)
        except ApiError as error:
            if "HTTP 404" in str(error):
                return None
            raise

    def create_issue(self, payload: dict) -> str:
        return call("POST", f"{self._base}/rest/api/3/issue", self._headers, payload)["key"]


class GitHubClient:
    def __init__(self, config: Config) -> None:
        self._headers = {
            "Authorization": f"Bearer {config.github_token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        self._base = f"{config.github_api_url}/repos/{config.repository}"

    def get_issue(self, number: int) -> dict:
        return call("GET", f"{self._base}/issues/{number}", self._headers)

    def list_comments(self, number: int) -> list[dict]:
        comments: list[dict] = []
        page = 1
        while True:
            batch = call("GET", f"{self._base}/issues/{number}/comments?per_page=100&page={page}", self._headers)
            comments.extend(batch)
            if len(batch) < 100:
                return comments
            page += 1

    def create_comment(self, number: int, body: str) -> None:
        call("POST", f"{self._base}/issues/{number}/comments", self._headers, {"body": body})


def parse_form(body: str) -> dict[str, str]:
    """Issue 폼 본문(`### 칸 이름` 다음 값)을 칸 이름 → 값으로 읽는다. 비워 둔 칸은 빈 문자열이다."""
    sections: dict[str, str] = {}
    heading: str | None = None
    lines: list[str] = []
    for line in (body or "").splitlines():
        if line.startswith("### "):
            if heading is not None:
                sections[heading] = clean_value(lines)
            heading, lines = line[4:].strip(), []
        elif heading is not None:
            lines.append(line)
    if heading is not None:
        sections[heading] = clean_value(lines)
    return sections


def clean_value(lines: list[str]) -> str:
    text = "\n".join(lines).strip()
    return "" if text == NO_RESPONSE else text


def created_key(comments: list[dict]) -> str | None:
    for comment in comments:
        match = CREATED_MARKER_PATTERN.search(comment.get("body") or "")
        if match:
            return match.group(1)
    return None


def active_sprints(parent: dict, sprint_field: str) -> list[str]:
    sprints = (parent.get("fields") or {}).get(sprint_field) or []
    return [sprint.get("name", "") for sprint in sprints if sprint.get("state") == "active"]


def text_node(value: str, *marks: dict) -> dict:
    node = {"type": "text", "text": value}
    if marks:
        node["marks"] = list(marks)
    return node


def paragraph(*nodes: dict) -> dict:
    return {"type": "paragraph", "content": list(nodes)}


def description(issue_url: str, sections: dict[str, str]) -> dict:
    """Jira 설명(Atlassian Document Format). 폼의 요약 칸과 산출물·완료 조건을 옮긴다."""
    content = [paragraph(text_node("GitHub Issue: ", {"type": "strong"}),
                         text_node(issue_url, {"type": "link", "attrs": {"href": issue_url}}))]
    for heading in SUMMARY_HEADINGS:
        if sections.get(heading):
            content.append(paragraph(text_node(f"{heading}: ", {"type": "strong"}), text_node(sections[heading])))
    for heading in BLOCK_HEADINGS:
        lines = [line.strip() for line in sections.get(heading, "").splitlines() if line.strip()]
        if lines:
            content.append({"type": "heading", "attrs": {"level": 3}, "content": [text_node(heading)]})
            content.extend(paragraph(text_node(line)) for line in lines)
    return {"type": "doc", "version": 1, "content": content}


def build_payload(issue: dict, sections: dict[str, str], parent_key: str, config: Config) -> dict:
    labels = []
    work_type = sections.get(WORK_TYPE_HEADING, "")
    if work_type in BRANCH_TYPES:
        labels.append(work_type)
    if config.part_label:
        labels.append(config.part_label)
    return {
        "fields": {
            "project": {"key": config.project_key},
            "parent": {"key": parent_key},
            "issuetype": {"name": config.subtask_type},
            "summary": issue["title"].strip()[:255],
            "labels": labels,
            "description": description(issue["html_url"], sections),
        }
    }


def created_comment(key: str, parent_key: str, sprints: list[str] | None, issue: dict,
                    sections: dict[str, str], config: Config) -> str:
    branch_type = BRANCH_TYPES.get(sections.get(WORK_TYPE_HEADING, ""), "<type>")
    lines = [
        CREATED_MARKER.format(key=key),
        f"Jira 하위 작업 [{key}]({config.browse_url(key)})을 "
        f"[{parent_key}]({config.browse_url(parent_key)}) 아래에 만들었습니다.",
    ]
    if sprints:
        lines += ["", f"스프린트는 상위 이슈를 따라 {', '.join(sprints)}입니다."]
    elif sprints is not None:
        lines += ["", (
            f"상위 이슈 {parent_key}가 활성 스프린트에 없어 이 하위 작업도 스프린트에 들어가지 않았습니다. "
            "주간 계획에서 정한 활성 스프린트로 상위 이슈를 옮기면 하위 작업도 함께 옮겨집니다."
        )]
    lines += [
        "",
        "작업 브랜치는 최신 `main`에서 다음 형식으로 만듭니다. 브랜치 이름의 Jira 키로 Jira 개발 패널에 연결됩니다.",
        "",
        "```text",
        f"{branch_type}/{key}-gh-{issue['number']}-<short-slug>",
        "```",
    ]
    return "\n".join(lines)


def failed_comment(reason: str) -> str:
    return "\n".join([
        FAILED_MARKER,
        f"Jira 하위 작업을 만들지 못했습니다. {reason}",
        "",
        "고친 뒤 Actions의 `Jira subtask` 워크플로를 이 Issue 번호로 수동 실행합니다.",
    ])


def process(issue: dict, comments: list[dict], jira, config: Config, *, dry_run: bool) -> Result:
    if "pull_request" in issue:
        return Result("skipped", "Pull Request라 건너뛴다.")
    if issue.get("author_association") not in ALLOWED_AUTHORS:
        return Result("skipped", f"작성자 권한({issue.get('author_association')})이 대상이 아니라 건너뛴다.")
    sections = parse_form(issue.get("body") or "")
    if PARENT_HEADING not in sections:
        return Result("skipped", f"'{PARENT_HEADING}' 칸이 없어 작업 폼 Issue가 아니라고 보고 건너뛴다.")
    if sections.get(EXISTING_HEADING):
        return Result("skipped", f"기존 Jira 이슈 {sections[EXISTING_HEADING]}가 있어 만들지 않는다.")
    existing = created_key(comments)
    if existing:
        return Result("skipped", f"이미 {existing}을 만든 댓글이 있어 만들지 않는다.")

    parent_key = sections[PARENT_HEADING].strip().upper()
    if not re.fullmatch(rf"{re.escape(config.project_key)}-[0-9]+", parent_key):
        reason = f"'{PARENT_HEADING}' 값 `{parent_key or '(빈칸)'}`가 `{config.project_key}-<번호>` 형식이 아닙니다."
        return Result("failed", reason, comment=failed_comment(reason))

    sprints: list[str] | None = None
    notes: list[str] = []
    if jira is None:
        notes.append("Jira 접속 정보가 없어 상위 이슈 확인을 건너뛰었다.")
    else:
        parent = jira.get_issue(parent_key)
        if parent is None:
            reason = f"상위 이슈 {parent_key}를 찾지 못했습니다."
            return Result("failed", reason, comment=failed_comment(reason))
        if ((parent.get("fields") or {}).get("issuetype") or {}).get("subtask"):
            reason = f"{parent_key}는 하위 작업이라 그 아래에 하위 작업을 만들 수 없습니다. 상위 작업의 키를 입력합니다."
            return Result("failed", reason, comment=failed_comment(reason))
        sprints = active_sprints(parent, config.sprint_field)

    payload = build_payload(issue, sections, parent_key, config)
    if dry_run:
        key = f"{config.project_key}-<번호>"
        comment = created_comment(key, parent_key, sprints, issue, sections, config)
        return Result("created", "dry-run: Jira와 GitHub에 쓰지 않았다.", comment=comment, payload=payload, notes=notes)

    key = jira.create_issue(payload)
    comment = created_comment(key, parent_key, sprints, issue, sections, config)
    return Result("created", f"{key}를 {parent_key} 아래에 만들었다.", comment=comment, payload=payload,
                  created_key=key, notes=notes)


def load_issue(args: argparse.Namespace, config: Config, github: GitHubClient | None) -> dict:
    number = args.issue or os.environ.get("ISSUE_NUMBER", "").strip()
    if number:
        if github is None:
            raise ApiError("Issue 번호로 실행하려면 GITHUB_TOKEN과 GITHUB_REPOSITORY가 필요하다.")
        return github.get_issue(int(number))
    path = args.event or os.environ.get("GITHUB_EVENT_PATH")
    if not path:
        raise ApiError("--event 또는 GITHUB_EVENT_PATH가 필요하다.")
    with open(path, encoding="utf-8") as handle:
        event = json.load(handle)
    if "issue" not in event:
        raise ApiError("이벤트에 issue가 없다.")
    return event["issue"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", help="GitHub 이벤트 JSON 경로. 없으면 GITHUB_EVENT_PATH를 쓴다")
    parser.add_argument("--issue", help="이 번호의 Issue를 GitHub API로 읽어 처리한다(수동 실행용)")
    parser.add_argument("--dry-run", action="store_true", help="Jira·GitHub에 쓰지 않고 만들 내용만 출력한다")
    args = parser.parse_args()

    config = Config.from_env(dict(os.environ))
    github = GitHubClient(config) if config.github_token and config.repository else None
    jira = JiraClient(config) if config.has_jira() else None
    if jira is None and not args.dry_run:
        print("JIRA_BASE_URL, JIRA_USER_EMAIL, JIRA_API_TOKEN Secret이 필요하다.", file=sys.stderr)
        return 2

    issue: dict | None = None
    try:
        issue = load_issue(args, config, github)
        comments = github.list_comments(issue["number"]) if github else []
        result = process(issue, comments, jira, config, dry_run=args.dry_run)
    except ApiError as error:
        result = Result("failed", str(error), comment=failed_comment(f"API 호출이 실패했습니다: {error}"))

    print(f"[{result.action}] {result.message}")
    for note in result.notes:
        print(f"참고: {note}")
    if args.dry_run:
        if result.payload is not None:
            print(json.dumps(result.payload, ensure_ascii=False, indent=2))
        if result.comment:
            print("--- GitHub 댓글 ---")
            print(result.comment)
    elif result.comment and issue and github:
        try:
            github.create_comment(issue["number"], result.comment)
        except ApiError as error:
            print(f"GitHub 댓글을 남기지 못했다: {error}", file=sys.stderr)
            return 1
    return 1 if result.action == "failed" else 0


if __name__ == "__main__":
    sys.exit(main())
