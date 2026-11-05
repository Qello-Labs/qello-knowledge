"""저장소 git 이력 읽기 경계(QK-STO-002 research R-09). 판정과 활성화가 정책 병합 여부를 확인할 때 쓴다."""

from __future__ import annotations

from typing import Protocol


class RepoHistory(Protocol):
    def first_added_commit(self, ref: str, path: str) -> str | None:
        """`ref` 첫 부모 이력에서 `path`를 처음 들여온 커밋. 없으면 `None`."""

    def file_at(self, ref: str, path: str) -> bytes | None:
        """`ref` 시점의 파일 바이트. 없으면 `None`."""

    def list_paths(self, ref: str, directory: str) -> tuple[str, ...]:
        """`ref` 시점 `directory` 바로 아래 경로(저장소 상대)."""

    def is_ancestor(self, ancestor: str, commit: str) -> bool:
        """`ancestor`가 `commit`의 조상이거나 같으면 참. 커밋을 모르면 거짓."""

    def head(self) -> tuple[str | None, bool]:
        """지금 체크아웃 커밋과 커밋하지 않은 변경 유무."""
