"""보안 판정 결과. 출력은 `to_dict(context)`만 쓰고, 모든 문자열은 필드 종류별로 가린다."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from qello_knowledge.domain.redact import FieldKind, OutputContext, safe_text
from qello_knowledge.domain.source import FetchResult, Listing, SourceContent, SourceItem


class AccessScope(StrEnum):
    TEAM = "TEAM"
    RESTRICTED = "RESTRICTED"
    UNKNOWN = "UNKNOWN"


class Verdict(StrEnum):
    PASSED = "PASSED"
    PATH_EXCLUDED = "PATH_EXCLUDED"
    ACCESS_HELD = "ACCESS_HELD"
    SECRET_BLOCKED = "SECRET_BLOCKED"  # noqa: S105 - 판정 이름이다
    ERROR = "ERROR"


class Stage(StrEnum):
    PATH = "PATH"
    ACCESS = "ACCESS"
    ITEM_SECRET = "ITEM_SECRET"  # noqa: S105 - 판정 이름이다
    FETCH = "FETCH"
    CONTENT_SECRET = "CONTENT_SECRET"  # noqa: S105 - 판정 이름이다
    PASSED = "PASSED"


@dataclass(frozen=True)
class SecurityVerdict:
    source_name: str
    source_id: str
    location: str
    url: str
    title: str | None
    verdict: Verdict
    stage: Stage
    rules_version: str
    rule: str | None = None
    lines: tuple[int, ...] = ()
    field: str | None = None
    access_scope: AccessScope | None = None
    access_raw: tuple[tuple[str, str], ...] = ()
    error_type: str | None = None

    def __post_init__(self) -> None:
        if self.verdict == Verdict.PASSED and self.access_scope != AccessScope.TEAM:
            raise ValueError("통과한 자료의 접근 범위는 팀 공용이어야 한다")
        if self.verdict == Verdict.ACCESS_HELD and self.access_scope not in {
            AccessScope.RESTRICTED,
            AccessScope.UNKNOWN,
        }:
            raise ValueError("접근 범위 보류는 제한이나 미확인이어야 한다")
        if self.verdict == Verdict.ERROR and not self.error_type:
            raise ValueError("판정 실패에는 오류 유형이 필요하다")

    def to_dict(self, context: OutputContext) -> dict:
        """data-model.md의 필드→FieldKind 대응대로 가린 값만 담는다."""

        def text(value: str | None) -> str | None:
            return None if value is None else safe_text(value, FieldKind.TEXT, context)

        id_kind = FieldKind.PATH if context.source_id_is_path else FieldKind.TEXT
        return {
            "source_name": self.source_name,
            "source_id": safe_text(self.source_id, id_kind, context),
            "location": safe_text(self.location, FieldKind.PATH, context),
            "url": safe_text(self.url, FieldKind.LINK, context),
            "title": text(self.title),
            "verdict": self.verdict.value,
            "stage": self.stage.value,
            "rule": self.rule,
            "lines": list(self.lines),
            "field": self.field,
            "access_scope": self.access_scope.value if self.access_scope is not None else None,
            "access_raw": [[text(key), text(value)] for key, value in self.access_raw],
            "error_type": text(self.error_type),
            "rules_version": self.rules_version,
        }


@dataclass(frozen=True)
class ScreenedContent:
    item: SourceItem
    content: SourceContent = field(repr=False)
    access_scope: AccessScope
    rules_version: str


@dataclass(frozen=True)
class FilterSummary:
    source_name: str
    rules_version: str
    by_verdict: Mapping[Verdict, int]
    by_rule: Mapping[str, int]
    by_access_scope: Mapping[AccessScope, int]

    @classmethod
    def from_verdicts(cls, source_name: str, rules_version: str, verdicts: Iterable[SecurityVerdict]) -> FilterSummary:
        verdicts = tuple(verdicts)
        return cls(
            source_name,
            rules_version,
            {v: n for v, n in Counter(x.verdict for x in verdicts).items()},
            {r: n for r, n in Counter(x.rule for x in verdicts if x.rule is not None).items()},
            {s: n for s, n in Counter(x.access_scope for x in verdicts if x.access_scope is not None).items()},
        )

    def to_dict(self) -> dict:
        return {
            "source_name": self.source_name,
            "rules_version": self.rules_version,
            "by_verdict": {v.value: n for v, n in sorted(self.by_verdict.items())},
            "by_rule": dict(sorted(self.by_rule.items())),
            "by_access_scope": {s.value: n for s, n in sorted(self.by_access_scope.items())},
        }


@dataclass(frozen=True)
class ScreenResult:
    passed: tuple[ScreenedContent, ...]
    verdicts: tuple[SecurityVerdict, ...]
    summary: FilterSummary
    fetch: FetchResult
    listing: Listing | None = field(default=None, repr=False)
