"""저장 상태와 청킹 입력 지문의 비교."""

from qello_knowledge.domain.sync import ChangeReason


def change_reason(stored, fingerprint, chunking_version, index_version):
    if stored is None:
        return ChangeReason.NEW
    if stored.chunk_input_hash != fingerprint:
        return ChangeReason.INPUT_CHANGED
    if stored.processed_chunking_version != chunking_version:
        return ChangeReason.CHUNKING_CHANGED
    if stored.status != "active" or stored.access_scope != "team":
        return ChangeReason.REINSTATED
    if stored.processed_index_version != index_version:
        return ChangeReason.INDEX_CHANGED
    return None


def exceeds_takedown_ratio(base, general, purge):
    return max(general, purge) > base * 0.2


def constrain(doc, holds):
    """보류가 막는 동작을 HOLD 결과로 바꾼다. 보안 검색 제외는 항상 남긴다."""
    from dataclasses import replace

    from qello_knowledge.domain.sync import Action, Operation, TakedownReason, allowed

    actions = []
    blocked = False
    delete = doc.delete_bodies
    for action in doc.actions:
        operation = None
        if action == Action.PROCESS:
            operation = Operation.PROCESS
        elif action == Action.UNCHANGED:
            operation = Operation.MARK_SEEN
        elif action == Action.PURGE:
            operation = Operation.PURGE
        elif action == Action.TAKE_DOWN:
            reason = doc.takedown_reason
            operation = (
                Operation.SECURITY_HIDE
                if reason.is_security
                else (
                    Operation.SOURCE_MISSING if reason == TakedownReason.SOURCE_MISSING else Operation.GENERAL_TAKEDOWN
                )
            )
            delete = delete and allowed(holds, Operation.SECURITY_PURGE)
        if operation is None or allowed(holds, operation):
            actions.append(action)
        else:
            blocked = True
    if not actions:
        actions = [Action.HOLD]
    hold = next((h for h in sorted(holds) if not allowed({h}, operation)), None) if blocked and operation else None
    return replace(
        doc, actions=tuple(actions), delete_bodies=delete, hold=hold, failure=hold.value if hold else doc.failure
    )
