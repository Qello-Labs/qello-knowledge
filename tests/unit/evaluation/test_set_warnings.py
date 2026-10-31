"""평가 대상 지정 경고(QK-EVL-001 spec US1-7, FR-007, contracts/question-set.md 5절, tasks T009)."""

from __future__ import annotations

from pathlib import Path

from qello_knowledge.evaluation.question_set import check_question_set
from tests.unit.evaluation.fakes import GOLDEN, document, question_set_file

TEXT = GOLDEN.read_text(encoding="utf-8")


def _check(tmp_path: Path, text: str, docs):
    return check_question_set(question_set_file(tmp_path, "fixture-golden", 1, text), documents=docs)[1]


def test_unindexed_and_partly_unindexed_are_warnings(tmp_path: Path) -> None:
    text = TEXT.replace(
        'location = "docs/A.md" }]',
        'location = "docs/A.md" }, { source = "dnd-backend-docs", location = "docs/Z.md" }]',
    )
    check = _check(tmp_path, text, [document("docs/A.md")])
    assert check.ok
    assert {(w.question_id, w.rule, w.locations) for w in check.warnings} == {
        ("g01", "evidence_partly_unindexed", ("docs/Z.md",)),
        ("g02", "evidence_unindexed", ("docs/B.md",)),
        ("g04", "evidence_unindexed", ("docs/B.md",)),
    }


def test_all_indexed_has_no_warnings_and_no_answer_is_skipped(tmp_path: Path) -> None:
    check = _check(tmp_path, TEXT, [document("docs/A.md"), document("docs/B.md")])
    assert check.ok and check.warnings == ()


def test_without_documents_there_are_no_warnings(tmp_path: Path) -> None:
    check = check_question_set(question_set_file(tmp_path, "fixture-golden", 1, TEXT))[1]
    assert check.warnings == ()


def test_other_source_documents_do_not_count(tmp_path: Path) -> None:
    check = _check(tmp_path, TEXT, [document("docs/A.md", source="other"), document("docs/B.md")])
    assert {w.question_id for w in check.warnings} == {"g01"}
