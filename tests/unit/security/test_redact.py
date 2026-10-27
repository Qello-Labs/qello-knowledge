"""필드 종류별 가림(research R-07). 주소와 토큰 형식 값은 실행 중에 만든다."""

import pytest

from qello_knowledge.domain.redact import AddressPolicy, FieldKind, OutputContext, has_unsafe, safe_text

PUBLIC = OutputContext(public_link_hosts=("github.com",), source_id_is_path=True)
OPAQUE = OutputContext(public_link_hosts=("github.com",), source_id_is_path=False)
# 확장자와 겹치는 합성 호스트 이름. md는 국가 도메인이기도 하다.
COLLIDING_HOST = "intra" + "net-qk.md"
INTERNAL_HOST = "db." + "corp" + ".internal"
TOKEN = "gh" + "p_" + "A" * 36
MASK = "[가림:address]"


def test_colliding_host_survives_only_as_a_path_file_name():
    assert safe_text(f"docs/{COLLIDING_HOST}", FieldKind.PATH, PUBLIC) == f"docs/{COLLIDING_HOST}"
    assert safe_text(COLLIDING_HOST, FieldKind.TEXT, PUBLIC) == MASK
    assert safe_text(f"https://{COLLIDING_HOST}/x", FieldKind.LINK, PUBLIC) == MASK


def test_directory_parts_are_judged_as_text():
    assert safe_text(f"{COLLIDING_HOST}/notes.md", FieldKind.PATH, PUBLIC) == f"{MASK}/notes.md"
    assert safe_text(f"{INTERNAL_HOST}/a/b.md", FieldKind.PATH, PUBLIC) == f"{MASK}/a/b.md"


def test_unknown_extension_file_name_is_masked_in_path():
    assert safe_text("docs/notes.weird", FieldKind.PATH, PUBLIC) == f"docs/{MASK}"


def test_extension_comparison_ignores_case():
    assert safe_text("docs/README.MD", FieldKind.PATH, PUBLIC) == "docs/README.MD"


def test_numeric_version_survives_in_text():
    assert safe_text("release 1.2.3 notes", FieldKind.TEXT, PUBLIC) == "release 1.2.3 notes"


@pytest.mark.parametrize(
    "value",
    [
        "http://github.com/org/repo",
        f"https://{INTERNAL_HOST}/x",
        "https://10.0.0.5/x",
        "https://github.com:8443/x",
        f"https://github.com/org/{INTERNAL_HOST}/x.md",
        f"https://github.com/org/repo?next=http://{INTERNAL_HOST}/",
    ],
)
def test_link_keeps_only_https_public_hosts(value):
    assert safe_text(value, FieldKind.LINK, PUBLIC) == MASK


def test_public_link_is_kept():
    link = "https://github.com/Qello-Labs/qello-knowledge/blob/main/README.md"
    assert safe_text(link, FieldKind.LINK, PUBLIC) == link


@pytest.mark.parametrize(
    "value",
    [f"see {INTERNAL_HOST} now", "call 10.0.0.5 later", "open localhost:8080", "ping fe80::1", "ssh://h/x"],
)
def test_text_addresses_are_masked(value):
    out = safe_text(value, FieldKind.TEXT, PUBLIC)
    assert MASK in out
    assert has_unsafe(value, FieldKind.TEXT, PUBLIC) == "address"


def test_secret_masks_the_whole_field_with_rule_name():
    assert safe_text(f"docs/{TOKEN}.md", FieldKind.PATH, PUBLIC) == "[가림:github-token]"
    assert has_unsafe(TOKEN, FieldKind.TEXT, PUBLIC) == "github-token"


def test_clean_values_are_unchanged():
    assert has_unsafe("docs/setup.md", FieldKind.PATH, PUBLIC) is None
    assert safe_text("Setup guide", FieldKind.TEXT, PUBLIC) == "Setup guide"


def test_source_id_kind_follows_context():
    # 같은 공개 호스트에서 source_id_is_path만 다르면 출력이 달라진다.
    path_kind = FieldKind.PATH if PUBLIC.source_id_is_path else FieldKind.TEXT
    opaque_kind = FieldKind.PATH if OPAQUE.source_id_is_path else FieldKind.TEXT
    assert safe_text(f"docs/{COLLIDING_HOST}", path_kind, PUBLIC) != safe_text(
        f"docs/{COLLIDING_HOST}", opaque_kind, OPAQUE
    )


# --- 구현 리뷰 반영(2026-10-20) ---


@pytest.mark.parametrize("value", ["buildbox:9", "open buildbox:65535 now"])
def test_single_digit_and_full_range_ports_are_addresses(value):
    assert has_unsafe(value, FieldKind.TEXT, PUBLIC) == "address"


@pytest.mark.parametrize(
    "value",
    [
        "https://github.com/o/r?next=db%2Eexample%2Einvalid",
        "https://github.com/o/r?next=http%3A%2F%2Fexample",
        "https://github.com/o/db%252Eexample%252Einvalid/x.md",
        "https://github.com/o/r#10%2E0%2E0%2E5",
    ],
)
def test_percent_encoded_addresses_in_public_links_are_masked(value):
    assert safe_text(value, FieldKind.LINK, PUBLIC) == MASK


def test_percent_encoded_secret_is_masked():
    encoded = TOKEN.replace("_", "%5F")
    assert has_unsafe(f"docs/{encoded}.md", FieldKind.PATH, PUBLIC) == "github-token"


@pytest.mark.parametrize("value", ["::ffff:192.0.2.1", "see ::ffff:192.0.2.1 now", "64:ff9b::10.0.0.5"])
def test_ipv6_with_embedded_ipv4_is_fully_masked(value):
    out = safe_text(value, FieldKind.TEXT, PUBLIC)
    assert "192.0" not in out and "0.2.1" not in out and "10.0" not in out and "0.5" not in out


@pytest.mark.parametrize(
    ("value", "kind"),
    [
        ("connect 2001:db8::1.", FieldKind.TEXT),
        ("docs/2001:db8::1.md", FieldKind.PATH),
        ("2001:db8::1", FieldKind.TEXT),
    ],
)
def test_ipv6_followed_by_period_or_extension_is_masked(value, kind):
    assert "2001:db8" not in safe_text(value, kind, PUBLIC)


# --- 구현 재리뷰 2차 반영: IP는 경계 정규식이 아니라 후보를 ipaddress로 검증한다 ---


@pytest.mark.parametrize(
    ("value", "kind", "leftover"),
    [
        ("Host ...2001:db8::1.", FieldKind.TEXT, "2001:db8"),
        ("docs/file.2001:db8::1.md", FieldKind.PATH, "2001:db8"),
        ("docs/file.::ffff:192.0.2.1.md", FieldKind.PATH, "192.0"),
        ("docs/file.10.0.0.5.md", FieldKind.PATH, "10.0.0.5"),
        ("see 10.0.0.5.", FieldKind.TEXT, "10.0.0.5"),
        ("[2001:db8::1]:443", FieldKind.TEXT, "2001:db8"),
    ],
)
def test_ip_addresses_next_to_dots_and_extensions_are_masked(value, kind, leftover):
    assert leftover not in safe_text(value, kind, PUBLIC)
    assert has_unsafe(value, kind, PUBLIC) == "address"


@pytest.mark.parametrize("value", ["12:30:45 회의", "release 1.2.3", "sha256:abcd", "1.2.3.456", "2026.10.20.1"])
def test_code_like_colons_and_versions_are_not_addresses(value):
    assert safe_text(value, FieldKind.TEXT, PUBLIC) == value


# --- 구현 재리뷰 3차 반영: 숫자가 든 후보는 앞뒤에 무엇이 붙든 가린다. 두 글자 `::`도 IPv6다 ---


@pytest.mark.parametrize(
    ("value", "kind", "leftover"),
    [
        ("docs/10.0.0.5_backup.md", FieldKind.PATH, "10.0.0.5"),
        ("docs/backup_2001:db8::1.md", FieldKind.PATH, "2001:db8"),
        ("docs/2001:db8::1_backup.md", FieldKind.PATH, "2001:db8"),
        ("host a2001:db8::1 here", FieldKind.TEXT, "2001:db8"),
        ("::", FieldKind.TEXT, "::"),
        ("[::]:9", FieldKind.TEXT, "::"),
    ],
)
def test_ips_glued_to_words_and_the_shortest_ipv6_are_masked(value, kind, leftover):
    assert leftover not in safe_text(value, kind, PUBLIC)
    assert has_unsafe(value, kind, PUBLIC) == "address"


# --- 구현 재리뷰 4차 반영: 코드 예외를 없애고, IPv4는 숫자 덩어리 전체가 IPv4일 때만 가린다 ---


@pytest.mark.parametrize(
    ("value", "kind", "leftover"),
    [
        ("backupbeef::cafe", FieldKind.TEXT, "beef::cafe"),
        ("face::beefx", FieldKind.TEXT, "face::beef"),
        ("docs/face::beef.md", FieldKind.PATH, "face::beef"),
        ("https://github.com/o/r?next=backupbeef::cafe", FieldKind.LINK, "beef::cafe"),
        ("std::map", FieldKind.TEXT, "d::"),
    ],
)
def test_letter_only_ipv6_is_masked_even_next_to_letters(value, kind, leftover):
    assert leftover not in safe_text(value, kind, PUBLIC)


@pytest.mark.parametrize("value", ["docs/2026.10.20.1.md", "docs/v1.2.3.456.md"])
def test_numeric_versions_in_file_names_are_not_addresses(value):
    assert has_unsafe(value, FieldKind.PATH, PUBLIC) is None


def test_long_non_address_strings_are_cheap():
    import time

    started = time.perf_counter()
    safe_text("a" * 100_000, FieldKind.TEXT, PUBLIC)
    safe_text("1" * 100_000, FieldKind.TEXT, PUBLIC)
    assert time.perf_counter() - started < 1


# --- #70: `\b`·`\w`가 한글을 단어 문자로 봐서 한글에 바로 붙은 주소를 놓쳤다 ---

SCHEME_ADDRESS = "ssh" + "://h/x"  # 점·포트가 없어 스킴 패턴만 잡는다
HOST_PORT_ADDRESS = "buildbox" + ":9"
IPV4_ADDRESS = ".".join(["192", "0", "2", "1"])
IPV6_ADDRESS = "2001:db8" + "::1"
# 점 이름 뒤에 한글이 붙으면 앞부분만 가리고 마지막 이름 조각이 남았다. 마지막 조각으로 확인한다.
LAST_LABEL = INTERNAL_HOST.rsplit(".", 1)[-1]
HANGUL_FORMS = ("주소{}", "{}입니다", "주소{}입니다", "주소 {} 입니다")
HANGUL_CASES = [
    (SCHEME_ADDRESS, FieldKind.TEXT, "{}", "ssh:"),
    (HOST_PORT_ADDRESS, FieldKind.TEXT, "{}", "buildbox"),
    (HOST_PORT_ADDRESS, FieldKind.PATH, "docs/{}/a.md", "buildbox"),
    (HOST_PORT_ADDRESS, FieldKind.PATH, "docs/{}.md", "buildbox"),
    (INTERNAL_HOST, FieldKind.TEXT, "{}", LAST_LABEL),
    (INTERNAL_HOST, FieldKind.PATH, "docs/{}/a.md", LAST_LABEL),
    (INTERNAL_HOST, FieldKind.PATH, "docs/{}", LAST_LABEL),
    (IPV4_ADDRESS, FieldKind.TEXT, "{}", IPV4_ADDRESS),
    (IPV4_ADDRESS, FieldKind.PATH, "docs/{}.md", IPV4_ADDRESS),
    (IPV6_ADDRESS, FieldKind.TEXT, "{}", IPV6_ADDRESS),
    (IPV6_ADDRESS, FieldKind.PATH, "docs/{}.md", IPV6_ADDRESS),
]


@pytest.mark.parametrize("form", HANGUL_FORMS)
@pytest.mark.parametrize(("address", "kind", "template", "leftover"), HANGUL_CASES)
def test_addresses_glued_to_hangul_are_masked(address, kind, template, leftover, form):
    value = template.format(form.format(address))
    assert leftover not in safe_text(value, kind, PUBLIC)
    assert has_unsafe(value, kind, PUBLIC) == "address"


@pytest.mark.parametrize("form", HANGUL_FORMS)
@pytest.mark.parametrize(
    ("address", "template"),
    [
        (SCHEME_ADDRESS, "https://github.com/o/r?next={}"),
        (HOST_PORT_ADDRESS, "https://github.com/o/r#{}"),
        (INTERNAL_HOST, "https://github.com/o/r?next={}"),
        (INTERNAL_HOST, "https://github.com/o/{}/x.md"),
        (IPV4_ADDRESS, "https://github.com/o/r#{}"),
    ],
)
def test_public_links_with_hangul_glued_addresses_are_masked(address, template, form):
    assert safe_text(template.format(form.format(address)), FieldKind.LINK, PUBLIC) == MASK


@pytest.mark.parametrize("form", ("住所{}", "{}です"))
@pytest.mark.parametrize(
    ("address", "leftover"), [(SCHEME_ADDRESS, "ssh:"), (HOST_PORT_ADDRESS, "buildbox"), (INTERNAL_HOST, LAST_LABEL)]
)
def test_addresses_glued_to_other_non_ascii_letters_are_masked(address, leftover, form):
    assert leftover not in safe_text(form.format(address), FieldKind.TEXT, PUBLIC)


@pytest.mark.parametrize(
    ("value", "kind", "expected"),
    [
        (f"x{SCHEME_ADDRESS}", FieldKind.TEXT, MASK),
        (f"_{SCHEME_ADDRESS}", FieldKind.TEXT, f"_{MASK}"),  # #79: 스킴 주소는 숫자·밑줄 뒤에서도 가린다
        (f"9{SCHEME_ADDRESS}", FieldKind.TEXT, MASK),  # 스킴 덩어리 앞 숫자도 함께 가린다
        (f"x{HOST_PORT_ADDRESS}", FieldKind.TEXT, MASK),
        (f"_{HOST_PORT_ADDRESS}", FieldKind.TEXT, f"_{HOST_PORT_ADDRESS}"),
        (f"9{HOST_PORT_ADDRESS}", FieldKind.TEXT, f"9{HOST_PORT_ADDRESS}"),
        (f"{HOST_PORT_ADDRESS}x", FieldKind.TEXT, f"{HOST_PORT_ADDRESS}x"),
        (f"{HOST_PORT_ADDRESS}_", FieldKind.TEXT, f"{HOST_PORT_ADDRESS}_"),
        (f"docs/{HOST_PORT_ADDRESS}x.md", FieldKind.PATH, f"docs/{HOST_PORT_ADDRESS}x.md"),
        (f"docs/_{HOST_PORT_ADDRESS}.md", FieldKind.PATH, f"docs/_{HOST_PORT_ADDRESS}.md"),
        (f"x{INTERNAL_HOST}x", FieldKind.TEXT, MASK),
        (f"docs/x{INTERNAL_HOST}.md", FieldKind.PATH, f"docs/x{INTERNAL_HOST}.md"),
        (f"9{IPV4_ADDRESS}", FieldKind.TEXT, f"9{IPV4_ADDRESS}"),
        (f"x{IPV4_ADDRESS}x", FieldKind.TEXT, f"x{MASK}x"),
        (f"x{IPV6_ADDRESS}x", FieldKind.TEXT, f"x{MASK}x"),
    ],
)
def test_ascii_neighbors_keep_the_previous_judgement(value, kind, expected):
    assert safe_text(value, kind, PUBLIC) == expected


def test_address_policy_version_changed_with_the_scheme_boundary():
    assert AddressPolicy().version == "address-v6"


# --- #79: 스킴 패턴이 긴 입력에서 길이의 제곱으로 느렸고, 숫자·밑줄·`..` 뒤의 주소가 한 번 가림에서 남았다 ---


def test_long_dotted_runs_without_a_scheme_are_cheap():
    import time

    started = time.perf_counter()
    for unit in ("a.", "a-", "a.-", "1."):
        safe_text(unit * (100_000 // len(unit)), FieldKind.TEXT, PUBLIC)
    assert time.perf_counter() - started < 1


@pytest.mark.parametrize("field_kind", list(FieldKind))
@pytest.mark.parametrize("unit", ["fffff:", "f:f.", "a.a.a.a:99999", "::", "f:", "ffff:", "1:2:3:4:5:6:7:"])
def test_long_hex_colon_runs_are_cheap(unit, field_kind):
    # 위치마다 길이별로 `ipaddress`를 부르면 10만 자에 몇 초가 걸린다(#82).
    import time

    started = time.perf_counter()
    safe_text(unit * (100_000 // len(unit)), field_kind, PUBLIC)
    assert time.perf_counter() - started < 1


# 한 위치에서는 `ipaddress`가 받는 가장 긴 IPv6 후보를 가린다(#82 전과 같은 결과).
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("1:2:3:4:5:6:7::9", f"{MASK}9"),
        ("::1:2:3:4:5:6:7:8", f"{MASK}:8"),
        ("1:2:3:4:5:6:7:8:9", f"{MASK}:9"),
        ("2001:db8::1:2:3:4:5:6", f"{MASK}:6"),
        ("2001:db8:::1", f"{MASK}:1"),
        ("fffff::1", f"f{MASK}"),
        ("::192.0.2.256", f"{MASK}6"),
        ("::ffff:192.0.2.01", f"{MASK}1"),
        ("1:2:3:4:5:6:192.0.2.1.5", f"{MASK}.5"),
        ("std::map::f", f"st{MASK}map{MASK}"),
    ],
)
def test_ipv6_masks_the_longest_valid_candidate(value, expected):
    assert safe_text(value, FieldKind.TEXT, PUBLIC) == expected
    assert safe_text(value, FieldKind.PATH, PUBLIC) == expected


@pytest.mark.parametrize(
    ("value", "leftover"),
    [
        (f"{IPV4_ADDRESS}{SCHEME_ADDRESS}", "ssh:"),
        (f"{IPV4_ADDRESS}{SCHEME_ADDRESS}", IPV4_ADDRESS),
        (f"_{SCHEME_ADDRESS}", "ssh:"),
        (f"9{SCHEME_ADDRESS}", "ssh:"),
        (f"1.2.{SCHEME_ADDRESS}", "ssh:"),
        (f"v1.2..{IPV4_ADDRESS}_x", IPV4_ADDRESS),
        (f"1.2..{IPV4_ADDRESS}", IPV4_ADDRESS),
    ],
)
def test_addresses_after_digits_underscores_and_double_dots_are_masked(value, leftover):
    assert leftover not in safe_text(value, FieldKind.TEXT, PUBLIC)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (f"1.{IPV4_ADDRESS}{SCHEME_ADDRESS}", MASK),
        (f"9{IPV4_ADDRESS}{SCHEME_ADDRESS}", MASK),
        (f"_{SCHEME_ADDRESS}", f"_{MASK}"),
        (f"x {SCHEME_ADDRESS}", f"x {MASK}"),
        (f"{HOST_PORT_ADDRESS}.md+{SCHEME_ADDRESS}", f"{MASK}{MASK}"),  # 포트 숫자는 `host:port`가 가린다
    ],
)
def test_digits_and_dots_before_a_scheme_are_masked_with_it(value, expected):
    assert safe_text(value, FieldKind.TEXT, PUBLIC) == expected


def test_only_port_digits_after_a_colon_are_left_before_a_scheme():
    masked = safe_text(f":80{IPV4_ADDRESS}{SCHEME_ADDRESS}", FieldKind.TEXT, PUBLIC)
    assert masked.endswith(MASK)
    assert IPV4_ADDRESS not in masked
    assert "." not in masked.removesuffix(MASK)


@pytest.mark.parametrize("kind", [FieldKind.TEXT, FieldKind.PATH])
def test_ipv4_after_a_masked_port_is_masked(kind):
    value = (
        f"docs/{HOST_PORT_ADDRESS}.{IPV4_ADDRESS}" if kind == FieldKind.PATH else f"{HOST_PORT_ADDRESS}.{IPV4_ADDRESS}"
    )
    assert IPV4_ADDRESS not in safe_text(value, kind, PUBLIC)


@pytest.mark.parametrize(
    ("value", "kind"),
    [
        (f"v1.2..{IPV4_ADDRESS}", FieldKind.TEXT),
        (f"docs/v1.2..{IPV4_ADDRESS}/a.md", FieldKind.PATH),
        (f"docs/v1.2..{IPV4_ADDRESS}.md", FieldKind.PATH),
    ],
)
def test_ipv4_after_double_dots_counts_as_an_address(value, kind):
    assert IPV4_ADDRESS not in safe_text(value, kind, PUBLIC)
    assert has_unsafe(value, kind, PUBLIC) == "address"


@pytest.mark.parametrize(
    "value",
    ["release 1.2.3.4.5", "1.2.3.456", "2026.10.20.1", "x9://", "a_b://", f"_{HOST_PORT_ADDRESS}", "9://"],
)
def test_versions_and_schemes_without_a_host_are_kept(value):
    assert safe_text(value, FieldKind.TEXT, PUBLIC) == value


IDEMPOTENT_PARTS = (
    SCHEME_ADDRESS, IPV4_ADDRESS, IPV6_ADDRESS, HOST_PORT_ADDRESS, INTERNAL_HOST, COLLIDING_HOST,
    "v1.2", "..", ".", "_", "9", "-", "/", " ", "주소", "://", ":1", "x", ".md",
)  # fmt: skip


def _glued_inputs(max_parts: int) -> list[str]:
    from itertools import product

    return ["".join(parts) for n in range(1, max_parts + 1) for parts in product(IDEMPOTENT_PARTS, repeat=n)]


@pytest.mark.parametrize("kind", list(FieldKind))
def test_masking_twice_gives_the_same_result(kind):
    once = {v: safe_text(v, kind, PUBLIC) for v in _glued_inputs(3)}
    assert [v for v, masked in once.items() if safe_text(masked, kind, PUBLIC) != masked] == []
