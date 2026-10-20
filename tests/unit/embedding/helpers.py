"""임베딩 단위 시험 공통 부품(conftest와 시험 파일이 함께 쓴다).

외부 호출 0건: 가짜 제공자·메모리 저장소·메모리 장부만 쓴다(FR-006).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

from qello_knowledge.domain.embedding import BudgetSettings, EmbedInput, EmbedPurpose, EmbedRequest
from qello_knowledge.embedding.fake import FakeEmbeddingProvider
from qello_knowledge.embedding.service import EmbeddingService
from qello_knowledge.indexer.embedding import security_outgoing_check
from tests.unit.fakes import InMemoryUsageLedger, MemoryEmbeddingStore
from tests.unit.security.helpers import team_policy

MODEL = "@cf/baai/bge-m3"


class StepClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta: float) -> None:
        self.now += timedelta(**delta)


@dataclass
class Harness:
    provider: FakeEmbeddingProvider
    store: MemoryEmbeddingStore
    ledger: InMemoryUsageLedger
    clock: StepClock
    sleeps: list[float] = field(default_factory=list)
    service: EmbeddingService | None = None

    @property
    def embedder(self) -> EmbeddingService:
        assert self.service is not None
        return self.service


def index_request(texts: list[str], *, allow_partial: bool = False, run_id: str = "run-1") -> EmbedRequest:
    inputs = tuple(EmbedInput(text, ("docs", f"docs/{i}.md")) for i, text in enumerate(texts))
    return EmbedRequest(inputs, EmbedPurpose.INDEX, MODEL, run_id, allow_partial)


def query_request(texts: list[str]) -> EmbedRequest:
    return EmbedRequest(tuple(EmbedInput(text) for text in texts), EmbedPurpose.QUERY, MODEL, "q-1")


def build_harness(
    provider: FakeEmbeddingProvider | None = None,
    settings: BudgetSettings | None = None,
    policy=None,
    ledger=None,
    **service_options,
) -> Harness:
    clock = StepClock()
    harness = Harness(
        provider or FakeEmbeddingProvider(),
        MemoryEmbeddingStore(),
        InMemoryUsageLedger(settings or BudgetSettings(), clock),
        clock,
    )
    harness.service = EmbeddingService(
        harness.provider,
        harness.store,  # type: ignore[arg-type]
        ledger or harness.ledger,
        harness.ledger.settings,
        security_outgoing_check(policy or team_policy()),
        sleep=harness.sleeps.append,
        **service_options,
    )
    return harness
