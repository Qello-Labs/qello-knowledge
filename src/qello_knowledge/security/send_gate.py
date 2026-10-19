"""임베딩·생성 API로 보내기 직전 검사(FR-013). 실제 호출에 잇는 일은 QK-EMB-001·QK-GEN-001이 한다."""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field

from qello_knowledge.domain.secret_rules import find_secrets
from qello_knowledge.security.exceptions import normalize_path
from qello_knowledge.security.policy import SecurityPolicy

logger = logging.getLogger("qello_knowledge.security")


@dataclass(frozen=True)
class OutgoingPiece:
    """보낼 텍스트 조각. `origin`은 (자료원 이름, 경로) 또는 출처 없음(질의·프롬프트 문구)."""

    text: str = field(repr=False)
    origin: tuple[str, str] | None = None


@dataclass(frozen=True)
class SendHit:
    piece_index: int
    rule: str
    line: int


@dataclass(frozen=True)
class SendCheck:
    allowed: bool
    hits: tuple[SendHit, ...] = ()


def check_outgoing(pieces: Sequence[OutgoingPiece], policy: SecurityPolicy) -> SendCheck:
    """하나라도 걸리면 `allowed=False`. 호출자는 그 요청 전체를 보내지 않는다."""
    hits = []
    for index, piece in enumerate(pieces):
        skip = frozenset()
        if piece.origin is not None:
            source, path = piece.origin
            skip = policy.exempt_rules(source, normalize_path(path))
        hits += [SendHit(index, hit.rule, hit.line) for hit in find_secrets(piece.text, skip)]
    for hit in hits:
        logger.info("send_blocked piece=%s rule=%s line=%s", hit.piece_index, hit.rule, hit.line)
    return SendCheck(not hits, tuple(hits))
