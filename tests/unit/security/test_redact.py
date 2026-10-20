"""필드 종류별 가림(research R-07). 주소와 토큰 형식 값은 실행 중에 만든다."""

import pytest

from qello_knowledge.domain.redact import FieldKind, OutputContext, has_unsafe, safe_text

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
