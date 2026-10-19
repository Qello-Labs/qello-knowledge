#!/usr/bin/env python3
"""Detect tracked environment files and obvious secrets without printing values."""

from __future__ import annotations

import argparse
import importlib.util
import subprocess
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
# 오탐 예외 목록. 한 줄에 `경로:규칙 이름 # 사유` 하나. 사유가 없으면 검사가 실패한다. 규칙을 끄는 옵션은 두지 않는다.
ALLOWLIST = ROOT / "scripts" / "preflight_allowlist.txt"
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
# 규칙은 색인 필터와 한 벌이다(QK-SEC-001 FR-009). 패키지 설치 없이 경로로 불러온다.
RULES_RELATIVE = "src/qello_knowledge/domain/secret_rules.py"
RULES_MODULE = ROOT / RULES_RELATIVE


def load_rules(staged: bool) -> tuple | None:
    """`--staged`면 index에 있는 규칙으로 검사한다. index에 없으면 `None`."""
    if staged:
        result = subprocess.run(
            ["git", "show", f":{RULES_RELATIVE}"],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
        if result.returncode != 0:
            return None
        module = types.ModuleType("qk_secret_rules")
        sys.modules[module.__name__] = module
        exec(compile(result.stdout.decode("utf-8"), RULES_RELATIVE, "exec"), module.__dict__)
        return module.RULES
    spec = importlib.util.spec_from_file_location("qk_secret_rules", RULES_MODULE)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module.RULES


# 다른 시험이 `preflight.RULES`를 직접 읽는다. 작업 트리 규칙과 같다.
RULES = load_rules(staged=False)


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
            and path.resolve() not in {Path(__file__).resolve(), RULES_MODULE.resolve()}
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


def load_allowlist(path: Path = ALLOWLIST) -> tuple[set[tuple[str, str]], list[str]]:
    """예외 목록을 읽는다. 돌려주는 값은 (경로, 규칙 이름) 집합과 형식 오류 목록이다."""
    entries: set[tuple[str, str]] = set()
    errors: list[str] = []
    if not path.is_file():
        return entries, errors
    for line_number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        target, _, reason = line.partition("#")
        relative, _, rule_name = target.strip().rpartition(":")
        if not relative or not rule_name or not reason.strip():
            errors.append(f"{path.relative_to(ROOT)}:{line_number}: allowlist-entry-needs-path-rule-and-reason")
            continue
        entries.add((relative, rule_name))
    return entries, errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--staged",
        action="store_true",
        help="inspect only the exact staged blobs",
    )
    args = parser.parse_args()
    rules = load_rules(args.staged)
    if rules is None:
        print("Secret preflight failed. Matched values are intentionally hidden.")
        print(f"- {RULES_RELATIVE}: rules-module-not-staged")
        return 1
    allowed, findings = load_allowlist()
    paths = candidate_paths(args.staged)
    for path in tracked_environment_files(args.staged):
        findings.append(f"{path.relative_to(ROOT)}: tracked-env-file")

    for path in paths:
        try:
            lines = read_lines(path, args.staged)
        except (UnicodeDecodeError, OSError):
            continue
        for line_number, line in enumerate(lines, start=1):
            for rule_name, pattern in rules:
                if (path.relative_to(ROOT).as_posix(), rule_name) in allowed:
                    continue
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
