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
