"""설정 로딩. 원천 우선순위는 실행 환경 변수 > `.env` > 기본값이다(FR-004).

비밀 값은 `SecretValue`로 감싸 `str`·`repr`·로그에 나오지 않게 한다(FR-008).
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from qello_knowledge.config.registry import Entrypoint, SettingSpec, specs_for

MASK = "***"


class SecretValue:
    """값을 감춘다. 실제 값은 `reveal()`로만 꺼내고, 어댑터 안에서만 부른다."""

    __slots__ = ("_value",)

    def __init__(self, value: str) -> None:
        self._value = value

    def reveal(self) -> str:
        return self._value

    def __str__(self) -> str:
        return MASK

    def __repr__(self) -> str:
        return f"SecretValue({MASK})"

    def __eq__(self, other: object) -> bool:
        return isinstance(other, SecretValue) and other._value == self._value

    def __hash__(self) -> int:
        return hash(self._value)


class SettingStatus(StrEnum):
    OK = "OK"
    MISSING = "MISSING"
    INVALID = "INVALID"


def parse_env_file(text: str) -> dict[str, str]:
    """`KEY=VALUE` 줄만 읽는다. 주석·빈 줄은 무시하고 감싼 따옴표는 벗긴다."""
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[len("export ") :].lstrip()
        key, sep, value = line.partition("=")
        key = key.strip()
        if not sep or not key:
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key] = value
    return values


def read_env_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    return parse_env_file(path.read_text(encoding="utf-8"))


def merge_sources(environ: Mapping[str, str], dotenv: Mapping[str, str]) -> dict[str, str]:
    """`.env` 위에 실행 환경 변수를 덮는다. 빈 값도 덮는다: 비어 있으면 누락으로 본다."""
    merged = dict(dotenv)
    merged.update(environ)
    return merged


@dataclass(frozen=True)
class Resolved:
    spec: SettingSpec
    status: SettingStatus
    value: str | SecretValue | None


def resolve(spec: SettingSpec, source: Mapping[str, str]) -> Resolved:
    raw = source.get(spec.name)
    if raw is None or not raw.strip():
        if spec.default is not None:
            return Resolved(spec, SettingStatus.OK, spec.default)
        return Resolved(spec, SettingStatus.MISSING, None)
    raw = raw.strip()
    if not spec.rule(raw):
        return Resolved(spec, SettingStatus.INVALID, None)
    return Resolved(spec, SettingStatus.OK, SecretValue(raw) if spec.secret else raw)


@dataclass(frozen=True)
class Settings:
    """진입점 하나가 쓰는 항목의 로딩 결과."""

    entrypoint: Entrypoint
    items: tuple[Resolved, ...]

    def get(self, name: str) -> str | SecretValue | None:
        for item in self.items:
            if item.spec.name == name:
                return item.value
        raise KeyError(name)


def load(
    entrypoint: Entrypoint,
    environ: Mapping[str, str] | None = None,
    env_file: Path | None = Path(".env"),
) -> Settings:
    environ = os.environ if environ is None else environ
    dotenv = read_env_file(env_file) if env_file is not None else {}
    source = merge_sources(environ, dotenv)
    return Settings(entrypoint, tuple(resolve(spec, source) for spec in specs_for(entrypoint)))
