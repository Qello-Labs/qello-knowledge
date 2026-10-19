"""생성 경계. 계약 내용은 QK-GEN-001이 정한다."""

from typing import Protocol


class Generator(Protocol):
    """검색된 근거로 답변을 만든다."""
