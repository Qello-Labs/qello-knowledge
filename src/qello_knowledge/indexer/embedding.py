"""임베딩 서비스 조립. `embedding/`이 모르는 QK-SEC-001 전송 검사와 QK-ING-001 재시도 규칙을 여기서 잇는다.

2026-10-20 사용자 결정(TASK.md): `embedding/`은 `domain`·`ports`만 가져오고, 검사·대기 계산은 생성 인자로 받는다.
"""

from __future__ import annotations

from qello_knowledge.domain.embedding import SendBlock
from qello_knowledge.domain.source_config import RetryPolicy
from qello_knowledge.ports.embedder import OutgoingCheck, RetryDelay
from qello_knowledge.security.policy import SecurityPolicy
from qello_knowledge.security.send_gate import OutgoingPiece, check_outgoing
from qello_knowledge.sources.clock import Clock, SystemClock
from qello_knowledge.sources.retry import Jitter, next_delay, system_jitter


def security_outgoing_check(policy: SecurityPolicy) -> OutgoingCheck:
    """텍스트 하나를 출처와 함께 QK-SEC-001 전송 직전 검사에 넘긴다. 출처의 예외만 적용된다."""

    def check(text: str, origin: tuple[str, str] | None) -> tuple[SendBlock, ...]:
        result = check_outgoing([OutgoingPiece(text, origin)], policy)
        return tuple(SendBlock(hit.rule, hit.line) for hit in result.hits)

    return check


def retry_delay_for(policy: RetryPolicy, clock: Clock | None = None, jitter: Jitter = system_jitter) -> RetryDelay:
    """제공자가 대기 시간을 알려 주면 그대로, 아니면 QK-ING-001의 지수 대기와 무작위 지연을 쓴다."""
    used_clock = clock or SystemClock()

    def delay(attempt: int, retry_after_seconds: float | None) -> float:
        if retry_after_seconds is not None:
            return max(0.0, retry_after_seconds)
        return next_delay(policy, attempt, jitter, None, used_clock)

    return delay
