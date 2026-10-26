"""질의 서비스의 서명 재검사. 암호 백엔드는 사용할 때만 가져온다."""

import math
import re


def require_backend() -> None:
    try:
        from cryptography.exceptions import InvalidSignature  # noqa: F401
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey  # noqa: F401
    except ImportError:
        raise RuntimeError("query 선택 의존성의 cryptography를 설치해 주세요") from None


def verify(public_key_hex: str, signature_hex: str, timestamp: str, body: bytes, now: float) -> bool:
    if not all(isinstance(v, str) for v in (public_key_hex, signature_hex, timestamp)):
        return False
    if not re.fullmatch(r"[0-9a-fA-F]{64}", public_key_hex) or not re.fullmatch(r"[0-9a-fA-F]{128}", signature_hex):
        return False
    if not re.fullmatch(r"[0-9]{1,20}", timestamp) or not math.isfinite(now) or abs(now - int(timestamp)) > 300:
        return False
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:
        return False
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(public_key_hex)).verify(
            bytes.fromhex(signature_hex),
            timestamp.encode() + body,
        )
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False
