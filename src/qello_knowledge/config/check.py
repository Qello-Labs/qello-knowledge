"""설정 점검 결과와 출력. 이름과 상태만 담고 값은 담지 않는다(FR-008, FR-009)."""

from __future__ import annotations

import json
from dataclasses import dataclass

from qello_knowledge.config.loader import Settings, SettingStatus
from qello_knowledge.config.registry import Entrypoint
from qello_knowledge.domain.embedding import BudgetSettings

BUDGET_NAMES = ("QK_EMBED_DAILY_ALLOWANCE", "QK_EMBED_INDEX_BUDGET", "QK_EMBED_QUERY_RESERVE")
BUDGET_CHECK = "QK_EMBED_INDEX_BUDGET + QK_EMBED_QUERY_RESERVE <= QK_EMBED_DAILY_ALLOWANCE"


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

    def to_dict(self) -> dict[str, object]:
        return {
            "entrypoint": self.entrypoint.value,
            "ok": self.ok,
            "items": [{"name": name, "status": status.value} for name, status in self.items],
            "checks": [{"name": c.name, "ok": c.ok, "detail": c.detail} for c in self.checks],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    def to_text(self) -> str:
        lines = [f"설정 점검: {self.entrypoint.value}"]
        lines += [f"  {status.value:<8} {name}" for name, status in self.items]
        lines += [f"  {'OK' if c.ok else 'FAIL':<8} {c.name} ({c.detail})" for c in self.checks]
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
    checks = tuple(check for check in (_budget_check(settings),) if check is not None)
    ok = ok and all(check.ok for check in checks)
    return CheckReport(settings.entrypoint, tuple(items), ok, checks)
