"""비밀값 규칙. 커밋 검사(`scripts/preflight.py`)와 색인 필터가 함께 쓰는 유일한 목록이다.

`preflight.py`는 이 파일을 패키지 설치 없이 경로로 불러온다. CI의 시스템 Python(3.12)에서도 돌도록
3.12 문법과 `re`만 쓴다. 맞은 문자열은 어디에도 돌려주지 않는다.
"""

from __future__ import annotations

import re
from typing import NamedTuple


class SecretRule(NamedTuple):
    name: str
    pattern: re.Pattern[str]


class SecretHit(NamedTuple):
    rule: str
    line: int


KEY_NAME_PATTERN = (
    r"[A-Za-z0-9_]*(?:password|passwd|api[_-]?key|api[_-]?token|auth[_-]?token"
    r"|secret[_-]?key|access[_-]?token|client[_-]?secret|token|secret)"
)
PLACEHOLDER = r"(?!\$\{|<|example|redacted|masked|changeme|dummy)"
RULES = (
    SecretRule("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    SecretRule("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    SecretRule("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{30,}\b")),
    SecretRule("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    SecretRule("anthropic-key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    SecretRule("openai-key", re.compile(r"\bsk-(?!ant-)(?:proj-)?[A-Za-z0-9_-]{32,}")),
    SecretRule("notion-token", re.compile(r"\b(?:secret|ntn)_[A-Za-z0-9]{40,}\b")),
    SecretRule("figma-token", re.compile(r"\bfigd_[A-Za-z0-9_-]{30,}")),
    SecretRule("atlassian-token", re.compile(r"\bATATT[A-Za-z0-9_=-]{20,}")),
    SecretRule("github-fine-grained-token", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{22,}")),
    SecretRule("cloudflare-account-token", re.compile(r"\bcfat_[A-Za-z0-9_-]{20,}")),
    SecretRule("discord-bot-token", re.compile(r"\b[MNO][A-Za-z0-9_-]{23,27}\.[A-Za-z0-9_-]{6}\.[A-Za-z0-9_-]{27,}")),
    SecretRule("clickup-token", re.compile(r"\bpk_\d{3,}_[A-Z0-9]{20,}")),
    SecretRule(
        "db-url-with-password",
        re.compile(r"(?i)\bpostgres(?:ql)?(?:\+\w+)?://[^:/\s@]+:(?!<|\$\{)[^@\s]{3,}@"),
    ),
    # 코드의 `api_key = settings.api_key` 같은 참조는 잡지 않도록 따옴표로 감싼 값만 본다.
    SecretRule(
        "assigned-secret",
        re.compile(
            rf"(?i)\b{KEY_NAME_PATTERN}[\"']?\s*(?::\s*[\w\[\]|. ]+?\s*)?[:=]\s*[\"']"
            rf"{PLACEHOLDER}[^\s\"']{{12,}}[\"']"
        ),
    ),
    SecretRule(
        "env-assigned-secret",
        re.compile(
            r"^\s*(?:export\s+)?[A-Z0-9_]*(?:PASSWORD|PASSWD|API_KEY|API_TOKEN|AUTH_TOKEN"
            r"|SECRET|ACCESS_TOKEN|PRIVATE_KEY|TOKEN)[A-Z0-9_]*\s*=\s*[\"']?"
            r"(?!\$\{|<|example|redacted|masked|changeme|dummy)[^\s#\"']{12,}"
        ),
    ),
)

# 반드시 잡을 종류와 그 종류를 잡는 규칙(FR-009). 수용 시험(SC-001)은 규칙 목록이 아니라 이 목록으로 만든다.
REQUIRED_KINDS = {
    "github-classic": ("github-token",),
    "github-fine-grained": ("github-fine-grained-token",),
    "cloudflare-account": ("cloudflare-account-token",),
    "discord-bot": ("discord-bot-token",),
    "clickup": ("clickup-token",),
    "anthropic": ("anthropic-key",),
    "openai": ("openai-key",),
    "atlassian": ("atlassian-token",),
    "figma": ("figma-token",),
    "notion": ("notion-token",),
    "slack": ("slack-token",),
    "aws": ("aws-access-key",),
    "private-key": ("private-key",),
    "db-url": ("db-url-with-password",),
}


def find_secrets(text: str, skip: frozenset[str] = frozenset()) -> tuple[SecretHit, ...]:
    """줄마다 모든 규칙을 맞춘다. `skip`에 든 규칙 이름은 건너뛴다(오탐 예외)."""
    hits = []
    for number, line in enumerate(text.splitlines(), start=1):
        for rule in RULES:
            if rule.name not in skip and rule.pattern.search(line):
                hits.append(SecretHit(rule.name, number))
    return tuple(hits)
