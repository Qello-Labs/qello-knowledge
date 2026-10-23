"""설정 항목 정의. 항목을 추가하거나 바꿀 때는 이 파일만 고친다(FR-005).

항목 이름은 `docs/sdd/research/tokens.md` 6절의 `.env` 변수 이름을 그대로 쓴다.
형식 규칙은 통과 여부만 돌려주고, 오류 문구에 값을 넣지 않는다(FR-008).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit


class Entrypoint(StrEnum):
    QUERY = "query"
    INDEX = "index"


BOTH = frozenset({Entrypoint.QUERY, Entrypoint.INDEX})


@dataclass(frozen=True)
class Rule:
    """값 형식 규칙. `description`은 문서와 `.env.example`에 쓴다."""

    description: str
    check: Callable[[str], bool]

    def __call__(self, value: str) -> bool:
        return self.check(value)


def _pattern(regex: str, description: str) -> Rule:
    compiled = re.compile(regex)
    return Rule(description, lambda value: compiled.fullmatch(value) is not None)


def _postgres_url(value: str) -> bool:
    try:
        parts = urlsplit(value)
    except ValueError:
        return False
    return parts.scheme in {"postgres", "postgresql"} and bool(parts.hostname)


POSTGRES_URL = Rule("`postgres` 또는 `postgresql` 스킴의 URL", _postgres_url)
GITHUB_TOKEN = _pattern(r"(?:ghp_|github_pat_)\S+", "`ghp_` 또는 `github_pat_`로 시작")
NO_SPACE_40 = _pattern(r"\S{40,}", "공백 없는 40자 이상")
NO_SPACE_50 = _pattern(r"\S{50,}", "공백 없는 50자 이상")
HEX_32 = _pattern(r"[0-9a-fA-F]{32}", "32자리 16진수")
HEX_64 = _pattern(r"[0-9a-fA-F]{64}", "64자리 16진수")
DIGITS_17_20 = _pattern(r"[0-9]{17,20}", "숫자 17~20자리")
POSITIVE_INT = _pattern(r"[1-9][0-9]{0,8}", "양의 정수")
LOG_LEVEL = _pattern(r"DEBUG|INFO|WARNING|ERROR", "`DEBUG`, `INFO`, `WARNING`, `ERROR` 중 하나")
CONTEXT_BUDGET = _pattern(r"[1-9][0-9]{0,2}|[1-7][0-9]{3}|8000", "1 이상 8000 이하 정수")
GEN_MODEL = _pattern(r"@cf/qwen/qwen3-[A-Za-z0-9._-]+", "`@cf/qwen/qwen3-`로 시작하는 Workers AI 모델 식별자")
GEN_MAX_TOKENS = _pattern(r"[1-9][0-9]{0,2}|[1-3][0-9]{3}|40[0-8][0-9]|409[0-6]", "1 이상 4096 이하 정수")
GEN_TEMPERATURE = _pattern(r"0(?:\.[0-9]{1,3})?|1(?:\.0{1,3})?", "0 이상 1 이하 소수(소수점 아래 3자리까지)")
GEN_TIMEOUT = _pattern(r"[1-9]|[1-5][0-9]|60", "1 이상 60 이하 정수(초)")
GEN_PROMPT = _pattern(r"gen-p1|gen-base", "`gen-p1` 또는 `gen-base`")


@dataclass(frozen=True)
class SettingSpec:
    name: str
    description: str
    entrypoints: frozenset[Entrypoint]
    required: bool
    secret: bool
    rule: Rule
    default: str | None = None

    def __post_init__(self) -> None:
        if not re.fullmatch(r"[A-Z][A-Z0-9_]*", self.name):
            raise ValueError(f"설정 이름 형식 오류: {self.name}")
        if not self.description.strip():
            raise ValueError(f"설명이 비어 있음: {self.name}")
        if not self.entrypoints:
            raise ValueError(f"진입점이 없음: {self.name}")
        if self.secret and self.default is not None:
            raise ValueError(f"비밀 항목은 기본값을 가질 수 없음: {self.name}")
        if self.default is not None and not self.rule(self.default):
            raise ValueError(f"기본값이 형식 규칙에 맞지 않음: {self.name}")


SETTINGS: tuple[SettingSpec, ...] = (
    SettingSpec(
        name="DATABASE_URL",
        description="PostgreSQL 연결 문자열. 로컬 개발은 compose.yaml의 DB를 가리킨다",
        entrypoints=BOTH,
        required=True,
        secret=True,
        rule=POSTGRES_URL,
    ),
    SettingSpec(
        name="GITHUB_API_TOKEN",
        description="GitHub 저장소 읽기 전용 토큰",
        entrypoints=frozenset({Entrypoint.INDEX}),
        required=True,
        secret=True,
        rule=GITHUB_TOKEN,
    ),
    SettingSpec(
        name="CLOUDFLARE_API_TOKEN",
        description="Workers 밖 색인에서 Workers AI REST를 부를 때 쓰는 토큰",
        entrypoints=frozenset({Entrypoint.INDEX}),
        required=True,
        secret=True,
        rule=NO_SPACE_40,
    ),
    SettingSpec(
        name="CLOUDFLARE_ACCOUNT_ID",
        description="Workers AI REST 호출에 쓰는 Cloudflare 계정 ID",
        entrypoints=frozenset({Entrypoint.INDEX}),
        required=True,
        secret=False,
        rule=HEX_32,
    ),
    SettingSpec(
        name="DISCORD_APPLICATION_ID",
        description="Discord 애플리케이션 ID",
        entrypoints=frozenset({Entrypoint.QUERY}),
        required=True,
        secret=False,
        rule=DIGITS_17_20,
    ),
    SettingSpec(
        name="DISCORD_PUBLIC_KEY",
        description="Discord 상호작용 요청 서명 검증용 공개 키",
        entrypoints=frozenset({Entrypoint.QUERY}),
        required=True,
        secret=False,
        rule=HEX_64,
    ),
    SettingSpec(
        name="DISCORD_BOT_TOKEN",
        description="Discord 봇 토큰. HTTP 상호작용만 쓰면 필요 없다(QK-BOT-001에서 확정)",
        entrypoints=frozenset({Entrypoint.QUERY}),
        required=False,
        secret=True,
        rule=NO_SPACE_50,
    ),
    SettingSpec(
        name="QK_LOG_LEVEL",
        description="로그 수준",
        entrypoints=BOTH,
        required=False,
        secret=False,
        rule=LOG_LEVEL,
        default="INFO",
    ),
    SettingSpec(
        name="QK_EMBED_DAILY_ALLOWANCE",
        description="Workers AI 하루 무료 할당(Neurons). 하루 경계는 00:00 UTC다",
        entrypoints=BOTH,
        required=False,
        secret=False,
        rule=POSITIVE_INT,
        default="10000",
    ),
    SettingSpec(
        name="QK_EMBED_INDEX_BUDGET",
        description="색인 임베딩이 하루에 쓸 수 있는 Neurons. 색인 예산 + 질의응답 예비분은 하루 할당 이하여야 한다",
        entrypoints=BOTH,
        required=False,
        secret=False,
        rule=POSITIVE_INT,
        default="5000",
    ),
    SettingSpec(
        name="QK_EMBED_QUERY_RESERVE",
        description="질의응답 몫으로 남겨 두는 하루 Neurons. 넘으면 경고만 하고 질의는 막지 않는다",
        entrypoints=BOTH,
        required=False,
        secret=False,
        rule=POSITIVE_INT,
        default="3000",
    ),
    SettingSpec(
        name="QK_RETRIEVAL_CONTEXT_BUDGET",
        description="검색이 생성에 넘기는 Context의 예상 토큰 예산(QK-RET-001). 프롬프트·출력 몫은 들어 있지 않다",
        entrypoints=BOTH,
        required=False,
        secret=False,
        rule=CONTEXT_BUDGET,
        default="2000",
    ),
    SettingSpec(
        name="QK_GEN_MODEL",
        description="답변 생성 모델(QK-GEN-001, ADR-009). qwen3 계열만 받는다. 다른 계열은 ADR-009 개정이 필요하다",
        entrypoints=BOTH,
        required=False,
        secret=False,
        rule=GEN_MODEL,
        default="@cf/qwen/qwen3-30b-a3b-fp8",
    ),
    SettingSpec(
        name="QK_GEN_MAX_TOKENS",
        description="답변 생성 출력 상한(토큰)",
        entrypoints=BOTH,
        required=False,
        secret=False,
        rule=GEN_MAX_TOKENS,
        default="800",
    ),
    SettingSpec(
        name="QK_GEN_TEMPERATURE",
        description="답변 생성 온도",
        entrypoints=BOTH,
        required=False,
        secret=False,
        rule=GEN_TEMPERATURE,
        default="0.2",
    ),
    SettingSpec(
        name="QK_GEN_TIMEOUT_SECONDS",
        description="생성 호출 한 번의 시간 제한(초). 재시도 마감은 이 값의 두 배 + 5초다",
        entrypoints=BOTH,
        required=False,
        secret=False,
        rule=GEN_TIMEOUT,
        default="20",
    ),
    SettingSpec(
        name="QK_GEN_PROMPT_VERSION",
        description="답변 생성 프롬프트. 기본은 승인된 후보 1, 비교용은 기준 프롬프트다",
        entrypoints=BOTH,
        required=False,
        secret=False,
        rule=GEN_PROMPT,
        default="gen-p1",
    ),
)


def specs_for(entrypoint: Entrypoint) -> tuple[SettingSpec, ...]:
    """그 진입점이 쓰는 항목만 이름순으로 돌려준다(FR-006)."""
    return tuple(sorted((s for s in SETTINGS if entrypoint in s.entrypoints), key=lambda s: s.name))
