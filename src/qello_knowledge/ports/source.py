"""자료원 경계. 계약 내용은 QK-ING-001이 정한다."""

from typing import Protocol


class SourceAdapter(Protocol):
    """원본 자료원을 읽기 전용으로 수집한다(C-09)."""
