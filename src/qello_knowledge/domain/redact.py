"""판정 기록·로그로 내보내는 값을 가린다. 판정(식별자 주소)과 기록이 같은 함수를 쓴다(research R-07).

맨 호스트 이름과 파일 이름은 글자만으로 구분할 수 없다. 그래서 확장자 예외는 경로 필드의 파일 이름 부분에만
적용하고, 글 필드에서는 숫자 버전이 아닌 점 이름을 모두 주소로 본다.
"""

from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from enum import StrEnum
from urllib.parse import unquote, urlsplit

from qello_knowledge.domain.secret_rules import find_secrets

ADDRESS_MASK = "[가림:address]"
ADDRESS_POLICY_VERSION = "address-v3"
FILE_EXTENSIONS = frozenset(
    {
        "md", "mdx", "markdown", "txt", "rst", "adoc",
        "py", "java", "kt", "kts", "ts", "tsx", "js", "jsx", "mjs", "go", "rs", "sh",
        "json", "yml", "yaml", "toml", "ini", "cfg", "conf", "properties", "env",
        "sql", "tf", "hcl", "xml", "gradle", "csv", "html", "css", "png", "svg", "jpg", "jpeg", "gif", "pdf",
    }
)  # fmt: skip
SCHEME_URL = re.compile(r"\b[A-Za-z][A-Za-z0-9+.-]*://[^\s\"'<>]+")
# IP는 경계 정규식으로 찾지 않는다. 숫자·16진수·`:`·`.`가 이어진 구간 안에서 후보를 `ipaddress`로 검증한다.
# 점이나 확장자가 바로 앞뒤에 붙은 주소(`file.10.0.0.5.md`)도 놓치지 않으려는 것이다.
IP_RUN = re.compile(r"[0-9A-Fa-f:.]{2,}")
IP_MAX_LENGTH = 45  # IPv4를 붙인 IPv6 표기의 최대 길이
LETTER = re.compile(r"[A-Za-z]")
HOST_PORT = re.compile(r"(?<![\w.-])[A-Za-z][A-Za-z0-9.-]*:\d{1,5}\b")
DOTTED_NAME = re.compile(r"(?<![\w.-])[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+(?![\w-])")
FILE_NAME = re.compile(r"^(?P<stem>.+)\.(?P<ext>[A-Za-z0-9]+)$")


class FieldKind(StrEnum):
    LINK = "LINK"
    PATH = "PATH"
    TEXT = "TEXT"


@dataclass(frozen=True)
class AddressPolicy:
    patterns: tuple[re.Pattern[str], ...] = (SCHEME_URL, IP_RUN, HOST_PORT, DOTTED_NAME)
    file_extensions: frozenset[str] = FILE_EXTENSIONS
    version: str = ADDRESS_POLICY_VERSION


@dataclass(frozen=True)
class OutputContext:
    public_link_hosts: tuple[str, ...] = ()
    source_id_is_path: bool = False
    address_policy: AddressPolicy = field(default_factory=AddressPolicy)


def _is_ip(candidate: str) -> bool:
    try:
        ipaddress.ip_address(candidate)
    except ValueError:
        return False
    return True


def _is_letter(value: str, index: int) -> bool:
    return 0 <= index < len(value) and LETTER.match(value[index]) is not None


def _code_like(value: str, start: int, end: int) -> bool:
    """`std::map`, `Foo::bar()`처럼 숫자 없이 영문자에 붙은 후보는 코드로 보고 주소로 보지 않는다.

    숫자가 하나라도 든 후보는 앞뒤에 무엇이 붙든(`10.0.0.5_backup`, `a2001:db8::1`) 주소로 본다.
    """
    candidate = value[start:end]
    return not any(c.isdigit() for c in candidate) and (_is_letter(value, start - 1) or _is_letter(value, end))


def _mask_ips(value: str, ip_run: re.Pattern[str]) -> str:
    """구간마다 왼쪽부터 가장 긴 유효 IP 후보를 가린다."""
    out, last = [], 0
    for match in ip_run.finditer(value):
        run, base, i = match.group(0), match.start(), 0
        while i < len(run):
            end = None
            if run[i] != ".":
                for j in range(min(len(run), i + IP_MAX_LENGTH), i + 1, -1):
                    if _is_ip(run[i:j]) and not _code_like(value, base + i, base + j):
                        end = j
                        break
            if end is None:
                i += 1
                continue
            out += [value[last : base + i], ADDRESS_MASK]
            last, i = base + end, end
    return "".join(out) + value[last:]


def _mask_definite(value: str, policy: AddressPolicy) -> str:
    """스킴 주소, IP, `host:port`처럼 글자만으로 주소가 확실한 것을 가린다."""
    scheme, ip_run, host_port, _ = policy.patterns
    value = scheme.sub(ADDRESS_MASK, value)
    value = _mask_ips(value, ip_run)
    return host_port.sub(ADDRESS_MASK, value)


def _mask_text(value: str, policy: AddressPolicy) -> str:
    dotted = policy.patterns[3]
    value = _mask_definite(value, policy)
    return dotted.sub(lambda m: m.group(0) if all(p.isdigit() for p in m.group(0).split(".")) else ADDRESS_MASK, value)


def _mask_path(value: str, policy: AddressPolicy) -> str:
    *directories, name = value.split("/")
    masked = [_mask_text(part, policy) for part in directories]
    match = FILE_NAME.match(name)
    is_file_name = match is not None and match.group("ext").lower() in policy.file_extensions
    masked.append(_mask_definite(name, policy) if is_file_name else _mask_text(name, policy))
    return "/".join(masked)


def _mask_link(value: str, context: OutputContext) -> str:
    try:
        parts = urlsplit(value)
        port = parts.port
    except ValueError:
        return ADDRESS_MASK
    public = (
        parts.scheme == "https"
        and parts.hostname is not None
        and parts.hostname.lower() in context.public_link_hosts
        and port in (None, 443)
        and parts.username is None
    )
    if not public:
        return ADDRESS_MASK
    # 공개 호스트 링크라도 경로·쿼리에 주소가 들어 있으면 링크 전체를 가린다.
    policy = context.address_policy
    path = _decode(parts.path).lstrip("/")
    unsafe_path = bool(path) and _mask_path(path, policy) != path
    rest = (_decode(part) for part in (parts.query, parts.fragment) if part)
    unsafe_rest = any(_mask_text(part, policy) != part for part in rest)
    return ADDRESS_MASK if unsafe_path or unsafe_rest else value


def _decode(value: str) -> str:
    """퍼센트 인코딩을 값이 더 바뀌지 않을 때까지(최대 3번) 푼다. 인코딩으로 규칙을 피하지 못하게 한다."""
    for _ in range(3):
        decoded = unquote(value)
        if decoded == value:
            break
        value = decoded
    return value


def _masked(value: str, field_kind: FieldKind, context: OutputContext) -> tuple[str, str | None]:
    decoded = _decode(value)
    hits = find_secrets(value) or find_secrets(decoded)
    if hits:
        return f"[가림:{hits[0].rule}]", hits[0].rule
    if decoded != value and _plain_masked(decoded, field_kind, context) != decoded:
        return ADDRESS_MASK, "address"
    out = _plain_masked(value, field_kind, context)
    return out, (None if out == value else "address")


def _plain_masked(value: str, field_kind: FieldKind, context: OutputContext) -> str:
    if field_kind == FieldKind.LINK:
        return _mask_link(value, context)
    if field_kind == FieldKind.PATH:
        return _mask_path(value, context.address_policy)
    return _mask_text(value, context.address_policy)


def safe_text(value: str, field_kind: FieldKind, context: OutputContext) -> str:
    """비밀값이면 필드 전체를, 주소면 그 부분을 가린 값을 돌려준다."""
    return _masked(value, field_kind, context)[0]


def has_unsafe(value: str, field_kind: FieldKind, context: OutputContext) -> str | None:
    """가릴 것이 있으면 비밀값 규칙 이름 또는 `address`, 없으면 `None`."""
    return _masked(value, field_kind, context)[1]
