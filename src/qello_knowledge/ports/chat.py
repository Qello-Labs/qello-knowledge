"""채팅 창구 경계. 계약 내용은 QK-BOT-001이 정한다."""

from typing import Protocol


class ChatChannel(Protocol):
    """질문을 받고 답변을 돌려준다."""
