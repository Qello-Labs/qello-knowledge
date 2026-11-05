"""`RepoHistory` 구현(QK-STO-002 research R-09).

저장소의 `git` 명령을 읽기로만 부른다. 네트워크(`fetch`)는 하지 않는다.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class GitHistory:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = Path(repo_root)

    def _git(self, *args: str) -> subprocess.CompletedProcess[bytes]:
        git = shutil.which("git")
        if git is None:
            return subprocess.CompletedProcess(args, 127, b"", b"")
        # 인자는 이 모듈의 고정 값과 저장소 상대 경로·커밋 해시뿐이다(devtools/eval_cli.py `_git_state`와 같은 방식).
        return subprocess.run([git, "-C", str(self.repo_root), *args], capture_output=True, check=False)  # noqa: S603

    def first_added_commit(self, ref: str, path: str) -> str | None:
        result = self._git(
            "log",
            "--first-parent",
            "--diff-merges=first-parent",
            "--diff-filter=A",
            "--no-patch",
            "--format=%H",
            ref,
            "--",
            path,
        )
        if result.returncode != 0:
            return None
        lines = [line for line in result.stdout.decode().splitlines() if line.strip()]
        return lines[-1] if lines else None

    def file_at(self, ref: str, path: str) -> bytes | None:
        result = self._git("show", f"{ref}:{path}")
        return result.stdout if result.returncode == 0 else None

    def list_paths(self, ref: str, directory: str) -> tuple[str, ...]:
        result = self._git("ls-tree", "--name-only", ref, directory.rstrip("/") + "/")
        if result.returncode != 0:
            return ()
        return tuple(line for line in result.stdout.decode().splitlines() if line.strip())

    def is_ancestor(self, ancestor: str, commit: str) -> bool:
        return self._git("merge-base", "--is-ancestor", ancestor, commit).returncode == 0

    def head(self) -> tuple[str | None, bool]:
        head = self._git("rev-parse", "HEAD")
        status = self._git("status", "--porcelain")
        sha = head.stdout.decode().strip() if head.returncode == 0 else None
        return sha, bool(status.stdout.strip()) if status.returncode == 0 else True
