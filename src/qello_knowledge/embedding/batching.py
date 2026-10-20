"""묶음 나누기(research R-05, R-06).

- 요청 하나에 텍스트 최대 32개, 예상 토큰 합 최대 32,768.
- 예상 토큰이 입력 한도의 75%를 넘는 텍스트는 다른 텍스트와 묶지 않는다.
- 여러 텍스트 요청이 입력 한도 초과로 거부되면 반으로 나눠 원인 텍스트를 찾는다.
"""

from __future__ import annotations

from collections.abc import Sequence

MAX_ITEMS = 32
MAX_TOKENS = 32_768
SOLO_RATIO = 0.75


def make_batches(
    token_counts: Sequence[int],
    max_input_tokens: int,
    max_items: int = MAX_ITEMS,
    max_tokens: int = MAX_TOKENS,
) -> list[tuple[int, ...]]:
    """입력 순서를 지키는 위치 묶음 목록을 돌려준다."""
    solo_limit = max_input_tokens * SOLO_RATIO
    batches: list[tuple[int, ...]] = []
    current: list[int] = []
    current_tokens = 0
    for position, tokens in enumerate(token_counts):
        if tokens > solo_limit:
            if current:
                batches.append(tuple(current))
                current, current_tokens = [], 0
            batches.append((position,))
            continue
        if current and (len(current) >= max_items or current_tokens + tokens > max_tokens):
            batches.append(tuple(current))
            current, current_tokens = [], 0
        current.append(position)
        current_tokens += tokens
    if current:
        batches.append(tuple(current))
    return batches


def split_half(batch: tuple[int, ...]) -> tuple[tuple[int, ...], tuple[int, ...]]:
    middle = len(batch) // 2
    return batch[:middle], batch[middle:]
