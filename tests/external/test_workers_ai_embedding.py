"""실제 Workers AI bge-m3 실측(SC-005, quickstart 4절). 기본 검증에서 돌리지 않는다(`-m external`).

실행 전 예상 사용량: 합성 텍스트 20개(한국어 10, 영어·코드 10), UTF-8 21,620바이트
→ 예상 6.65 Neurons(하루 무료 10,000 대비 0.07%).
사람 승인 뒤 한 번만 돌린다(AGENTS.md 3.5, tasks.md T046). 결과는 PR 본문이나 `docs/sdd/research/`에 남긴다.
필요한 설정: `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`. 값은 출력하지 않는다.
"""

from __future__ import annotations

import pytest

from qello_knowledge.adapters.workers_ai.rest import WorkersAiRestProvider
from qello_knowledge.config.loader import SecretValue
from qello_knowledge.domain.embedding import MODELS
from qello_knowledge.embedding.estimate import estimated_neurons, input_bytes

pytestmark = pytest.mark.external

MODEL = MODELS["@cf/baai/bge-m3"]
KOREAN = [
    f"{i}번 문서: 색인 파이프라인은 저장소 문서를 읽어 청크로 나누고, 바뀐 청크만 임베딩한다. "
    "임베딩 결과는 입력 해시와 모델 버전으로 저장해 다음 실행에서 다시 쓴다. " * 6
    for i in range(10)
]
ENGLISH_CODE = [
    f"# Note {i}\nThe indexer reads repository files, splits them into chunks and embeds only changed chunks.\n"
    "```python\ndef input_hash(text: str) -> str:\n    return 'sha256:' + sha256(text.encode()).hexdigest()\n```\n" * 4
    for i in range(10)
]
TEXTS = KOREAN + ENGLISH_CODE
MAX_EXPECTED_NEURONS = 10


def test_bge_m3_dimension_order_and_estimate_gap(require_env) -> None:
    expected = estimated_neurons(TEXTS, MODEL)
    assert expected < MAX_EXPECTED_NEURONS, "예상 사용량이 승인 범위를 넘는다"
    provider = WorkersAiRestProvider(
        require_env("CLOUDFLARE_ACCOUNT_ID"), SecretValue(require_env("CLOUDFLARE_API_TOKEN"))
    )
    measured = 0.0
    vectors = []
    for start in range(0, len(TEXTS), 10):
        batch = provider.embed_texts(MODEL, TEXTS[start : start + 10])
        assert batch.neurons is not None, "cf-ai-neurons 헤더가 없다"
        measured += batch.neurons
        vectors += batch.vectors
    assert len(vectors) == len(TEXTS) and {len(v) for v in vectors} == {MODEL.dimension}
    gap = (expected - measured) / measured * 100
    print(
        f"texts={len(TEXTS)} korean=10 english_code=10 bytes={input_bytes(TEXTS)} "
        f"expected={expected:.2f} measured={measured:.2f} gap={gap:+.1f}% model={MODEL.model_version}"
    )
