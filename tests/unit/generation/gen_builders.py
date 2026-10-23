"""생성 단위 시험용 합성 Context·결과 도우미(QK-GEN-001). 모든 글은 합성이다."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime

from qello_knowledge.domain.embedding import SendBlock
from qello_knowledge.domain.generation import GenerationRequest
from qello_knowledge.domain.retrieval import (
    ChunkRole,
    ContextBlock,
    ContextChunk,
    Omitted,
    RetrievalResult,
    RetrievalSummary,
)
from qello_knowledge.generation.fake import MemoryLedger, ScriptedProvider
from qello_knowledge.generation.service import GenerationDeps

COLLECTED = datetime(2026, 10, 21, 3, 0, tzinfo=UTC)
MODIFIED = datetime(2026, 10, 9, 16, 0, tzinfo=UTC)  # 한국 시간 2026-10-10


def chunk(
    artifact_id: int,
    ordinal: int,
    body: str,
    heading: Sequence[str] = ("A", "B"),
    *,
    path: str | None = None,
    chunk_id: int | None = None,
) -> ContextChunk:
    locator = {"path": path} if path else {}
    return ContextChunk(
        chunk_id=chunk_id if chunk_id is not None else artifact_id * 100 + ordinal,
        artifact_id=artifact_id,
        ordinal=ordinal,
        role=ChunkRole.CENTER,
        heading_path=tuple(heading),
        locator=locator,
        body=body,
        estimated_tokens=max(1, len(body.encode()) // 4),
    )


def block(
    source_id: str,
    chunks: Sequence[ContextChunk],
    *,
    modified: datetime | None = MODIFIED,
    url: str | None = None,
    rank: int | None = None,
) -> ContextBlock:
    artifact_id = chunks[0].artifact_id
    ordinals = [c.ordinal for c in chunks]
    gaps = tuple((a, b) for a, b in zip(ordinals, ordinals[1:], strict=False) if b != a + 1)
    return ContextBlock(
        source_id=source_id,
        rank=rank if rank is not None else int(source_id[1:]),
        artifact_id=artifact_id,
        source_url=url or f"https://github.example.test/o/r/blob/main/docs/doc{artifact_id}.md",
        source_version=f"sha{artifact_id}",
        source_modified_at=modified,
        collected_at=COLLECTED,
        chunks=tuple(chunks),
        centers=((chunks[0].chunk_id, 1),),
        gaps=gaps,
    )


def three_blocks() -> tuple[ContextBlock, ...]:
    return (
        block("S1", [chunk(1, 0, "배포는 승인 뒤에 한다.")]),
        block("S2", [chunk(2, 3, "재시도는 3회다.", ("결제", "재시도"))]),
        block("S3", [chunk(3, 1, "알림은 FCM으로 보낸다.", ("알림",))], modified=None),
    )


def retrieval(
    context: Sequence[ContextBlock] = (),
    *,
    status: str = "ok",
    omitted: Sequence[Omitted] = (),
    external_calls: int = 5,
) -> RetrievalResult:
    return RetrievalResult(
        status=status,
        context=tuple(context),
        summary=RetrievalSummary(omitted=tuple(omitted), external_calls=external_calls),
    )


def request(
    question: str = "배포 절차가 뭐야?", context: Sequence[ContextBlock] | None = None, **kwargs
) -> GenerationRequest:
    result = kwargs.pop("result", None) or retrieval(three_blocks() if context is None else context)
    return GenerationRequest(question, result, **kwargs)


class Clock:
    def __init__(self) -> None:
        self.now = 100.0
        self.slept: list[float] = []

    def monotonic(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def never_blocks(text: str, origin) -> tuple[SendBlock, ...]:
    return ()


def deps(
    provider: ScriptedProvider | None = None,
    ledger: MemoryLedger | None = None,
    check=never_blocks,
    clock: Clock | None = None,
) -> GenerationDeps:
    clock = clock or Clock()
    return GenerationDeps(
        provider=provider or ScriptedProvider(),
        ledger=ledger or MemoryLedger(),
        outgoing_check=check,
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        new_run_id=lambda: "answer-test",
    )
