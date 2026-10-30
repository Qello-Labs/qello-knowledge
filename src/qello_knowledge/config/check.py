"""설정 점검 결과와 출력. 이름과 상태만 담고 값은 담지 않는다(FR-008, FR-009)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime

from qello_knowledge.config.loader import Settings, SettingStatus
from qello_knowledge.config.registry import Entrypoint
from qello_knowledge.domain.embedding import BudgetSettings
from qello_knowledge.domain.generation import GenerationSettings
from qello_knowledge.domain.retrieval import RetrievalSettings

BUDGET_NAMES = ("QK_EMBED_DAILY_ALLOWANCE", "QK_EMBED_INDEX_BUDGET", "QK_EMBED_QUERY_RESERVE")
BUDGET_CHECK = "QK_EMBED_INDEX_BUDGET + QK_EMBED_QUERY_RESERVE <= QK_EMBED_DAILY_ALLOWANCE"
GENERATION_NAMES = (
    "QK_GEN_MODEL", "QK_GEN_MAX_TOKENS", "QK_GEN_TEMPERATURE", "QK_GEN_TIMEOUT_SECONDS", "QK_GEN_PROMPT_VERSION",
)  # fmt: skip
GENERATION_CHECK = "QK-GEN-001 생성 입력 최대 예상 <= 모델 컨텍스트"
CODE_LIMIT_OVER_CONTEXT_BUDGET = "CODE_LIMIT_OVER_CONTEXT_BUDGET"
CODE_INDEX_VERSION_UNREGISTERED = "CODE_INDEX_VERSION_UNREGISTERED"


@dataclass(frozen=True)
class CrossCheck:
    """여러 항목을 함께 보는 검사. `detail`에는 숫자만 넣는다."""

    name: str
    ok: bool
    detail: str


@dataclass(frozen=True)
class CheckReport:
    entrypoint: Entrypoint
    items: tuple[tuple[str, SettingStatus], ...]
    ok: bool
    checks: tuple[CrossCheck, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "entrypoint": self.entrypoint.value,
            "ok": self.ok,
            "items": [{"name": name, "status": status.value} for name, status in self.items],
            "checks": [{"name": c.name, "ok": c.ok, "detail": c.detail} for c in self.checks],
            "warnings": list(self.warnings),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    def to_text(self) -> str:
        lines = [f"설정 점검: {self.entrypoint.value}"]
        lines += [f"  {status.value:<8} {name}" for name, status in self.items]
        lines += [f"  {'OK' if c.ok else 'FAIL':<8} {c.name} ({c.detail})" for c in self.checks]
        lines += [f"  WARNING  {name}" for name in self.warnings]
        missing = sum(1 for _, status in self.items if status is SettingStatus.MISSING)
        invalid = sum(1 for _, status in self.items if status is SettingStatus.INVALID)
        verdict = "통과" if self.ok else "실패"
        lines.append(f"결과: {verdict} (누락 {missing}, 형식 오류 {invalid})")
        return "\n".join(lines)


def budget_settings(settings: Settings) -> BudgetSettings | None:
    """세 항목이 모두 형식에 맞으면 `BudgetSettings`로 바꾼다. 하나라도 아니면 `None`."""
    values = []
    for name in BUDGET_NAMES:
        try:
            value = settings.get(name)
        except KeyError:
            return None
        if not isinstance(value, str):
            return None
        values.append(int(value))
    return BudgetSettings(*values)


def _text(settings: Settings, name: str) -> str | None:
    try:
        value = settings.get(name)
    except KeyError:
        return None
    return value if isinstance(value, str) else None


def generation_settings(settings: Settings) -> GenerationSettings | None:
    """불러온 `QK_GEN_*`를 `GenerationSettings`로 바꾸는 하나뿐인 함수(QK-GEN-001). 형식이 어긋나면 `None`."""
    values = {name: _text(settings, name) for name in GENERATION_NAMES}
    if any(value is None for value in values.values()):
        return None
    try:
        return GenerationSettings(
            model_id=str(values["QK_GEN_MODEL"]),
            max_tokens=int(str(values["QK_GEN_MAX_TOKENS"])),
            temperature=float(str(values["QK_GEN_TEMPERATURE"])),
            timeout_seconds=int(str(values["QK_GEN_TIMEOUT_SECONDS"])),
            prompt_version=str(values["QK_GEN_PROMPT_VERSION"]),
        )
    except ValueError:
        return None


def _generation_check(settings: Settings) -> CrossCheck | None:
    """문제가 있을 때만 항목을 만든다. 통과면 `checks`에 넣지 않는다(기존 설정 보고 꼴 유지, tasks T046)."""
    from qello_knowledge.generation.settings import check_settings

    gen = generation_settings(settings)
    budget = _text(settings, "QK_RETRIEVAL_CONTEXT_BUDGET")
    if gen is None or budget is None:
        return None
    problems = check_settings(gen, RetrievalSettings(context_budget=int(budget)))
    return CrossCheck(GENERATION_CHECK, False, "; ".join(problems)) if problems else None


def code_chunking_from(settings: Settings):
    """`QK_CODE_CHUNKING`을 코드 청킹 설정으로 바꾸는 하나뿐인 함수(QK-CHK-001). 꺼짐·없음·형식 오류는 `None`."""
    from qello_knowledge.domain.chunking import CodeChunkingSettings

    return CodeChunkingSettings() if _text(settings, "QK_CODE_CHUNKING") == "on" else None


def _code_checks(settings: Settings) -> tuple[CrossCheck, ...]:
    """켜짐일 때만 계산한다. 질의 경로가 청커를 불러오지 않게 함수 안에서 가져온다(research R-09, plan 재검토 N2)."""
    code = code_chunking_from(settings) if settings.entrypoint is Entrypoint.INDEX else None
    if code is None:
        return ()
    from qello_knowledge.chunking.version import index_chunking_version
    from qello_knowledge.domain.chunking import ChunkingSettings
    from qello_knowledge.domain.embedding import MODELS
    from qello_knowledge.domain.keyword_rules import INDEX_KEYWORD_RULES
    from qello_knowledge.sync.keys import index_version_id, metadata_schema_version

    checks = []
    budget = _text(settings, "QK_RETRIEVAL_CONTEXT_BUDGET")
    model = MODELS[code.model_version]
    if budget is not None:
        context_tokens = code.limit_tokens * model.bytes_per_token_estimate / RetrievalSettings().bytes_per_token
        if context_tokens > int(budget):
            detail = f"{code.limit_tokens} > {budget}"
            checks.append(CrossCheck(CODE_LIMIT_OVER_CONTEXT_BUDGET, False, detail))
    chunking = index_chunking_version(ChunkingSettings(model_version=code.model_version), code)
    # 환경값만으로는 Confluence 켜짐을 모른다. 둘 중 하나라도 등록돼 있으면 통과하고 정확한 값은 자료원 쪽 검사가 본다
    # (QK-ING-003 research R-10).
    versions = {
        index_version_id(model.model_version, model.dimension, chunking, metadata_schema_version(code, confluence))
        for confluence in (False, True)
    }
    if not versions & INDEX_KEYWORD_RULES.keys():
        checks.append(CrossCheck(CODE_INDEX_VERSION_UNREGISTERED, False, CODE_INDEX_VERSION_UNREGISTERED))
    return tuple(checks)


def _budget_check(settings: Settings) -> CrossCheck | None:
    budget = budget_settings(settings)
    if budget is None:
        return None
    detail = f"{budget.index_budget} + {budget.query_reserve} <= {budget.daily_allowance}"
    return CrossCheck(BUDGET_CHECK, budget.within_allowance, detail)


def build_report(settings: Settings) -> CheckReport:
    items: list[tuple[str, SettingStatus]] = []
    ok = True
    for item in settings.items:
        items.append((item.spec.name, item.status))
        if item.status is SettingStatus.INVALID:
            ok = False
        elif item.status is SettingStatus.MISSING and item.spec.required:
            ok = False
    checks = tuple(check for check in (_budget_check(settings), _generation_check(settings)) if check is not None)
    checks += _query_checks(settings) + _code_checks(settings)
    source_check = _source_list_check(settings)
    if source_check is not None:
        checks += (source_check,)
    checks += _obs_checks(settings)
    ok = ok and all(check.ok for check in checks)
    warnings = ()
    if settings.entrypoint is Entrypoint.QUERY and not _text(settings, "QK_DISCORD_ALLOWED_CHANNELS"):
        warnings = ("QK_DISCORD_ALLOWED_CHANNELS",)
    warnings += _obs_warnings(settings)
    return CheckReport(settings.entrypoint, tuple(items), ok, checks, warnings)


def _query_checks(settings: Settings) -> tuple[CrossCheck, ...]:
    if settings.entrypoint is not Entrypoint.QUERY:
        return ()
    names = (
        "QK_QUERY_DEADLINE_SECONDS",
        "QK_QUERY_NOTICE_GRACE_SECONDS",
        "QK_GEN_TIMEOUT_SECONDS",
        "QK_QUERY_MIN_START_SECONDS",
        "QK_QUERY_CALL_LIMIT",
        "QK_DISCORD_MAX_MESSAGES",
    )
    values = [_text(settings, name) for name in names]
    if any(v is None for v in values):
        return ()
    deadline, grace, timeout, minimum, calls, messages = (int(v) for v in values)
    rules = (
        ("notice_before_token_expiry", deadline + grace < 900),
        ("generation_fits_query", 2 * timeout + 5 <= deadline),
        ("minimum_start_before_deadline", minimum < deadline),
        ("query_call_limit", calls >= 7 + 4 + messages * 2),
    )
    # 통과 항목은 기존 보고 꼴을 유지한다(_generation_check와 같은 방식).
    return tuple(CrossCheck(name, False, name) for name, valid in rules if not valid)


def _source_list_check(settings: Settings) -> CrossCheck | None:
    from qello_knowledge.discord.render import source_capacity

    if settings.entrypoint is not Entrypoint.QUERY:
        return None
    values = [
        _text(settings, name)
        for name in ("QK_DISCORD_TITLE_MAX_CHARS", "QK_DISCORD_LINK_MAX_CHARS", "QK_DISCORD_MAX_MESSAGES")
    ]
    if any(value is None for value in values):
        return None
    title, link, messages = (int(value) for value in values)
    items, required = source_capacity(title, link, expand_top=RetrievalSettings().expand_top)
    if items < 1 or required > messages - 1:
        return CrossCheck("discord_source_capacity", False, "discord_source_capacity")
    return None


def _obs_checks(settings):
    if settings.entrypoint is not Entrypoint.QUERY:
        return ()
    checks = []
    if _text(settings, "QK_QUERY_LOG_ENABLED") == "true" and not _text(settings, "QK_QUERY_TEXT_RETAIN_UNTIL"):
        checks.append(CrossCheck("query_text_retention_required", False, "query_text_retention_required"))
    component, relay = (
        _text(settings, name) for name in ("QK_DISCORD_COMPONENT_TIMEOUT_MS", "QK_RELAY_TIMEOUT_SECONDS")
    )
    if component is not None and relay is not None and int(component) >= float(relay) * 1000:
        checks.append(CrossCheck("component_before_relay", False, "component_before_relay"))
    return tuple(checks)


def _obs_warnings(settings):
    from pathlib import Path

    from qello_knowledge.sources.config import load_sources

    warnings = []
    retain = _text(settings, "QK_QUERY_TEXT_RETAIN_UNTIL")
    if retain and date.fromisoformat(retain) < datetime.now(UTC).date():
        warnings.append("원문 기록 보존 상한이 지났습니다. qk-index queries erase-texts를 확인하세요")
    if settings.entrypoint is Entrypoint.QUERY:
        configs, issues = load_sources(Path("config/sources.toml"))
        if not issues and 130 * len(configs) + 150 > 2000:
            warnings.append("sources_message_capacity")
    return tuple(warnings)
