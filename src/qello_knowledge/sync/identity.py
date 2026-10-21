"""설정과 수집 뒤 원본 정체성 검사. 오류에는 원본 식별값을 넣지 않는다."""

from dataclasses import replace

from qello_knowledge.sync.keys import scope_key


class IdentityError(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def select_targets(targets, stored_sources, source=None):
    from qello_knowledge.sync.plan import SyncTarget

    active = [t for t in targets if t.mode == "FULL" and t.config is not None and t.config.enabled]
    kinds = {}
    for target in active:
        if target.source_kind in kinds:
            raise IdentityError("duplicate_source_kind")
        kinds[target.source_kind] = target.source_name
        for previous in stored_sources.values():
            if previous.source_kind == target.source_kind and previous.source_name != target.source_name:
                raise IdentityError("source_replacement")
        previous = stored_sources.get(target.source_name)
        if previous and (
            previous.source_kind != target.source_kind
            or previous.scope_key != scope_key(target.source_kind, target.config.scope)
        ):
            raise IdentityError("scope_changed")
    result = [replace(t, stored_source=stored_sources.get(t.source_name)) for t in active]
    names = {t.source_name for t in result}
    for name, previous in stored_sources.items():
        if name not in names:
            result.append(SyncTarget(name, previous.source_kind, mode="TAKEDOWN_ONLY", stored_source=previous))
    for target in targets:
        if target.mode == "TAKEDOWN_ONLY" and target.source_name not in {t.source_name for t in result}:
            result.append(target)
    if source is not None:
        result = [t for t in result if t.source_name == source]
        if not result:
            raise IdentityError("unknown_source")
    return tuple(result)


def check_origin(origin, previous):
    if origin is None:
        return "MISSING"
    if previous is None:
        return "REGISTER"
    if (origin.origin_id, origin.origin_name) != (previous.origin_id, previous.origin_name):
        return "MISMATCH"
    return "OK"
