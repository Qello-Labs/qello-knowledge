"""설정 점검 결과와 출력. 이름과 상태만 담고 값은 담지 않는다(FR-008, FR-009)."""

from __future__ import annotations

import json
from dataclasses import dataclass

from qello_knowledge.config.loader import Settings, SettingStatus
from qello_knowledge.config.registry import Entrypoint


@dataclass(frozen=True)
class CheckReport:
    entrypoint: Entrypoint
    items: tuple[tuple[str, SettingStatus], ...]
    ok: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "entrypoint": self.entrypoint.value,
            "ok": self.ok,
            "items": [{"name": name, "status": status.value} for name, status in self.items],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    def to_text(self) -> str:
        lines = [f"설정 점검: {self.entrypoint.value}"]
        lines += [f"  {status.value:<8} {name}" for name, status in self.items]
        missing = sum(1 for _, status in self.items if status is SettingStatus.MISSING)
        invalid = sum(1 for _, status in self.items if status is SettingStatus.INVALID)
        verdict = "통과" if self.ok else "실패"
        lines.append(f"결과: {verdict} (누락 {missing}, 형식 오류 {invalid})")
        return "\n".join(lines)


def build_report(settings: Settings) -> CheckReport:
    items: list[tuple[str, SettingStatus]] = []
    ok = True
    for item in settings.items:
        items.append((item.spec.name, item.status))
        if item.status is SettingStatus.INVALID:
            ok = False
        elif item.status is SettingStatus.MISSING and item.spec.required:
            ok = False
    return CheckReport(settings.entrypoint, tuple(items), ok)
