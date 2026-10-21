"""수집·필터·청킹·내림 판단. 저장소 쓰기 없이 실행과 미리 보기가 공유한다."""

from dataclasses import dataclass, field, replace

from qello_knowledge.chunking.service import chunk_screened
from qello_knowledge.chunking.version import chunking_version
from qello_knowledge.domain.chunking import ChunkingSummary, ChunkOutcomeKind
from qello_knowledge.domain.redact import FieldKind, safe_text
from qello_knowledge.domain.scope import in_scope
from qello_knowledge.domain.security import Verdict
from qello_knowledge.domain.source import ItemStatus
from qello_knowledge.domain.sync import (
    Action,
    DocumentDecision,
    HoldReason,
    Operation,
    SourcePlan,
    TakedownReason,
    allowed,
)
from qello_knowledge.security.screen import screen_source, source_excluded
from qello_knowledge.sync.decide import change_reason, constrain, exceeds_takedown_ratio
from qello_knowledge.sync.keys import chunk_input_hash, doc_key


@dataclass(frozen=True)
class SyncTarget:
    source_name: str
    source_kind: str
    mode: str = "FULL"
    config: object = field(default=None, repr=False)
    adapter: object = field(default=None, repr=False)
    session: object = field(default=None, repr=False)
    stored_source: object = field(default=None, repr=False)
    holds: frozenset = frozenset()


def _settled_security_takedown(previous, reason, access_scope=None):
    scope = {"TEAM": "team", "RESTRICTED": "restricted"}.get(access_scope)
    return (
        previous.status == "deleted"
        and previous.takedown_reason == reason
        and not previous.purge_pending
        and previous.access_scope == scope
    )


def plan_source(target, deps, stored, index_version, options):
    decisions, to_chunk, chunk_results = {}, [], []
    settled = set()
    holds = set(target.holds)
    context = deps.policy.output_context(target.source_kind)

    def doc(identity, action, **kwargs):
        previous = stored.get(identity)
        return DocumentDecision(
            doc_key=doc_key(target.source_name, target.source_kind, identity),
            display=safe_text(identity, FieldKind.PATH if context.source_id_is_path else FieldKind.TEXT, context),
            source_name=target.source_name,
            source_id=identity,
            artifact_id=previous.artifact_id if previous else None,
            actions=(action,),
            **kwargs,
        )

    origin_check = "OK"
    result = None
    listing = None
    if target.mode == "TAKEDOWN_ONLY":
        for identity, previous in stored.items():
            if previous.takedown_reason != TakedownReason.SOURCE_DISABLED:
                decisions[identity] = doc(identity, Action.TAKE_DOWN, takedown_reason=TakedownReason.SOURCE_DISABLED)
    else:
        result = screen_source(target.adapter, target.config, target.session, deps.policy)
        listing = result.listing
        from qello_knowledge.sync.identity import check_origin

        origin_check = check_origin(listing.origin, target.stored_source)
        if origin_check in {"MISSING", "MISMATCH"}:
            holds.add(HoldReason.ORIGIN_MISSING if origin_check == "MISSING" else HoldReason.ORIGIN_MISMATCH)
        if not listing.complete or result.fetch.stop:
            holds.add(HoldReason.COLLECTION_INCOMPLETE)
        for screened in result.passed:
            item, content = screened.item, screened.content
            previous = stored.get(item.source_id)
            fingerprint = chunk_input_hash(content.content_hash, content.location, content.title or item.title)
            reason = change_reason(previous, fingerprint, chunking_version(deps.chunking_settings), index_version)
            decision = doc(
                item.source_id,
                Action.PROCESS if reason else Action.UNCHANGED,
                change_reason=reason,
                fingerprint=fingerprint,
            )
            if reason and allowed(holds, Operation.PROCESS):
                to_chunk.append((decision, screened))
            else:
                decisions[item.source_id] = decision
        if to_chunk:
            chunking = chunk_screened([s for d, s in to_chunk], deps.chunking_settings)
            chunk_results = list(chunking.results)
            for (decision, _screened), chunked in zip(to_chunk, chunking.results, strict=True):
                if chunked.outcome == ChunkOutcomeKind.FAILED:
                    decision = replace(
                        decision, actions=(Action.FAIL,), stage="chunk", failure=chunked.failure.value.lower()
                    )
                elif chunked.outcome == ChunkOutcomeKind.NOT_MARKDOWN:
                    decision = replace(
                        decision,
                        actions=(Action.TAKE_DOWN,) if decision.artifact_id else (Action.SKIP,),
                        takedown_reason=TakedownReason.NOT_TARGET,
                    )
                else:
                    decision = replace(decision, chunked=chunked)
                decisions[decision.source_id] = decision
        skipped = {o.source_id for o in result.fetch.items if o.status == ItemStatus.SKIPPED}
        for verdict in result.verdicts:
            if verdict.verdict == Verdict.PASSED:
                continue
            reason = {
                Verdict.PATH_EXCLUDED: TakedownReason.SECURITY_PATH,
                Verdict.SECRET_BLOCKED: TakedownReason.SECURITY_SECRET,
                Verdict.ACCESS_HELD: TakedownReason.SECURITY_ACCESS,
            }.get(verdict.verdict)
            if reason:
                if verdict.source_id in stored:
                    if _settled_security_takedown(stored[verdict.source_id], reason, verdict.access_scope):
                        settled.add(verdict.source_id)
                        continue
                    decisions[verdict.source_id] = doc(
                        verdict.source_id,
                        Action.TAKE_DOWN,
                        takedown_reason=reason,
                        delete_bodies=True,
                        access_scope=verdict.access_scope,
                        rule=verdict.rule,
                        lines=verdict.lines,
                    )
                else:
                    decisions[verdict.source_id] = doc(
                        verdict.source_id,
                        Action.SKIP,
                        stage="screen",
                        failure=reason.value,
                        rule=verdict.rule,
                        lines=verdict.lines,
                    )
            else:
                failure = next(
                    (
                        o.failure.value.lower()
                        for o in result.fetch.items
                        if o.source_id == verdict.source_id and o.failure
                    ),
                    "screen_error",
                )
                decisions[verdict.source_id] = doc(
                    verdict.source_id,
                    Action.SKIP if verdict.source_id in skipped else Action.FAIL,
                    stage="fetch" if verdict.stage == "FETCH" else "screen",
                    failure=failure,
                )
        listed = {item.source_id for item in listing.items}
        for identity, previous in stored.items():
            if previous.location and source_excluded(previous.location, target.config):
                if not _settled_security_takedown(previous, TakedownReason.CONFIG_EXCLUDED):
                    decisions[identity] = doc(
                        identity, Action.TAKE_DOWN, takedown_reason=TakedownReason.CONFIG_EXCLUDED, delete_bodies=True
                    )
            elif (
                identity not in decisions
                and identity not in settled
                and listing.complete
                and not result.fetch.stop
                and (
                    identity not in listed
                    or (previous.location and not in_scope(previous.location, target.config.scope.include, ()))
                )
                and previous.takedown_reason
                not in {TakedownReason.SOURCE_MISSING, TakedownReason.SOURCE_DISABLED, TakedownReason.NOT_TARGET}
            ):
                decisions[identity] = doc(identity, Action.TAKE_DOWN, takedown_reason=TakedownReason.SOURCE_MISSING)
    pending = {identity for identity, previous in stored.items() if previous.purge_pending}
    general = sum(Action.TAKE_DOWN in d.actions and not d.takedown_reason.is_security for d in decisions.values())
    purge = len(
        pending | {i for i, d in decisions.items() if Action.TAKE_DOWN in d.actions and d.takedown_reason.is_security}
    )
    base = sum(
        r.takedown_reason
        not in {TakedownReason.SOURCE_MISSING, TakedownReason.NOT_TARGET, TakedownReason.SOURCE_DISABLED}
        for r in stored.values()
    )
    if not options.confirm_takedown and exceeds_takedown_ratio(base, general, purge):
        holds.add(HoldReason.TAKEDOWN_RATIO)
    if options.confirm_takedown:
        for identity in pending:
            decision = decisions.get(identity)
            decisions[identity] = (
                replace(decision, actions=(Action.PURGE, *decision.actions))
                if decision
                else doc(identity, Action.PURGE)
            )
    decisions = tuple(constrain(d, holds) for d in decisions.values())
    fetch = result.fetch.to_dict() if result else {}
    fetch.pop("items", None)
    return SourcePlan(
        source_name=target.source_name,
        mode=target.mode,
        decisions=decisions,
        origin=listing.origin if listing else None,
        origin_check=origin_check,
        origin_version=listing.origin.version if listing and listing.origin else None,
        listing_complete=listing.complete if listing else None,
        stop=result.fetch.stop if result else None,
        fetch_summary=fetch,
        filter_summary=result.summary if result else None,
        chunking_summary=ChunkingSummary.from_results(chunk_results),
        holds=frozenset(holds),
        takedown_ratio={"general": general, "purge": purge, "base": base, "threshold": 0.2},
    )
