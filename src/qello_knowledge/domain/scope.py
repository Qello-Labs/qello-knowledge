"""경로 전체를 맞추며, 겹치면 제외가 이긴다."""

from pathlib import PurePosixPath


def in_scope(location: str, include: tuple[str, ...], exclude: tuple[str, ...]) -> bool:
    if not include:
        raise ValueError("포함 패턴이 필요하다")
    path = PurePosixPath(location)
    return any(path.full_match(p, case_sensitive=True) for p in include) and not any(
        path.full_match(p, case_sensitive=True) for p in exclude
    )
