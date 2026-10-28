"""QK-ING-003 공통 형식 확장(data-model 5절). 새 필드는 기본값일 때 지금 동작과 같다."""

from types import MappingProxyType

import pytest

from qello_knowledge.domain.source import (
    AccessInfo,
    AccessStatus,
    ChangeKeyKind,
    ContentFormat,
    ConversionWarning,
    ConversionWarningKind,
    ListPage,
    MissingCheck,
    SourceContent,
    SourceItem,
)
from qello_knowledge.domain.source_config import SourceConfig, SourceScope
from qello_knowledge.sources.collect import list_all


def _item(**changes):
    values = dict(
        source_name="docs",
        source_kind="fake",
        source_id="a",
        url="https://fake.invalid/a",
        change_key="v1",
        change_key_kind=ChangeKeyKind.VERSION,
        version="v1",
        modified_at=None,
        item_type="markdown_file",
        title=None,
        location="a.md",
        size_bytes=None,
        access=AccessInfo(AccessStatus.UNKNOWN),
        origin_state=None,
    )
    return SourceItem(**(values | changes))


def test_new_fields_default_to_current_behaviour():
    positional = SourceItem(
        "docs", "fake", "a", "https://fake.invalid/a", "v1", ChangeKeyKind.VERSION, "v1", None, "f", None, "a.md", None,
        AccessInfo(AccessStatus.UNKNOWN), None,
    )  # fmt: skip
    assert positional.exclusion is None
    content = SourceContent("a", "# t\n", ContentFormat.MARKDOWN, "v1", "a.md", None)
    assert content.locator_extra is None
    assert content.fingerprint_extra is None
    assert content.conversion_warnings == ()
    assert ListPage((), None).incomplete_reason is None


def test_locator_extra_is_read_only():
    content = SourceContent(
        "a", "", ContentFormat.MARKDOWN, None, "a.md", None, locator_extra={"confluence": {"page_id": "1"}}
    )
    assert isinstance(content.locator_extra, MappingProxyType)
    with pytest.raises(TypeError):
        content.locator_extra["other"] = 1  # type: ignore[index]


def test_conversion_warning_kinds_are_fixed():
    assert {kind.value for kind in ConversionWarningKind} == {
        "UNSUPPORTED_BLOCK",
        "TABLE_FLATTENED",
        "MEETING_METADATA_MISSING",
        "NOT_GLOSSARY",
    }
    assert ConversionWarning("TABLE_FLATTENED", 3) == ConversionWarning(ConversionWarningKind.TABLE_FLATTENED, 3)
    with pytest.raises(ValueError):
        ConversionWarning("SOMETHING_ELSE", 0)
    with pytest.raises(ValueError):
        ConversionWarning(ConversionWarningKind.NOT_GLOSSARY, -1)


def test_missing_check_values():
    assert {value.value for value in MissingCheck} == {"GONE", "ARCHIVED", "PRESENT", "UNCERTAIN"}


def test_exclusion_is_kept():
    assert _item(exclusion="unclassified").exclusion == "unclassified"


class _IncompleteAdapter:
    kind = "fake"

    def list_page(self, session, config, cursor):
        return ListPage((_item(),), None, complete=False, incomplete_reason="space_id_mismatch")


def test_list_all_carries_incomplete_reason():
    config = SourceConfig("docs", "fake", True, scope=SourceScope(("**",)), allowed_hosts=("fake.invalid",))
    listing = list_all(_IncompleteAdapter(), config, session=None)
    assert listing.complete is False
    assert listing.incomplete_reason == "space_id_mismatch"
    assert [item.source_id for item in listing.items] == ["a"]
