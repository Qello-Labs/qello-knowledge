"""합성 입력 성능 회귀 감시. SC-011의 실제 문서 완료 판정(H01)을 대신하지 않는다."""

import hashlib
import random
import time

from qello_knowledge.chunking import chunk_screened
from qello_knowledge.domain.chunking import ChunkingSettings
from tests.unit.chunking.helpers import screened


def documents():
    rng = random.Random(20261021)  # noqa: S311 - 재현 가능한 합성 데이터용이다
    docs = []
    words = ("합성", "문서", "검색", "knowledge", "chunk", "example", "표", "원문")
    for doc in range(79):
        parts = []
        for section in range(13):
            parts.append(("#" if section == 0 else "##" if section % 3 else "###") + f" 문서 {doc} 절 {section}")
            for _ in range(rng.randint(2, 4)):
                parts.append(" ".join(rng.choice(words) for _ in range(30)))
            rows = ["| a | b | c | d |", "| --- | --- | --- | --- |"]
            rows += [f"| {n} | 합성 | row | {rng.randrange(1000)} |" for n in range(rng.randint(6, 12))]
            parts.append("\n".join(rows))
            parts.append(
                "```python\n"
                + "\n".join(f"value_{n} = {rng.randrange(1000)}" for n in range(rng.randint(10, 40)))
                + "\n```"
            )
            parts.append("\n".join(f"- 합성 item {rng.randrange(1000)}" for _ in range(rng.randint(3, 8))))
        docs.append("\n\n".join(parts))
    return docs


def test_synthetic_performance():
    bodies = documents()
    payload = "".join(bodies).encode()
    assert len(payload) == TOTAL_BYTES
    assert hashlib.sha256(payload).hexdigest() == INPUT_SHA256
    inputs = [screened(body, location=f"docs/{i}.md") for i, body in enumerate(bodies)]
    start = time.perf_counter()
    result = chunk_screened(inputs, ChunkingSettings())
    elapsed = time.perf_counter() - start
    assert result.summary.by_outcome == {"CHUNKED": 79}
    assert result.summary.chunk_count > 0
    assert elapsed <= 10


TOTAL_BYTES = 1447811
INPUT_SHA256 = "4bebfaa6fdc9a802f3b572c2103ffd61caae30a9fedee2ba75870feef9ee2751"
