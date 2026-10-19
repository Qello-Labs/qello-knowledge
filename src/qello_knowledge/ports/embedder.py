"""임베딩 경계. 계약 내용은 QK-EMB-001이 정한다."""

from typing import Protocol


class Embedder(Protocol):
    """텍스트를 벡터로 바꾼다."""
