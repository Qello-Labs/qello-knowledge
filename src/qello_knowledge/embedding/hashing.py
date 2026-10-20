"""입력 해시 규칙 `emb-hash-v1`(FR-009, research R-07). 텍스트를 정규화하지 않는다."""

from __future__ import annotations

from hashlib import sha256


def input_hash(text: str) -> str:
    return "sha256:" + sha256(text.encode("utf-8")).hexdigest()
