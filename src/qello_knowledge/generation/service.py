"""`generate` 처리 순서(QK-GEN-001 contracts/generation.md 3절, research R-05·R-06·R-07).

판정 순서: 질문 전송 차단 → 검색 실패 → 결과 없음·빈 Context → 묶음 검사 → 입력 한도 → 호출·기록 → 후처리.
요약·기록·로그·예외 문구에 질문·답변·청크 본문을 넣지 않는다(spec FR-012).
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field, replace

from qello_knowledge.domain.generation import (
    CANNOT_CONFIRM,
    MAX_RETRY_WAIT,
    RETRYABLE,
    AnswerUsageToday,
    CannotConfirmReason,
    Citation,
    DroppedBlock,
    GenerationFailure,
    GenerationFlags,
    GenerationRequest,
    GenerationResult,
    GenerationSettings,
    GenerationStatus,
    GenerationSummary,
    GenerationUsage,
    ProviderReply,
    RenderedInput,
    ResponseShape,
)
from qello_knowledge.domain.retrieval import OmitReason, RetrievalFailure
from qello_knowledge.generation.postprocess import Postprocessed, postprocess
from qello_knowledge.generation.prompts import prompt_spec
from qello_knowledge.generation.render import assemble, neutralize, render_block
from qello_knowledge.generation.settings import within_input_limit
from qello_knowledge.ports.embedder import OutgoingCheck, RetryDelay
from qello_knowledge.ports.generator import GenerationLedger, GenerationProvider, GenerationProviderFailure

logger = logging.getLogger("qello_knowledge.generation")

QUERY_RESERVE_WARNING = "query_reserve_exceeded"
USAGE_RECORD_WARNING = "generation_usage_record_failed"


def _new_run_id() -> str:
    return "answer-" + uuid.uuid4().hex


def default_retry_delay(attempt: int, retry_after_seconds: float | None) -> float:
    """제공자가 알려 준 값을 따르되 질의 경로 상한(2초)을 넘기지 않는다. 모르면 0.5초."""
    return min(0.5 if retry_after_seconds is None else max(0.0, retry_after_seconds), MAX_RETRY_WAIT)


@dataclass(frozen=True)
class GenerationDeps:
    provider: GenerationProvider
    ledger: GenerationLedger
    outgoing_check: OutgoingCheck
    retry_delay: RetryDelay = field(default=default_retry_delay)
    sleep: Callable[[float], None] = field(default=time.sleep)
    monotonic: Callable[[], float] = field(default=time.monotonic)
    new_run_id: Callable[[], str] = field(default=_new_run_id)


@dataclass
class _Run:
    settings: GenerationSettings
    prompt_version: str
    started: float
    retrieval_calls: int
    calls: int = 0
    attempts: int = 0
    neurons: float = 0.0
    measured: bool = True
    input_tokens: int | None = None
    output_tokens: int | None = None
    record_failed: bool = False
    usage_today: AnswerUsageToday | None = None
    shape: ResponseShape | None = None


def _usage_neurons(
    settings: GenerationSettings,
    estimated_input: int,
    *,
    measured: float | None,
    input_tokens: int | None,
    output_tokens: int | None,
    billable: bool,
) -> tuple[float, bool]:
    """research R-06 표: 측정값 → `usage` 토큰 × 단가(추정) → 예상 입력 + 출력 상한(추정) → 과금 안 됨 0."""
    if measured is not None:
        return measured, True
    if not billable:
        return 0.0, False
    if input_tokens is not None and output_tokens is not None:
        return settings.estimated_neurons(input_tokens, output_tokens), False
    return settings.estimated_neurons(estimated_input, settings.max_tokens), False


def generate(
    request: GenerationRequest, deps: GenerationDeps, settings: GenerationSettings | None = None
) -> GenerationResult:
    settings = settings or GenerationSettings()
    prompt = prompt_spec(request.prompt_version or settings.prompt_version)
    retrieval = request.retrieval
    run = _Run(settings, prompt.version, deps.monotonic(), retrieval.summary.external_calls)
    run_id = request.run_id or deps.new_run_id()

    def result(status: GenerationStatus, answer: str = "", citations=(), **extra: object) -> GenerationResult:
        flags = extra.pop("flags", GenerationFlags())
        if run.record_failed:
            flags = replace(flags, usage_record_failed=True)
        summary = GenerationSummary(
            status=status,
            prompt_version=prompt.version,
            model_id=settings.model_id,
            max_tokens=settings.max_tokens,
            temperature=settings.temperature,
            neurons=run.neurons,
            measured=run.measured and run.attempts > 0,
            input_tokens=run.input_tokens,
            output_tokens=run.output_tokens,
            attempts=run.attempts,
            latency_ms=int((deps.monotonic() - run.started) * 1000),
            generation_calls=run.calls,
            total_calls=run.calls + run.retrieval_calls,
            usage_today=run.usage_today,
            response_shape=run.shape,
            flags=flags,
            **extra,  # type: ignore[arg-type]
        )
        return GenerationResult(status, answer, tuple(citations), summary, retrieval.summary)

    def cannot(reason: CannotConfirmReason, **extra: object) -> GenerationResult:
        return result(GenerationStatus.CANNOT_CONFIRM, CANNOT_CONFIRM, cannot_confirm_reason=reason, **extra)

    # 1·2. 질문 전송 차단(research R-05 1·2)
    blocked_by_retrieval = retrieval.status == RetrievalFailure.OUTGOING_BLOCKED.value or any(
        o.reason is OmitReason.OUTGOING_BLOCKED for o in retrieval.summary.omitted
    )
    question, neutralized = neutralize(request.question.strip())
    if blocked_by_retrieval or deps.outgoing_check(question, None):
        return result(GenerationStatus.OUTGOING_BLOCKED)
    # 3. 검색 실패
    if retrieval.failure is not None:
        return result(GenerationStatus.RETRIEVAL_FAILED, retrieval_failure=retrieval.status)
    # 4. 결과 없음·빈 Context
    if retrieval.status == "no_results":
        return cannot(CannotConfirmReason.NO_RESULTS)
    if not retrieval.context:
        return cannot(CannotConfirmReason.EMPTY_CONTEXT)
    # 5. 묶음마다 렌더링하고 따로 검사한다. 걸린 묶음은 어떤 요청에도 싣지 않는다(spec FR-010)
    kept = []
    dropped: list[DroppedBlock] = []
    for block in retrieval.context:
        rendered_block, found = render_block(block, prompt.render_rule, settings)
        rules = deps.outgoing_check(rendered_block.text, None)
        if rules:
            dropped.append(DroppedBlock(block.source_id, tuple(sorted({hit.rule for hit in rules}))))
            continue
        kept.append(rendered_block)
        neutralized += found
    if not kept:
        return cannot(CannotConfirmReason.ALL_BLOCKS_BLOCKED, dropped=tuple(dropped), neutralized=neutralized)
    rendered = assemble(question, kept, prompt, settings, dropped=dropped, neutralized=neutralized)
    sent = {
        "blocks_sent": len(kept),
        "dropped": tuple(dropped),
        "neutralized": neutralized,
        "estimated_input_tokens": rendered.estimated_input_tokens,
    }
    # 6. 호출 직전 입력 한도(spec FR-019 (2))
    if not within_input_limit(rendered.estimated_input_tokens, settings):
        return result(GenerationStatus.GENERATION_FAILED, failure=GenerationFailure.INPUT_TOO_LONG, **sent)

    # 7·8. 시도와 기록
    reply: ProviderReply | None = None
    post: Postprocessed | None = None
    for attempt in (1, 2):
        run.attempts = attempt
        run.calls += 1
        try:
            reply = deps.provider.complete(
                settings.model_id,
                rendered.system,
                rendered.user,
                settings.max_tokens,
                settings.temperature,
                settings.timeout_seconds,
            )
        except GenerationProviderFailure as failure:
            run.shape = failure.shape
            neurons, measured = _usage_neurons(
                settings,
                rendered.estimated_input_tokens,
                measured=failure.neurons,
                input_tokens=failure.input_tokens,
                output_tokens=failure.output_tokens,
                billable=failure.billable,
            )
            _record(deps, run, run_id, attempt, rendered, failure.kind.value, neurons, measured, failure)
            if failure.kind in RETRYABLE and attempt == 1:
                wait = deps.retry_delay(0, failure.retry_after_seconds)
                elapsed = deps.monotonic() - run.started
                if elapsed + wait + settings.timeout_seconds <= settings.deadline:
                    deps.sleep(wait)
                    continue
            return result(GenerationStatus.GENERATION_FAILED, failure=failure.kind, **sent)
        run.shape = reply.shape
        neurons, measured = _usage_neurons(
            settings,
            rendered.estimated_input_tokens,
            measured=reply.neurons,
            input_tokens=reply.input_tokens,
            output_tokens=reply.output_tokens,
            billable=True,
        )
        truncated = _truncated(reply, settings)  # 요약과 기록이 같은 값을 쓴다(spec FR-023, 독립 검토 M3)
        try:
            post = postprocess(reply.text, rendered)
        except Exception:  # noqa: BLE001 - 후처리 오류도 과금된 시도이므로 기록하고 잘못된 응답으로 끝낸다(독립 검토 L1)
            bad = GenerationFailure.BAD_RESPONSE.value
            _record(deps, run, run_id, attempt, rendered, bad, neurons, measured, reply, truncated)
            logger.warning("generation_postprocess_failed")
            return result(GenerationStatus.GENERATION_FAILED, failure=GenerationFailure.BAD_RESPONSE, **sent)
        outcome = GenerationFailure.BAD_RESPONSE.value if post.empty else "ok"
        _record(deps, run, run_id, attempt, rendered, outcome, neurons, measured, reply, truncated)
        break
    assert reply is not None and post is not None  # noqa: S101 - 위 반복은 결과를 돌려주거나 두 값을 채운다

    counts = {
        "removed_citations": post.removed_citations,
        "unrecognized_citations": post.unrecognized_citations,
        "uncited_sentences": post.uncited_sentences,
        "removed_urls": post.removed_urls,
        "removed_source_lines": post.removed_source_lines,
    }
    flags = GenerationFlags(truncated=truncated, thinking_detected=post.thinking_detected)
    if post.empty:
        return result(
            GenerationStatus.GENERATION_FAILED, failure=GenerationFailure.BAD_RESPONSE, flags=flags, **sent, **counts
        )
    if post.cannot_confirm_reason is not None:
        return result(
            GenerationStatus.CANNOT_CONFIRM,
            post.answer,
            cannot_confirm_reason=post.cannot_confirm_reason,
            flags=flags,
            **sent,
            **counts,
        )
    by_id = {b.source_id: b for b in rendered.blocks}
    citations = [
        Citation(
            source_id=sid,
            title=by_id[sid].raw_title,
            source_url=by_id[sid].block.source_url,
            source_version=by_id[sid].block.source_version,
            source_modified_at=by_id[sid].block.source_modified_at,
            collected_at=by_id[sid].block.collected_at,
        )
        for sid in post.citation_ids
    ]
    flags = replace(flags, unsupported_answer=post.unsupported_answer)
    return result(GenerationStatus.ANSWERED, post.answer, citations, flags=flags, **sent, **counts)


def _truncated(reply: ProviderReply, settings: GenerationSettings) -> bool:
    """종료 사유가 `length`이거나, 종료 사유를 모를 때 출력 토큰이 출력 상한 이상이면 잘림이다(spec FR-023)."""
    if reply.finish_reason is not None:
        return reply.finish_reason == "length"
    return reply.output_tokens is not None and reply.output_tokens >= settings.max_tokens


def _record(
    deps: GenerationDeps,
    run: _Run,
    run_id: str,
    attempt: int,
    rendered: RenderedInput,
    outcome: str,
    neurons: float,
    measured: bool,
    source: ProviderReply | GenerationProviderFailure,
    truncated: bool = False,
) -> None:
    """시도 하나를 기록한다. 기록이 실패해도 답은 버리지 않는다(spec FR-020)."""
    run.neurons += neurons
    run.measured = run.measured and measured
    run.input_tokens = source.input_tokens
    run.output_tokens = source.output_tokens
    usage = GenerationUsage(
        run_id=run_id,
        model_id=run.settings.model_id,
        prompt_version=run.prompt_version,
        attempt=attempt,
        input_tokens=source.input_tokens,
        output_tokens=source.output_tokens,
        estimated_input_tokens=rendered.estimated_input_tokens,
        neurons=neurons,
        measured=measured,
        outcome=outcome,
        truncated=truncated,
    )
    run.calls += 1
    try:
        run.usage_today = deps.ledger.record(usage)
    except Exception as error:  # noqa: BLE001 - 저장소 오류 종류와 관계없이 답을 지킨다
        run.record_failed = True
        logger.warning("%s kind=%s", USAGE_RECORD_WARNING, type(error).__name__)
        return
    if run.usage_today.query_reserve_exceeded:
        logger.warning(
            "%s answer_total=%.2f reserve=%d",
            QUERY_RESERVE_WARNING,
            run.usage_today.answer_total,
            run.usage_today.query_reserve,
        )
