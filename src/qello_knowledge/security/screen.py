"""목록 단계와 본문 단계 판정. 목록 단계에서 빠진 자료는 본문을 추가로 조회하지 않는다(FR-002)."""

from __future__ import annotations

import logging
from collections.abc import Iterable, Mapping
from dataclasses import replace
from pathlib import PurePosixPath

from qello_knowledge.domain.exclusions import excluded_by, normalize_location
from qello_knowledge.domain.redact import FieldKind, has_unsafe
from qello_knowledge.domain.secret_rules import find_secrets
from qello_knowledge.domain.security import (
    AccessScope,
    FilterSummary,
    ScreenedContent,
    ScreenResult,
    SecurityVerdict,
    Stage,
    Verdict,
)
from qello_knowledge.domain.source import AccessStatus, ItemStatus, SourceContent, SourceItem
from qello_knowledge.domain.source_config import SourceConfig
from qello_knowledge.ports.source import SourceAdapter
from qello_knowledge.security.exceptions import normalize_path
from qello_knowledge.security.policy import SecurityPolicy
from qello_knowledge.sources.collect import fetch_contents, list_all
from qello_knowledge.sources.session import DefaultSourceSession

logger = logging.getLogger("qello_knowledge.security")


def _verdict(item: SourceItem, policy: SecurityPolicy, verdict: Verdict, stage: Stage, **fields) -> SecurityVerdict:
    return SecurityVerdict(
        item.source_name,
        item.source_id,
        item.location,
        item.url,
        item.title,
        verdict,
        stage,
        policy.version,
        **fields,
    )


def _item_secret(item: SourceItem, config: SourceConfig, policy: SecurityPolicy) -> tuple[str, str] | None:
    # source_id는 ING-001 로그와 FetchResult.to_dict()에 그대로 남으므로 오탐 예외를 적용하지 않는다.
    context = policy.output_context(item.source_kind)
    id_kind = FieldKind.PATH if context.source_id_is_path else FieldKind.TEXT
    unsafe = has_unsafe(item.source_id, id_kind, context)
    if unsafe is not None:
        return "source_id", "identifier-address" if unsafe == "address" else unsafe
    skip = policy.exempt_rules(config.name, normalize_path(item.location))
    for field, value in (("location", item.location), ("title", item.title), ("url", item.url)):
        if value is not None and (hits := find_secrets(value, skip)):
            return field, hits[0].rule
    return None


def _evidence(item: SourceItem) -> dict:
    """접근 판정을 통과한 뒤의 판정에 남기는 권한 증빙(FR-019)."""
    return {"access_scope": AccessScope.TEAM, "access_raw": item.access.raw}


def _source_excluded(location: str, config: SourceConfig) -> bool:
    return source_excluded(location, config)


def source_excluded(location: str, config: SourceConfig) -> bool:
    """ING-001 `list_all`이 거른 자료원 제외 패턴을 대소문자 무시로 다시 확인한다(방어선)."""
    path = PurePosixPath(normalize_location(location))
    return any(path.full_match(pattern, case_sensitive=False) for pattern in config.scope.exclude)


def _path_stage(item: SourceItem, config: SourceConfig, policy: SecurityPolicy) -> SecurityVerdict | None:
    if item.exclusion is not None:
        # 어댑터가 ID 기준으로 정한 제외(QK-ING-003 research R-07). 본문을 받지 않는다.
        return _verdict(item, policy, Verdict.PATH_EXCLUDED, Stage.PATH, rule="source-exclude:" + item.exclusion)
    category = excluded_by(item.location, policy.exclusions)
    if category is None and _source_excluded(item.location, config):
        category = "source-exclude"
    if category is not None:
        return _verdict(item, policy, Verdict.PATH_EXCLUDED, Stage.PATH, rule=category)
    return None


def _access_stage(item: SourceItem, config: SourceConfig, policy: SecurityPolicy) -> SecurityVerdict | None:
    spec = policy.kinds.get(item.source_kind)
    scope = spec.judge(item.access) if spec is not None else AccessScope.UNKNOWN
    if item.access.status == AccessStatus.UNKNOWN:
        scope = AccessScope.UNKNOWN
    if scope != AccessScope.TEAM:
        return _verdict(
            item,
            policy,
            Verdict.ACCESS_HELD,
            Stage.ACCESS,
            rule=_access_rule(item, policy),
            access_scope=scope,
            access_raw=item.access.raw,
        )
    return None


def _item_secret_stage(item: SourceItem, config: SourceConfig, policy: SecurityPolicy) -> SecurityVerdict | None:
    found = _item_secret(item, config, policy)
    if found is not None:
        field, rule = found
        return _verdict(
            item, policy, Verdict.SECRET_BLOCKED, Stage.ITEM_SECRET, rule=rule, field=field, **_evidence(item)
        )
    return None


# 목록 단계 순서(contracts/security-filter.md 표 1~5번). 세 번째 값은 그 단계 오류에 권한 증빙을 남기는지다.
ITEM_STAGES = (
    (Stage.PATH, _path_stage, False),
    (Stage.ACCESS, _access_stage, False),
    (Stage.ITEM_SECRET, _item_secret_stage, True),
)


def _error(item: SourceItem, policy: SecurityPolicy, stage: Stage, error_type: str, **fields) -> SecurityVerdict:
    return _verdict(item, policy, Verdict.ERROR, stage, error_type=error_type, **fields)


def screen_items(
    items: Iterable[SourceItem], config: SourceConfig, policy: SecurityPolicy
) -> tuple[tuple[SourceItem, ...], tuple[SecurityVerdict, ...]]:
    passed, verdicts = [], []
    for item in items:
        verdict = None
        for stage, judge, after_access in ITEM_STAGES:
            try:
                verdict = judge(item, config, policy)
            except Exception as error:  # 판정 실패는 막는 쪽으로(FR-004). 메시지는 남기지 않는다.
                evidence = _evidence(item) if after_access else {}
                verdict = _error(item, policy, stage, type(error).__name__, **evidence)
            if verdict is not None:
                break
        if verdict is None:
            passed.append(item)
        else:
            verdicts.append(verdict)
    return tuple(passed), tuple(verdicts)


def _screen_content(
    content: SourceContent, item: SourceItem, config: SourceConfig, policy: SecurityPolicy
) -> SecurityVerdict | ScreenedContent:
    skip = policy.exempt_rules(config.name, normalize_path(item.location))
    for field, value in (("body", content.body), ("title", content.title), ("location", content.location)):
        if value is None:
            continue
        hits = find_secrets(value, skip)
        if hits:
            lines = tuple(sorted({hit.line for hit in hits})) if field == "body" else ()
            return _verdict(
                item,
                policy,
                Verdict.SECRET_BLOCKED,
                Stage.CONTENT_SECRET,
                rule=hits[0].rule,
                field=field,
                lines=lines,
                **_evidence(item),
            )
    return ScreenedContent(item, content, AccessScope.TEAM, policy.version)


def screen_contents(
    contents: Iterable[SourceContent],
    items_by_id: Mapping[str, SourceItem],
    config: SourceConfig,
    policy: SecurityPolicy,
) -> tuple[tuple[ScreenedContent, ...], tuple[SecurityVerdict, ...]]:
    passed, verdicts = [], []
    seen = set()
    for content in contents:
        item = items_by_id.get(content.source_id)
        if item is None or content.source_id in seen:
            # 어댑터가 목록에 없는 식별자로 본문을 돌려줬다. 그 본문은 쓰지 않는다(FR-004).
            logger.warning("orphan_content dropped")
            continue
        seen.add(content.source_id)
        try:
            outcome = _screen_content(content, item, config, policy)
        except Exception as error:  # 판정 실패는 막는 쪽으로(FR-004).
            outcome = _error(item, policy, Stage.CONTENT_SECRET, type(error).__name__, **_evidence(item))
        if isinstance(outcome, ScreenedContent):
            passed.append(outcome)
            verdicts.append(
                _verdict(
                    item,
                    policy,
                    Verdict.PASSED,
                    Stage.PASSED,
                    rule=_access_rule(item, policy),
                    **_evidence(item),
                )
            )
        else:
            verdicts.append(outcome)
    return tuple(passed), tuple(verdicts)


def _access_rule(item: SourceItem, policy: SecurityPolicy) -> str:
    spec = policy.kinds.get(item.source_kind)
    return spec.rule_name if spec is not None else "unregistered-kind"


def screen_source(
    adapter: SourceAdapter, config: SourceConfig, session: DefaultSourceSession, policy: SecurityPolicy
) -> ScreenResult:
    """contracts/security-filter.md 조립 함수 1~6단계. 판정 기록은 목록 순서를 따른다."""
    listing = list_all(adapter, config, session)
    passed_items, early = screen_items(listing.items, config, policy)
    fetch = fetch_contents(adapter, config, session, replace(listing, items=passed_items))
    by_id = {item.source_id: item for item in passed_items}
    fetch_errors = tuple(
        _error(
            by_id[o.source_id],
            policy,
            Stage.FETCH,
            f"fetch:{o.status.value}:{o.failure.value if o.failure else 'none'}",
            **_evidence(by_id[o.source_id]),
        )
        for o in fetch.items
        if o.status != ItemStatus.SUCCEEDED
    )
    # fetch_contents는 성공한 자료의 본문을 요청 순서대로 담는다. 요청 자료와 받은 본문의 식별자가 다르면
    # 그 본문은 쓰지 않는다. 다른 자료로 간주하면 그 자료의 예외를 받아 통과할 수 있다.
    succeeded = [o.source_id for o in fetch.items if o.status == ItemStatus.SUCCEEDED]
    matched = [c for requested, c in zip(succeeded, fetch.contents, strict=False) if c.source_id == requested]
    passed, late = screen_contents(matched, by_id, config, policy)
    judged = {v.source_id for v in (*fetch_errors, *late)}
    late += tuple(
        _error(by_id[source_id], policy, Stage.FETCH, "fetch:SUCCEEDED:content-mismatch", **_evidence(by_id[source_id]))
        for source_id in succeeded
        if source_id not in judged
    )
    order = {item.source_id: index for index, item in enumerate(listing.items)}
    verdicts = tuple(sorted((*early, *fetch_errors, *late), key=lambda v: order[v.source_id]))
    summary = FilterSummary.from_verdicts(config.name, policy.version, verdicts)
    context = policy.output_context(config.kind)
    for verdict in verdicts:
        record = verdict.to_dict(context)
        logger.info(
            "verdict=%s stage=%s rule=%s source_id=%s",
            record["verdict"],
            record["stage"],
            record["rule"],
            record["source_id"],
        )
    logger.info("summary=%s", summary.to_dict())
    return ScreenResult(passed, verdicts, summary, replace(fetch, contents=()), listing)
