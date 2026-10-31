"""질문 세트 형식 검증(QK-EVL-001 spec FR-001~FR-006, SC-001, contracts/question-set.md, tasks T008).

규칙마다 그 규칙 하나만 어긴 파일을 만든다. 올바른 합성 세트 두 개(골든형·식별자형)를 고쳐서 만든다.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from pathlib import Path

import pytest

from qello_knowledge.evaluation.question_set import (
    RULES,
    LabelStatus,
    QuestionType,
    check_question_set,
)
from tests.unit.evaluation.fakes import GOLDEN, IDENTIFIERS, question_set_file
from tests.unit.synthetic_secrets import SYNTHETIC

SECRET = SYNTHETIC["github-classic"]
GOLDEN_TEXT = GOLDEN.read_text(encoding="utf-8")
IDENT_TEXT = IDENTIFIERS.read_text(encoding="utf-8")


def _replace(text: str, old: str, new: str) -> str:
    assert text.count(old) == 1, old
    return text.replace(old, new)


def _golden(old: str, new: str) -> Callable[[Path], Path]:
    return lambda root: question_set_file(root, "fixture-golden", 1, _replace(GOLDEN_TEXT, old, new))


def _ident(old: str, new: str) -> Callable[[Path], Path]:
    return lambda root: question_set_file(root, "fixture-identifiers", 1, _replace(IDENT_TEXT, old, new))


G01_EVIDENCE = 'facts = "두 번까지 다시 시도한다"\nevidence = [{ source = "dnd-backend-docs", location = "docs/A.md" }]'
G03_EVIDENCE = 'facts = "자료에 없다"\nevidence = []'
SOURCE_BLOCK = '[[set.sources]]\nname = "dnd-backend-docs"\nlabel_commit = "0000000000000000000000000000000000000001"\n'

# 규칙 이름 → 그 규칙 하나만 어긴 파일을 만드는 함수. contracts/question-set.md 4절 표와 같아야 한다.
VIOLATIONS: dict[str, Callable[[Path], Path]] = {
    "toml_invalid": _golden("version = 1\n", "version = 1\nversion = 1\n"),
    "unknown_field": _golden("version = 1\n", 'version = 1\nowner = "someone"\n'),
    "required_missing": _golden("created = 2026-10-31\n", ""),
    "bad_format": _golden("version = 1\n", 'version = "1"\n'),
    "set_path_mismatch": lambda root: question_set_file(root, "fixture-golden", 2, GOLDEN_TEXT),
    "confirmed_date": _golden("confirmed = false\n", "confirmed = true\n"),
    "source_duplicate": _golden(SOURCE_BLOCK, SOURCE_BLOCK + "\n" + SOURCE_BLOCK),
    "question_id_duplicate": _golden('id = "g04"', 'id = "g01"'),
    "bad_enum": _golden('type = "no_answer"', 'type = "unknown"'),
    "text_empty": _golden('text = "다음 회식은 어디서 해?"', 'text = "   "'),
    "text_too_long": _golden('text = "다음 회식은 어디서 해?"', 'text = "' + "가" * 2001 + '"'),
    "text_secret": _golden('text = "다음 회식은 어디서 해?"', f'text = "토큰 {SECRET} 은 어디에 둬?"'),
    "evidence_unknown_source": _golden(
        'location = "docs/A.md"', 'location = "docs/A.md" }, { source = "other-docs", location = "docs/C.md"'
    ),
    "evidence_bad_location": _golden('location = "docs/A.md"', 'location = "/docs/A.md"'),
    "evidence_duplicate": _golden(
        'location = "docs/A.md" }]',
        'location = "docs/A.md" }, { source = "dnd-backend-docs", location = "docs/A.md" }]',
    ),
    "evidence_required": _golden(G01_EVIDENCE, 'facts = "두 번까지 다시 시도한다"\nevidence = []'),
    "evidence_forbidden": _golden(
        G03_EVIDENCE, 'facts = "자료에 없다"\nevidence = [{ source = "dnd-backend-docs", location = "docs/B.md" }]'
    ),
    "form_mixed": _golden(
        G01_EVIDENCE, G01_EVIDENCE + '\nquery_form = "original"\nidentifier_form = "camel"\nlabel_terms = ["fooBar"]'
    ),
    "form_fields": _ident('query_form = "original"\nidentifier_form = "camel"\n', 'query_form = "original"\n'),
}


def test_every_rule_has_a_single_violation_case() -> None:
    assert set(VIOLATIONS) == set(RULES)
    assert len(RULES) == 19


@pytest.mark.parametrize("rule", sorted(VIOLATIONS))
def test_single_violation_is_rejected_by_that_rule_only(tmp_path: Path, rule: str) -> None:
    question_set, check = check_question_set(VIOLATIONS[rule](tmp_path))
    assert question_set is None and not check.ok
    assert {issue.rule for issue in check.issues} == {rule}, check.issues


@pytest.mark.parametrize("source", [GOLDEN, IDENTIFIERS])
def test_valid_sets_pass_with_counts(tmp_path: Path, source: Path) -> None:
    path = question_set_file(tmp_path, source.parent.name, 1, source.read_text(encoding="utf-8"))
    question_set, check = check_question_set(path)
    assert check.ok and check.issues == () and question_set is not None
    assert question_set.fingerprint == hashlib.sha256(path.read_bytes()).hexdigest()
    assert len(question_set.fingerprint) == 64


def test_golden_counts(tmp_path: Path) -> None:
    question_set, check = check_question_set(question_set_file(tmp_path, "fixture-golden", 1, GOLDEN_TEXT))
    assert check.counts.questions == 4
    assert check.counts.by_type == {QuestionType.DOC: 3, QuestionType.NO_ANSWER: 1}
    assert check.counts.by_label == {LabelStatus.DONE: 3, LabelStatus.PENDING: 1}
    assert check.counts.pending == 1
    assert question_set is not None
    assert [q.is_metric_target for q in question_set.questions] == [True, True, False, False]
    assert question_set.label_commits == {"dnd-backend-docs": "0" * 39 + "1"}
    assert not question_set.is_identifier_set


def test_all_errors_are_collected_at_once(tmp_path: Path) -> None:
    text = _replace(GOLDEN_TEXT, 'id = "g04"', 'id = "g01"')
    text = _replace(text, 'type = "no_answer"', 'type = "unknown"')
    text = _replace(text, "created = 2026-10-31\n", "")
    _, check = check_question_set(question_set_file(tmp_path, "fixture-golden", 1, text))
    assert {(i.question_id, i.field, i.rule) for i in check.issues} == {
        (None, "set.created", "required_missing"),
        ("g01", "id", "question_id_duplicate"),
        ("g03", "type", "bad_enum"),
    }


def test_confirmed_on_without_confirmation_is_confirmed_date(tmp_path: Path) -> None:
    text = _replace(GOLDEN_TEXT, "confirmed = false\n", "confirmed = false\nconfirmed_on = 2026-10-31\n")
    _, check = check_question_set(question_set_file(tmp_path, "fixture-golden", 1, text))
    assert [i.rule for i in check.issues] == ["confirmed_date"]


def test_text_length_limit_is_after_strip(tmp_path: Path) -> None:
    text = _replace(GOLDEN_TEXT, 'text = "다음 회식은 어디서 해?"', 'text = "  ' + "가" * 2000 + '  "')
    assert check_question_set(question_set_file(tmp_path, "fixture-golden", 1, text))[1].ok


@pytest.mark.parametrize("location", ["", "https://host/docs/A.md", "docs\\\\A.md", "docs/../A.md", ".."])
def test_bad_locations(tmp_path: Path, location: str) -> None:
    text = _replace(GOLDEN_TEXT, 'location = "docs/A.md"', f'location = "{location}"')
    _, check = check_question_set(question_set_file(tmp_path, "fixture-golden", 1, text))
    assert [i.rule for i in check.issues] == ["evidence_bad_location"]


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ('label_terms = ["금요일", "배포"]\n', ""),  # 문장형인데 낱말 없음
        ('label_terms = ["금요일", "배포"]', 'label_terms = ["금요일"]\nidentifier_form = "kebab"'),  # 문장형에 형태
        (
            'text = "payment"\ntype = "code"\nlabel = "done"\norigin = "synthetic"\nquery_form = "partial"\n'
            'identifier_form = "camel"\nlabel_terms = ["retryPayment"]',
            'text = "payment"\ntype = "code"\nlabel = "done"\norigin = "synthetic"\nquery_form = "partial"\n'
            'identifier_form = "camel"\nlabel_terms = ["retryPayment", "payment"]',
        ),  # 일부 질문은 원형 하나
    ],
)
def test_form_field_rules(tmp_path: Path, old: str, new: str) -> None:
    _, check = check_question_set(question_set_file(tmp_path, "fixture-identifiers", 1, _replace(IDENT_TEXT, old, new)))
    assert [i.rule for i in check.issues] == ["form_fields"]


def test_outputs_do_not_contain_text_facts_terms_or_secret(tmp_path: Path) -> None:
    text = _replace(GOLDEN_TEXT, 'text = "다음 회식은 어디서 해?"', f'text = "토큰 {SECRET} 은 어디에 둬?"')
    _, check = check_question_set(question_set_file(tmp_path, "fixture-golden", 1, text))
    rendered = repr(check) + repr(check.to_dict())
    assert SECRET not in rendered and "어디에 둬" not in rendered
    question_set, ok = check_question_set(question_set_file(tmp_path, "fixture-identifiers", 1, IDENT_TEXT))
    assert question_set is not None
    rendered = repr(question_set) + repr(ok.to_dict()) + "".join(repr(q) for q in question_set.questions)
    for question in question_set.questions:
        assert question.text not in rendered
        for term in question.label_terms:
            assert term not in rendered
    golden, _ = check_question_set(question_set_file(tmp_path, "fixture-golden", 1, GOLDEN_TEXT))
    assert golden is not None
    assert "두 번까지" not in repr(golden) + "".join(repr(q) for q in golden.questions)


def test_unreadable_file_is_toml_invalid(tmp_path: Path) -> None:
    path = tmp_path / "fixture-golden" / "v1.toml"
    path.parent.mkdir()
    path.write_bytes(b"\xff\xfe[set]")
    assert [i.rule for i in check_question_set(path)[1].issues] == ["toml_invalid"]


@pytest.mark.parametrize(
    ("old", "new", "rule"),
    [
        ('label_commit = "0000000000000000000000000000000000000001"', 'label_commit = "abc"', "bad_format"),
        (SOURCE_BLOCK, "", "required_missing"),
    ],
)
def test_bad_source_header_does_not_cascade_to_evidence(tmp_path: Path, old: str, new: str, rule: str) -> None:
    _, check = check_question_set(question_set_file(tmp_path, "fixture-golden", 1, _replace(GOLDEN_TEXT, old, new)))
    assert [i.rule for i in check.issues] == [rule]


def test_label_terms_wrong_type_is_bad_format_only(tmp_path: Path) -> None:
    text = _replace(IDENT_TEXT, 'label_terms = ["금요일", "배포"]', 'label_terms = "금요일"')
    _, check = check_question_set(question_set_file(tmp_path, "fixture-identifiers", 1, text))
    assert [i.rule for i in check.issues] == ["bad_format"]
