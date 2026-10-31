"""평가 대상과 운영 사용 장부 경계(QK-EVL-001 data-model 2절, research R-04·R-05·R-07).

평가 대상은 로컬 평가용 데이터베이스 하나다. 실행 전에 한 번 읽은 설명과 문서 표를 실행 내내 고정한다.
장부는 읽기만 한다. 쓰기 메서드를 두지 않는다.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from qello_knowledge.domain.generation import AnswerUsageToday
from qello_knowledge.ports.retrieval import RetrievalStore


class TargetUnavailable(Exception):  # noqa: N818 - 저장소 상태 이름
    """평가 대상에 연결하거나 읽을 수 없다. 문구에 접속 정보가 없다."""


class LedgerUnavailable(Exception):  # noqa: N818 - 저장소 상태 이름
    """운영 사용 장부를 읽을 수 없다. 문구에 접속 정보가 없다."""


@dataclass(frozen=True)
class TargetDescription:
    database: str
    index_version: str | None  # 활성 인덱스 버전이 없으면 None
    embedding_model: str | None
    dimension: int | None
    index_rule: str  # domain/keyword_rules.index_rule_for
    tokenizer: str | None  # qk.chunk_search_text_pgroonga의 tokenizer. 읽지 못하면 None
    commits: Mapping[str, str] = field(default_factory=dict)  # 자료원 이름 → 원본 리비전
    synced_at: datetime | None = None  # 그 동기화 실행의 finished_at
    sources: tuple[str, ...] = ()  # qk.sync_source 자료원 이름
    unlocated_documents: int = 0  # 노출 청크가 있는데 source_name·location이 비어 문서 표에 넣지 못한 자료 수


@dataclass(frozen=True)
class TargetDocument:
    source: str  # qk.artifact.source_name
    location: str  # qk.artifact.location
    source_url: str


class EvalTarget(Protocol):
    store: RetrievalStore

    def describe(self) -> TargetDescription: ...

    def documents(self) -> tuple[TargetDocument, ...]:
        """활성 인덱스 버전에서 노출 청크가 하나 이상인 문서(research R-04)."""
        ...


class DayUsageReader(Protocol):
    def today(self) -> AnswerUsageToday:
        """당일(UTC) 생성·질의 임베딩·색인 임베딩 사용량. 실패는 `LedgerUnavailable`."""
        ...


__all__ = [
    "DayUsageReader",
    "EvalTarget",
    "LedgerUnavailable",
    "TargetDescription",
    "TargetDocument",
    "TargetUnavailable",
]
