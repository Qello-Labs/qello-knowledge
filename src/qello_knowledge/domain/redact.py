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
ADDRESS_POLICY_VERSION = "address-v6"
FILE_EXTENSIONS = frozenset(
    {
        "md", "mdx", "markdown", "txt", "rst", "adoc",
        "py", "java", "kt", "kts", "ts", "tsx", "js", "jsx", "mjs", "go", "rs", "sh",
        "json", "yml", "yaml", "toml", "ini", "cfg", "conf", "properties", "env",
        "sql", "tf", "hcl", "xml", "gradle", "csv", "html", "css", "png", "svg", "jpg", "jpeg", "gif", "pdf",
    }
)  # fmt: skip
# `\b`·`\w`는 한글 같은 비ASCII 글자도 단어 문자로 봐서 그 글자에 바로 붙은 주소를 놓친다(#70).
# 경계는 ASCII 영숫자·밑줄로만 본다.
WORD = "A-Za-z0-9_"
# 스킴 주소는 `://`가 있어 글자만으로 주소가 확실하므로 앞 경계를 두지 않는다(#79). 패턴은 `://` 앞 스킴 문자 덩어리의
# 첫 글자에서만 맞춰 보고, 맞으면 덩어리 시작부터 가린다(`_mask_scheme`). 첫 글자 앞의 숫자·점이 IPv4 조각으로
# 남지 않게 한다. 다만 덩어리 바로 앞이 `:`이면 맨 앞 숫자 5자까지는 포트일 수 있어 남겨 `host:port` 패턴이 가리게 한다.
# 시작 위치마다 덩어리를 다시 훑으면 긴 `a.a.a…`에서 길이의 제곱이 걸린다.
SCHEME_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+.-")
SCHEME_URL = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s\"'<>]+")
# IP는 경계 정규식으로 찾지 않고 후보를 `ipaddress` 문법으로 검증한다.
# 점이나 확장자가 바로 붙은 주소도 놓치지 않으려는 것이다.
# IPv6는 콜론이 두 개 이상인 16진 구간 안에서 찾는다. 코드(`std::map`)와 주소(`face::beef`)는 글자로 구분할 수 없어
# 유효한 IPv6 후보는 모두 가린다. IPv4는 점 하나씩으로 이어진 숫자 덩어리 전체가 IPv4일 때만 가린다(`1.2.3.456`은 버전).
# `..`는 덩어리를 끊는다. `v1.2..` 뒤에 붙은 IPv4를 놓치지 않으려는 것이다(#79).
IP_RUN = re.compile(r"[0-9A-Fa-f:.]+")
IPV4_DIGITS = re.compile(r"[0-9]+(?:\.[0-9]+)*")
# IPv6 후보는 `ipaddress`가 받는 표기와 같은 RFC 3986 3.2.2 문법으로 찾는다. 위치마다 길이별로 `ipaddress`를 부르면
# 긴 16진·콜론 입력에서 몇 초가 걸린다(#82). 대안은 `::` 뒤 구간이 많은 것부터 두어, 한 위치에서 처음 맞는 것이
# 가장 긴 유효 후보가 되게 한다. 10진 옥텟은 `ipaddress`처럼 앞자리 0을 받지 않는다(`0` 하나는 받는다).
H16 = "[0-9A-Fa-f]{1,4}"
DEC_OCTET = "(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9][0-9]|[0-9])"
LS32 = rf"(?:{H16}:{H16}|{DEC_OCTET}(?:\.{DEC_OCTET}){{3}})"
IPV6 = re.compile(
    "|".join(
        [
            rf"(?:{H16}:){{6}}{LS32}",
            rf"::(?:{H16}:){{5}}{LS32}",
            *(rf"(?:(?:{H16}:){{0,{hi}}}{H16})?::(?:{H16}:){{{4 - hi}}}{LS32}" for hi in range(5)),
            rf"(?:(?:{H16}:){{0,5}}{H16})?::{H16}",
            rf"(?:(?:{H16}:){{0,6}}{H16})?::",
        ]
    )
)
HOST_PORT = re.compile(rf"(?<![{WORD}.-])[A-Za-z][A-Za-z0-9.-]*:\d{{1,5}}(?![{WORD}])")
DOTTED_NAME = re.compile(rf"(?<![{WORD}.-])[A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)+(?![{WORD}-])")
FILE_NAME = re.compile(r"^(?P<stem>.+)\.(?P<ext>[A-Za-z0-9]+)$")


class FieldKind(StrEnum):
    LINK = "LINK"
    PATH = "PATH"
    TEXT = "TEXT"


@dataclass(frozen=True)
class AddressPolicy:
    patterns: tuple[re.Pattern[str], ...] = (SCHEME_URL, IP_RUN, IPV4_DIGITS, HOST_PORT, DOTTED_NAME)
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


def _mask_ipv6(value: str, ip_run: re.Pattern[str]) -> str:
    """콜론이 두 개 이상인 구간마다 왼쪽부터 가장 긴 유효 IPv6 후보를 가린다."""
    out, last = [], 0
    for match in ip_run.finditer(value):
        if match.group(0).count(":") < 2:
            continue
        pos = match.start()
        while (found := IPV6.search(value, pos, match.end())) is not None:
            out += [value[last : found.start()], ADDRESS_MASK]
            last = pos = found.end()
    return "".join(out) + value[last:]


def _mask_ipv4(value: str, ipv4_digits: re.Pattern[str]) -> str:
    def replace(match: re.Match[str]) -> str:
        token = match.group(0)
        return ADDRESS_MASK if token.count(".") == 3 and _is_ip(token) else token

    return ipv4_digits.sub(replace, value)


def _mask_scheme(value: str, scheme: re.Pattern[str]) -> str:
    """`://`마다 그 앞 스킴 문자 덩어리의 첫 글자에서 패턴을 맞춰 보고, 맞으면 덩어리 시작부터 가린다.

    덩어리는 `:`에서 끝나 서로 겹치지 않으므로 전체 시간이 길이에 비례한다.
    """
    out, last, pos = [], 0, 0
    while (colon := value.find("://", pos)) >= 0:
        start = colon
        while start > last and value[start - 1] in SCHEME_CHARS:
            start -= 1
        letter = next((i for i in range(start, colon) if value[i].isascii() and value[i].isalpha()), None)
        match = scheme.match(value, letter) if letter is not None else None
        if match is None:
            pos = colon + 1
            continue
        begin = start
        if start > 0 and value[start - 1] == ":":
            while begin < min(letter, start + 5) and value[begin].isdigit():
                begin += 1
        out += [value[last:begin], ADDRESS_MASK]
        last = pos = match.end()
    return "".join(out) + value[last:]


def _mask_definite(value: str, policy: AddressPolicy) -> str:
    """스킴 주소, IP, `host:port`처럼 글자만으로 주소가 확실한 것을 가린다."""
    scheme, ip_run, ipv4_digits, host_port, _ = policy.patterns
    value = _mask_scheme(value, scheme)
    value = _mask_ipv6(value, ip_run)
    value = _mask_ipv4(value, ipv4_digits)
    # `host:9.192.0.2.1`처럼 포트가 IPv4 앞 숫자와 붙어 있으면 포트를 가린 뒤에야 IPv4가 드러난다(#79).
    return _mask_ipv4(host_port.sub(ADDRESS_MASK, value), ipv4_digits)


def _mask_text(value: str, policy: AddressPolicy) -> str:
    dotted = policy.patterns[4]
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
