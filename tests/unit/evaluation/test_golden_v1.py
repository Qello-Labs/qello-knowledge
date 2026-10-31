"""골든 세트 v1이 H05 v2와 같은지(QK-EVL-001 spec FR-008, SC-002, tasks T017).

세트 파일을 읽으므로 세트와 같은 커밋에 둔다(research R-14).
"""

from __future__ import annotations

import re
from pathlib import Path

from qello_knowledge.evaluation.question_set import LabelStatus, QuestionOrigin, QuestionType, check_question_set

ROOT = Path(__file__).resolve().parents[3]
H05_V2 = ROOT / "specs" / "QK-BOT-001-discord-ask" / "measurement" / "h05-question-set-v2.md"
GOLDEN = ROOT / "eval" / "question_sets" / "qk-evl-001-golden" / "v1.toml"
TYPES = {"있음": QuestionType.DOC, "없음": QuestionType.NO_ANSWER}


def _h05_rows() -> list[tuple[str, str, str, tuple[str, ...], str]]:
    rows = []
    for line in H05_V2.read_text(encoding="utf-8").splitlines():
        if not re.match(r"^\| Q\d\d \|", line):
            continue
        number, kind, _private, text, evidence, facts = (c.strip() for c in line.strip().strip("|").split("|"))
        paths = () if evidence == "—" else tuple(re.findall(r"`([^`]+)`", evidence))
        rows.append((number, kind, text, paths, facts))
    return rows


def test_golden_v1_matches_h05_v2() -> None:
    rows = _h05_rows()
    assert len(rows) == 11
    question_set, check = check_question_set(GOLDEN)
    assert check.ok, check.issues
    assert question_set is not None
    assert question_set.id == "qk-evl-001-golden" and question_set.version == 1
    assert question_set.label_commits == {"dnd-backend-docs": "6aeccd039b825dcd7a2b6c046a34ef72089a1f78"}
    origin = question_set.origin_set
    assert origin is not None and (origin.id, origin.version) == ("qk-bot-001-h05", 2)
    assert origin.document == H05_V2.relative_to(ROOT).as_posix()
    assert len(question_set.questions) == len(rows)
    for question, (number, kind, text, paths, facts) in zip(question_set.questions, rows, strict=True):
        assert question.id == number and question.original_number == number
        assert question.text == text
        assert question.facts == facts
        assert question.type is TYPES[kind]
        assert tuple(e.location for e in question.evidence) == paths
        assert {e.source for e in question.evidence} <= {"dnd-backend-docs"}
        assert question.label is LabelStatus.DONE and question.origin is QuestionOrigin.SYNTHETIC
        assert question.query_form is None and question.label_terms == ()
    assert sum(q.is_metric_target for q in question_set.questions) == 8
