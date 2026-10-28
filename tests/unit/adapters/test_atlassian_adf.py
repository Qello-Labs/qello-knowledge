"""ADF → Markdown 변환(QK-ING-003 contracts/adf-markdown.md, SC-003·SC-005·SC-012). 기대값은 사람이 쓴 픽스처다."""

import json
from pathlib import Path

import pytest

from qello_knowledge.adapters.atlassian_adf import RULES_VERSION, convert_adf

ROOT = Path("tests/fixtures/confluence/adf")
CASES = sorted(p.stem for p in ROOT.glob("*.json") if not p.name.endswith(".warnings.json"))


def _convert(case):
    data = json.loads((ROOT / f"{case}.json").read_text(encoding="utf-8"))
    return convert_adf(
        data["doc"],
        title=data["title"],
        site_host="site.invalid",
        public_link_hosts=("github.com",),
        doc_type=data["doc_type"],
    )


def test_cases_are_present():
    assert len(CASES) == 19


@pytest.mark.parametrize("case", CASES)
def test_case_matches_expected_markdown_and_warnings(case):
    result = _convert(case)
    expected = json.loads((ROOT / f"{case}.warnings.json").read_text(encoding="utf-8"))
    assert result.markdown == (ROOT / f"{case}.md").read_text(encoding="utf-8")
    assert [[w.kind.value, w.block] for w in result.warnings] == expected["warnings"]
    meeting = None if result.meeting is None else {
        "date": result.meeting.date, "kind": result.meeting.kind, "spec_ids": list(result.meeting.spec_ids)
    }  # fmt: skip
    assert meeting == expected["meeting"]
    assert result.rules_version == RULES_VERSION == "adf-md-v1"


@pytest.mark.parametrize("case", CASES)
def test_conversion_is_byte_identical_twice(case):
    assert _convert(case) == _convert(case)


@pytest.mark.parametrize("case", CASES)
def test_account_ids_and_mail_addresses_never_appear(case):
    markdown = _convert(case).markdown
    assert "acct-000" not in markdown
    assert "someone@" not in markdown and "mailto:" not in markdown


def test_warnings_carry_no_text():
    result = _convert("unknown_macro")
    assert all(set(vars(w)) == {"kind", "block"} for w in result.warnings)


@pytest.mark.parametrize("doc", [{"type": "paragraph"}, [], None, {"type": "doc", "content": "x"}])
def test_invalid_document_raises(doc):
    with pytest.raises(ValueError):
        convert_adf(doc, title="t", site_host="site.invalid", public_link_hosts=(), doc_type=None)
