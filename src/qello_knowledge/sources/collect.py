"""페이지 순회·범위 적용과 자료별 실패 격리는 자료원과 독립적으로 수행한다."""

import logging
from collections.abc import Iterable

from qello_knowledge.domain.scope import in_scope
from qello_knowledge.domain.source import (
    FailureType,
    FetchResult,
    ItemOutcome,
    ItemStatus,
    Listing,
    RunStopped,
    SourceFailure,
    SourceItem,
    StopReason,
)
from qello_knowledge.domain.source_config import SourceConfig
from qello_knowledge.ports.source import SourceAdapter, SourceSession
from qello_knowledge.sources.session import DefaultSourceSession

logger = logging.getLogger(__name__)
TRANSIENT_FAILURES = frozenset(
    {FailureType.RATE_LIMITED, FailureType.SERVER_ERROR, FailureType.TIMEOUT, FailureType.CONNECTION}
)


def list_all(adapter: SourceAdapter, config: SourceConfig, session: SourceSession) -> Listing:
    items = []
    seen = set()
    duplicates = excluded = 0
    cursor = None
    origin = None
    first = True
    while True:
        try:
            page = adapter.list_page(session, config, cursor)
        except RunStopped as stopped:
            return Listing(tuple(items), duplicates, False, excluded, stopped.stop, origin)
        except SourceFailure:
            return Listing(tuple(items), duplicates, False, excluded, origin=origin)
        if first:
            origin = page.origin
            first = False
        for item in page.items:
            if item.source_id in seen:
                duplicates += 1
                continue
            seen.add(item.source_id)
            if not in_scope(item.location, config.scope.include, config.scope.exclude):
                excluded += 1
                continue
            items.append(item)
        if not page.complete:
            return Listing(tuple(items), duplicates, False, excluded, origin=origin)
        cursor = page.next_cursor
        if cursor is None:
            return Listing(tuple(items), duplicates, True, excluded, origin=origin)


def fetch_contents(
    adapter: SourceAdapter, config: SourceConfig, session: DefaultSourceSession, items: Listing | Iterable[SourceItem]
) -> FetchResult:
    listing = items if isinstance(items, Listing) else Listing(tuple(items))
    outcomes = []
    contents = []
    stop = listing.stop or session.stop
    for item in listing.items:
        before_retries = session.retries_made
        before_requests = session.requests_made
        if stop is not None:
            outcome = ItemOutcome(item.source_id, ItemStatus.SKIPPED)
        elif item.size_bytes is not None and item.size_bytes > config.max_content_bytes:
            outcome = ItemOutcome(item.source_id, ItemStatus.PERMANENT_FAILED, failure=FailureType.SIZE_EXCEEDED)
        else:
            try:
                content = adapter.fetch_content(session, config, item)
                contents.append(session.finalize_content(content))
                outcome = ItemOutcome(
                    item.source_id,
                    ItemStatus.SUCCEEDED,
                    session.retries_made - before_retries,
                    http_status=session.last_http_status if session.requests_made > before_requests else None,
                )
            except SourceFailure as failed:
                status = (
                    ItemStatus.TRANSIENT_EXHAUSTED
                    if failed.failure in TRANSIENT_FAILURES
                    else ItemStatus.PERMANENT_FAILED
                )
                outcome = ItemOutcome(
                    item.source_id,
                    status,
                    session.retries_made - before_retries,
                    failed.failure,
                    failed.http_status
                    if failed.http_status is not None
                    else (session.last_http_status if session.requests_made > before_requests else None),
                )
            except RunStopped as stopped:
                stop = stopped.stop
                outcome = ItemOutcome(
                    item.source_id,
                    ItemStatus.SKIPPED,
                    session.retries_made - before_retries,
                    FailureType.AUTH_FAILED if stop.reason == StopReason.AUTH_FAILED else None,
                    session.last_http_status if session.requests_made > before_requests else None,
                )
        outcomes.append(outcome)
        logger.info(
            "source_name=%s source_id=%s status=%s retries=%s failure=%s http_status=%s",
            config.name,
            outcome.source_id,
            outcome.status,
            outcome.retries,
            outcome.failure,
            outcome.http_status,
        )
    return FetchResult(
        config.name,
        session.started_at,
        session.clock.now(),
        session.requests_made,
        listing.complete,
        sum(o.status == ItemStatus.SUCCEEDED for o in outcomes),
        sum(o.status in {ItemStatus.TRANSIENT_EXHAUSTED, ItemStatus.PERMANENT_FAILED} for o in outcomes),
        sum(o.status == ItemStatus.SKIPPED for o in outcomes),
        stop,
        tuple(outcomes),
        tuple(contents),
    )
