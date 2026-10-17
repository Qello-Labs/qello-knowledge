#!/usr/bin/env python3
"""Detect tracked environment files and obvious secrets without printing values."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKIP_PARTS = {
    ".git",
    ".idea",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "out",
    "venv",
}
# 평가 세트(.jsonl, .csv)와 노트북은 실제 팀 질문이 섞일 수 있어 검사 대상에 포함한다.
TEXT_SUFFIXES = {
    "",
    ".cfg",
    ".conf",
    ".csv",
    ".hcl",
    ".html",
    ".ini",
    ".ipynb",
    ".js",
    ".json",
    ".jsonl",
    ".md",
    ".mjs",
    ".properties",
    ".py",
    ".sh",
    ".sql",
    ".tf",
    ".tfvars",
    ".toml",
    ".ts",
    ".txt",
    ".yaml",
    ".yml",
    ".zsh",
}
SECRET_NAME = (
    r"[A-Za-z0-9_]*(?:password|passwd|api[_-]?key|api[_-]?token|auth[_-]?token"
    r"|secret[_-]?key|access[_-]?token|client[_-]?secret)"
)
PLACEHOLDER = r"(?!\$\{|<|example|redacted|masked|changeme|dummy)"
RULES = (
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{30,}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("anthropic-key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}")),
    ("openai-key", re.compile(r"\bsk-(?!ant-)(?:proj-)?[A-Za-z0-9_-]{32,}")),
    ("notion-token", re.compile(r"\b(?:secret|ntn)_[A-Za-z0-9]{40,}\b")),
    ("figma-token", re.compile(r"\bfigd_[A-Za-z0-9_-]{30,}")),
    ("atlassian-token", re.compile(r"\bATATT[A-Za-z0-9_=-]{20,}")),
    (
        "db-url-with-password",
        re.compile(r"(?i)\bpostgres(?:ql)?(?:\+\w+)?://[^:/\s@]+:(?!<|\$\{)[^@\s]{3,}@"),
    ),
    # 코드의 `api_key = settings.api_key` 같은 참조는 잡지 않도록 따옴표로 감싼 값만 본다.
    (
        "assigned-secret",
        re.compile(
            rf"(?i)\b{SECRET_NAME}[\"']?\s*(?::\s*[\w\[\]|. ]+?\s*)?[:=]\s*[\"']"
            rf"{PLACEHOLDER}[^\s\"']{{12,}}[\"']"
        ),
    ),
    (
        "env-assigned-secret",
        re.compile(
            r"^\s*(?:export\s+)?[A-Z0-9_]*(?:PASSWORD|PASSWD|API_KEY|API_TOKEN|AUTH_TOKEN"
            r"|SECRET|ACCESS_TOKEN|PRIVATE_KEY)[A-Z0-9_]*\s*=\s*"
            r"(?!\$\{|<|example|redacted|masked|changeme|dummy)[^\s#\"']{12,}"
        ),
    ),
)


def git_paths(*arguments: str) -> list[Path]:
    result = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [ROOT / line for line in result.stdout.splitlines() if line]


def staged_paths() -> list[Path]:
    result = subprocess.run(
        [
            "git",
            "diff",
            "--cached",
            "--name-only",
            "--diff-filter=ACMR",
            "-z",
        ],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [
        ROOT / item.decode("utf-8", errors="surrogateescape")
        for item in result.stdout.split(b"\0")
        if item
    ]


def candidate_paths(staged: bool) -> list[Path]:
    paths = (
        staged_paths()
        if staged
        else git_paths("ls-files", "-co", "--exclude-standard")
    )
    return sorted(
        {
            path
            for path in paths
            if path.is_file()
            and path.resolve() != Path(__file__).resolve()
            and not SKIP_PARTS.intersection(path.relative_to(ROOT).parts)
            and path.suffix.lower() in TEXT_SUFFIXES
        }
    )


def tracked_environment_files(staged: bool) -> list[Path]:
    tracked = staged_paths() if staged else git_paths("ls-files")
    return [
        path
        for path in tracked
        if path.name.startswith(".env")
        and path.name not in {".env.example", ".env.template", ".env.sample"}
    ]


def read_lines(path: Path, staged: bool) -> list[str]:
    if not staged:
        return path.read_text(encoding="utf-8").splitlines()
    relative = path.relative_to(ROOT).as_posix()
    result = subprocess.run(
        ["git", "show", f":{relative}"],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise OSError(f"unable to read staged file: {relative}")
    return result.stdout.decode("utf-8").splitlines()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--staged",
        action="store_true",
        help="inspect only the exact staged blobs",
    )
    args = parser.parse_args()
    findings: list[str] = []
    paths = candidate_paths(args.staged)
    for path in tracked_environment_files(args.staged):
        findings.append(f"{path.relative_to(ROOT)}: tracked-env-file")

    for path in paths:
        try:
            lines = read_lines(path, args.staged)
        except (UnicodeDecodeError, OSError):
            continue
        for line_number, line in enumerate(lines, start=1):
            for rule_name, pattern in RULES:
                if pattern.search(line):
                    findings.append(
                        f"{path.relative_to(ROOT)}:{line_number}: {rule_name}"
                    )

    if findings:
        print("Secret preflight failed. Matched values are intentionally hidden.")
        for finding in findings:
            print(f"- {finding}")
        return 1

    scope = "staged" if args.staged else "repository"
    print(f"Secret preflight passed: {len(paths)} {scope} text files inspected.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
