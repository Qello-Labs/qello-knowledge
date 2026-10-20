"""`Embedder` 구현(contracts/embedder.md).

캐시 → 중복 제거 → 전송 직전 검사 → 미리 보기 → 묶음 → 예약 → 호출 → 정산 → 저장 순서로 처리한다.

`domain`과 `ports`만 가져온다. 전송 직전 검사(QK-SEC-001)와 재시도 대기(QK-ING-001)는 생성 인자로 받는다
(2026-10-20 사용자 결정, TASK.md). 로그에는 항목 번호·규칙 이름·건수만 남기고 텍스트는 남기지 않는다(SC-006).
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from qello_knowledge.domain.embedding import (
    MODELS,
    BudgetSettings,
    DailyUsage,
    EmbedError,
    EmbedErrorKind,
    EmbedFailureKind,
    EmbedItem,
    EmbedPreview,
    EmbedPurpose,
    EmbedRequest,
    EmbedResult,
    ModelSpec,
    ProviderFailureKind,
    Reservation,
    RunSummary,
    UsageOutcome,
)
from qello_knowledge.domain.source_config import RetryPolicy
from qello_knowledge.domain.store import EmbeddingRef
from qello_knowledge.embedding.batching import MAX_ITEMS, MAX_TOKENS, make_batches, split_half
from qello_knowledge.embedding.estimate import estimate_basis, estimated_neurons, estimated_tokens, input_bytes
from qello_knowledge.embedding.hashing import input_hash
from qello_knowledge.ports.embedder import (
    EmbeddingProvider,
    OutgoingCheck,
    ProviderBatch,
    ProviderFailure,
    RetryDelay,
    UsageLedger,
)
from qello_knowledge.ports.store import Store

logger = logging.getLogger("qello_knowledge.embedding")

_FAILURE_OUTCOME = {
    ProviderFailureKind.INPUT_TOO_LONG: UsageOutcome.INPUT_TOO_LONG,
    ProviderFailureKind.TRANSIENT: UsageOutcome.TRANSIENT,
    ProviderFailureKind.PROVIDER_QUOTA: UsageOutcome.PROVIDER_QUOTA,
    ProviderFailureKind.AUTH_CONFIG: UsageOutcome.AUTH_CONFIG,
    ProviderFailureKind.BAD_RESPONSE: UsageOutcome.BAD_RESPONSE,
}

_ITEM_FAILURE = {
    ProviderFailureKind.INPUT_TOO_LONG: EmbedFailureKind.INPUT_TOO_LONG,
    ProviderFailureKind.TRANSIENT: EmbedFailureKind.TRANSIENT,
    ProviderFailureKind.PROVIDER_QUOTA: EmbedFailureKind.PROVIDER_QUOTA,
    ProviderFailureKind.BAD_RESPONSE: EmbedFailureKind.BAD_RESPONSE,
}

QUOTA_MISMATCH_WARNING = "provider_quota_with_index_budget_left"
QUERY_RESERVE_WARNING = "query_reserve_exceeded"
USAGE_UNAVAILABLE_WARNING = "usage_unavailable"


def default_retry_delay(attempt: int, retry_after_seconds: float | None) -> float:
    """조립 코드가 재시도 규칙을 넘기지 않을 때의 기본값: 제공자 대기 시간, 없으면 1·2·4초…(최대 60초)."""
    if retry_after_seconds is not None:
        return max(0.0, retry_after_seconds)
    return float(min(60, 2**attempt))


@dataclass
class _Unique:
    """보낼 텍스트 하나와 그 텍스트를 쓰는 입력 위치들."""

    text: str
    positions: list[int]


@dataclass
class _Plan:
    model: ModelSpec
    items: list[EmbedItem | None]
    uniques: list[_Unique]
    cache_hits: int
    deduplicated: int
    estimated: float = 0.0
    over_limit: int = 0
    today: DailyUsage | None = None
    runnable: bool = True


@dataclass
class _Run:
    calls: int = 0
    neurons: float = 0.0
    estimated: float = 0.0
    warnings: list[str] = field(default_factory=list)
    stop: EmbedFailureKind | None = None


class EmbeddingService:
    """`Embedder` 경계. 제공자·저장소·장부·검사·대기는 모두 주입한다(C-06, FR-006)."""

    def __init__(
        self,
        provider: EmbeddingProvider,
        store: Store,
        ledger: UsageLedger,
        settings: BudgetSettings,
        outgoing_check: OutgoingCheck,
        *,
        retry_policy: RetryPolicy | None = None,
        retry_delay: RetryDelay = default_retry_delay,
        sleep: Callable[[float], None] | None = None,
        max_items: int = MAX_ITEMS,
        max_tokens: int = MAX_TOKENS,
    ) -> None:
        self._provider = provider
        self._store = store
        self._ledger = ledger
        self._settings = settings
        self._check = outgoing_check
        self._retry = retry_policy or RetryPolicy()
        self._retry_delay = retry_delay
        self._sleep = sleep or time.sleep
        self._max_items = max_items
        self._max_tokens = max_tokens

    # ---- 1~5단계: 외부 호출 없는 계획 ------------------------------------------------------------

    def _plan(self, request: EmbedRequest) -> _Plan:
        model = MODELS.get(request.model_version)
        if model is None:
            raise EmbedError(EmbedErrorKind.AUTH_CONFIG, "지원하지 않는 모델 버전")
        indexing = request.purpose is EmbedPurpose.INDEX
        items: list[EmbedItem | None] = [None] * len(request.inputs)

        pending: list[int] = []
        for position, piece in enumerate(request.inputs):
            if not piece.text.strip():
                items[position] = EmbedItem(position, failure=EmbedFailureKind.EMPTY_INPUT)
            elif indexing and piece.origin is None:
                items[position] = EmbedItem(position, failure=EmbedFailureKind.NO_ORIGIN)
            else:
                pending.append(position)

        cache_hits = 0
        if indexing and pending:
            refs = {position: self._ref(request.inputs[position].text, model) for position in pending}
            found = self._store.find_embeddings(list(dict.fromkeys(refs.values())))
            still: list[int] = []
            for position in pending:
                vector = found.get(refs[position])
                if vector is None:
                    still.append(position)
                else:
                    items[position] = EmbedItem(position, vector=tuple(vector), cached=True)
                    cache_hits += 1
            pending = still

        allowed: list[int] = []
        for position in pending:
            piece = request.inputs[position]
            blocks = self._check(piece.text, piece.origin)
            if blocks:
                for block in blocks:
                    logger.info("embed_secret_blocked item=%s rule=%s line=%s", position, block.rule, block.line)
                items[position] = EmbedItem(position, failure=EmbedFailureKind.SECRET_BLOCKED)
            else:
                allowed.append(position)

        by_text: dict[str, _Unique] = {}
        for position in allowed:
            text = request.inputs[position].text
            if text in by_text:
                by_text[text].positions.append(position)
            else:
                by_text[text] = _Unique(text, [position])
        uniques = list(by_text.values())
        plan = _Plan(model, items, uniques, cache_hits, len(allowed) - len(uniques))

        texts = [unique.text for unique in uniques]
        plan.estimated = estimated_neurons(texts, model)
        plan.over_limit = sum(1 for text in texts if estimated_tokens(text, model) > model.max_input_tokens)
        if indexing:
            plan.today = self._today()
            plan.runnable = plan.estimated <= plan.today.index_remaining
        return plan

    def preview(self, request: EmbedRequest) -> EmbedPreview:
        plan = self._plan(request)
        today = plan.today or self._today()
        return EmbedPreview(
            requested=len(request.inputs),
            cache_hits=plan.cache_hits,
            deduplicated=plan.deduplicated,
            to_embed=len(plan.uniques),
            over_limit_expected=plan.over_limit,
            estimated_neurons=plan.estimated,
            basis=estimate_basis([unique.text for unique in plan.uniques], plan.model),
            index_budget=self._settings.index_budget,
            index_used_today=today.index_used,
            index_remaining=today.index_remaining,
            runnable=plan.runnable,
        )

    # ---- 6~8단계: 호출 ---------------------------------------------------------------------------

    def embed(self, request: EmbedRequest) -> EmbedResult:
        plan = self._plan(request)
        run = _Run()
        if not plan.runnable and not request.allow_partial:
            logger.info("embed_over_budget estimated=%.2f", plan.estimated)
            run.stop = EmbedFailureKind.INDEX_BUDGET
        tokens = [estimated_tokens(unique.text, plan.model) for unique in plan.uniques]
        queue = list(make_batches(tokens, plan.model.max_input_tokens, self._max_items, self._max_tokens))
        while queue:
            batch = queue.pop(0)
            if run.stop is not None:
                self._fail(plan, batch, run.stop)
                continue
            retry = self._send(request, plan, batch, run)
            if retry:
                queue[:0] = list(retry)

        items = tuple(item for item in plan.items if item is not None)
        assert len(items) == len(request.inputs)  # noqa: S101 - 모든 위치를 채웠는지 내부 불변식
        failures: dict[str, int] = {}
        for item in items:
            if item.failure is not None:
                failures[item.failure.value] = failures.get(item.failure.value, 0) + 1
        summary = RunSummary(
            requested=len(request.inputs),
            cache_hits=plan.cache_hits,
            deduplicated=plan.deduplicated,
            provider_calls=run.calls,
            failures=failures,
            neurons=run.neurons,
            estimated_neurons=run.estimated,
            warnings=tuple(dict.fromkeys(run.warnings)),
        )
        return EmbedResult(items, plan.model.model_version, plan.model.dimension, summary)

    def _send(
        self, request: EmbedRequest, plan: _Plan, batch: tuple[int, ...], run: _Run
    ) -> tuple[tuple[int, ...], ...] | None:
        """요청 하나를 보낸다. 입력 한도 초과로 쪼개야 하면 나눈 묶음을 돌려준다."""
        indexing = request.purpose is EmbedPurpose.INDEX
        texts = [plan.uniques[i].text for i in batch]
        estimated = estimated_neurons(texts, plan.model)
        size = input_bytes(texts)
        attempt = 0
        while True:
            reservation: Reservation | None = None
            if indexing:
                try:
                    reservation = self._ledger.reserve(
                        request.run_id, plan.model.model_version, len(texts), size, estimated
                    )
                except Exception:
                    self._usage_failed(run, indexing)
                    self._fail(plan, batch, EmbedFailureKind.USAGE_UNAVAILABLE)
                    return None
                if reservation is None:
                    run.stop = EmbedFailureKind.INDEX_BUDGET
                    self._fail(plan, batch, run.stop)
                    return None
            run.calls += 1
            run.estimated += estimated
            try:
                result = self._provider.embed_texts(plan.model, texts)
            except ProviderFailure as failure:
                self._account(request, plan, run, reservation, texts, size, estimated, 0.0, False, failure.kind)
                if failure.kind is ProviderFailureKind.AUTH_CONFIG:
                    raise EmbedError(EmbedErrorKind.AUTH_CONFIG, "제공자 인증·설정 오류") from None
                if failure.kind is ProviderFailureKind.TRANSIENT and attempt < self._retry.max_retries:
                    if run.stop is not None:  # 사용량 기록이 실패했으면 다시 보내지 않는다
                        self._fail(plan, batch, EmbedFailureKind.TRANSIENT)
                        return None
                    self._sleep(self._retry_delay(attempt, failure.retry_after_seconds))
                    attempt += 1
                    continue
                if failure.kind is ProviderFailureKind.INPUT_TOO_LONG and len(batch) > 1:
                    return split_half(batch)
                if failure.kind is ProviderFailureKind.PROVIDER_QUOTA:
                    run.stop = EmbedFailureKind.PROVIDER_QUOTA
                    if indexing and self._budget_left():
                        run.warnings.append(QUOTA_MISMATCH_WARNING)
                self._fail(plan, batch, _ITEM_FAILURE[failure.kind])
                return None
            except Exception:
                # 경계 밖 예외: 호출이 나갔을 수 있으므로 예상량으로 정산하고 그대로 올린다(예약을 남기지 않는다).
                self._account(
                    request, plan, run, reservation, texts, size, estimated, estimated, False,
                    ProviderFailureKind.TRANSIENT,
                )  # fmt: skip
                raise
            self._accept(request, plan, run, reservation, batch, texts, size, estimated, result)
            return None

    def _accept(
        self,
        request: EmbedRequest,
        plan: _Plan,
        run: _Run,
        reservation: Reservation | None,
        batch: tuple[int, ...],
        texts: Sequence[str],
        size: int,
        estimated: float,
        result: ProviderBatch,
    ) -> None:
        """결과를 먼저 저장하고 정산한다. 정산이 실패해도 이미 비용을 낸 결과는 돌려준다(spec Edge Cases)."""
        measured = result.neurons is not None
        neurons = result.neurons if result.neurons is not None else estimated
        valid = len(result.vectors) == len(texts) and all(len(v) == plan.model.dimension for v in result.vectors)
        if not valid:
            logger.info("embed_bad_response items=%s", len(batch))
            self._fail(plan, batch, EmbedFailureKind.BAD_RESPONSE)
        else:
            for unique_index, vector in zip(batch, result.vectors, strict=True):
                unique = plan.uniques[unique_index]
                if request.purpose is EmbedPurpose.INDEX:
                    self._store.put_embedding(self._ref(unique.text, plan.model), vector)
                for position in unique.positions:
                    plan.items[position] = EmbedItem(position, vector=tuple(vector))
        kind = None if valid else ProviderFailureKind.BAD_RESPONSE
        self._account(request, plan, run, reservation, texts, size, estimated, neurons, measured, kind)

    def _account(
        self,
        request: EmbedRequest,
        plan: _Plan,
        run: _Run,
        reservation: Reservation | None,
        texts: Sequence[str],
        size: int,
        estimated: float,
        neurons: float,
        measured: bool,
        failure: ProviderFailureKind | None,
    ) -> None:
        """사용량을 기록한다. 기록이 실패하면 경고를 남기고, 색인용이면 다음 외부 호출을 멈춘다."""
        outcome = UsageOutcome.OK if failure is None else _FAILURE_OUTCOME[failure]
        run.neurons += neurons
        try:
            if reservation is not None:
                self._ledger.settle(reservation, neurons, measured, outcome)
                return
            usage = self._ledger.record(
                request.run_id, plan.model.model_version, len(texts), size, estimated, neurons, measured, outcome
            )
        except Exception:
            self._usage_failed(run, request.purpose is EmbedPurpose.INDEX)
            return
        if usage.query_reserve_exceeded:
            run.warnings.append(QUERY_RESERVE_WARNING)

    @staticmethod
    def _usage_failed(run: _Run, indexing: bool) -> None:
        logger.warning("embed_usage_unavailable")
        run.warnings.append(USAGE_UNAVAILABLE_WARNING)
        if indexing:
            run.stop = EmbedFailureKind.USAGE_UNAVAILABLE

    def _budget_left(self) -> bool:
        try:
            return self._ledger.today().index_remaining > 0
        except Exception:
            return False

    # ---- 도우미 ----------------------------------------------------------------------------------

    @staticmethod
    def _ref(text: str, model: ModelSpec) -> EmbeddingRef:
        return EmbeddingRef(input_hash(text), model.model_version)

    @staticmethod
    def _fail(plan: _Plan, batch: tuple[int, ...], kind: EmbedFailureKind) -> None:
        for unique_index in batch:
            for position in plan.uniques[unique_index].positions:
                plan.items[position] = EmbedItem(position, failure=kind)

    def _today(self) -> DailyUsage:
        return self._guard(self._ledger.today)

    @staticmethod
    def _guard[T](call: Callable[[], T]) -> T:
        """장부 오류는 다음 외부 호출 전에 멈춘다(spec Edge Cases). 원인 문구는 옮기지 않는다."""
        try:
            return call()
        except EmbedError:
            raise
        except Exception as exc:
            raise EmbedError(EmbedErrorKind.USAGE_UNAVAILABLE, "사용량 장부를 쓸 수 없다") from exc
