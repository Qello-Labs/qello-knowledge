"""저장소 경계. 계약 내용은 QK-STO-001이 정한다."""

from typing import Protocol


class Store(Protocol):
    """청크와 벡터를 저장하고 검색한다."""
