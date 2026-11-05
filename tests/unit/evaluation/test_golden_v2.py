"""골든 세트 v2가 v1을 그대로 담고 골든셋 v0 문항을 더했는지(QK-EVL-001 tasks T046·T047).

v0 원본은 저장소에 없으므로 더한 문항의 문장 대조는 사람이 한다(H09). 세트 파일을 읽으므로 세트와 같은 커밋에 둔다.
"""

from __future__ import annotations

from pathlib import Path

from qello_knowledge.evaluation.question_set import LabelStatus, QuestionOrigin, QuestionType, check_question_set

ROOT = Path(__file__).resolve().parents[3]
GOLDEN = ROOT / "eval" / "question_sets" / "qk-evl-001-golden"
V1_IDS = tuple(f"Q{n:02d}" for n in range(1, 12))
V0_EVIDENCE = (
    "qmv26kb2qzu4q",
    "qmv26yx2nf6zx",
    "qmv3nxemzw984",
    "qmvap800bkpxt",
    "qmvapdxvo621o",
    "qmvb1yugb6wda",
    "qmvcgtyx83h8s",
    "cand-S11",
    "cand-S13",
    "cand-S17",
    "cand-S25",
    "cand-S31",
    "cand-S39",
    "cand-S47",
    "cand-S54",
)
V0_NO_ANSWER = ("qmv272r8raqgk", "qmvap6omullmy", "cand-S70", "cand-S74", "cand-S77", "cand-S78")


def test_golden_v2_keeps_v1_and_adds_v0_questions() -> None:
    v1, v1_check = check_question_set(GOLDEN / "v1.toml")
    v2, v2_check = check_question_set(GOLDEN / "v2.toml")
    assert v1_check.ok, v1_check.issues
    assert v2_check.ok, v2_check.issues
    assert v1 is not None and v2 is not None
    assert v2.id == "qk-evl-001-golden" and v2.version == 2
    assert v2.label_commits == v1.label_commits == {"dnd-backend-docs": "6aeccd039b825dcd7a2b6c046a34ef72089a1f78"}
    assert v2.origin_set is None
    assert v2.labeling == "eval/question_sets/qk-evl-001-golden/labeling-v2.md"
    assert (ROOT / v2.labeling).is_file()

    assert tuple(q.id for q in v2.questions) == V1_IDS + V0_EVIDENCE + V0_NO_ANSWER
    assert v2.questions[: len(V1_IDS)] == v1.questions

    for question in v2.questions[len(V1_IDS) :]:
        assert question.original_number == question.id
        assert question.label is LabelStatus.DONE and question.origin is QuestionOrigin.TEAM
        assert question.query_form is None and question.label_terms == ()
        assert question.facts
        assert {e.source for e in question.evidence} <= {"dnd-backend-docs"}
        if question.id in V0_NO_ANSWER:
            assert question.type is QuestionType.NO_ANSWER and question.evidence == ()
        else:
            assert question.type is not QuestionType.NO_ANSWER and question.evidence

    assert sum(q.is_metric_target for q in v2.questions) == 23
