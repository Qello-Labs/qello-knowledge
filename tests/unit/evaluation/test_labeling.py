"""식별자 세트 만들기 도우미(QK-EVL-001 research R-13, spec US2-3·US2-4, tasks T013). 외부 호출과 DB가 없다."""

from __future__ import annotations

from pathlib import Path

import pytest

from qello_knowledge.evaluation.labeling import form_of, identifier_candidates, recompute_evidence, split_words
from qello_knowledge.evaluation.question_set import IdentifierForm, check_question_set
from tests.unit.evaluation.fakes import IDENTIFIERS, SOURCE, question_set_file
from tests.unit.synthetic_secrets import SYNTHETIC

CHUNKS = [
    (SOURCE, "docs/A.md", "결제는 `retryPayment`가 맡고 `RetryPolicy`와 `HTTPClient`를 쓴다."),
    (SOURCE, "docs/A.md", "토큰은 `oauth2Token`이다. 설정 `max_retries`, 규칙 `kw-index-baseline-v1`."),
    (SOURCE, "docs/B.md", "금요일에는 배포하지 않는다. 경로 `/api/v1/users`, 다시 `retryPayment`."),
    (SOURCE, "docs/C.md", "외부 주소 https://host.invalid/hidden/path 는 경로 후보가 아니다. 배포 금요일 retrypayment"),
]


@pytest.mark.parametrize(
    ("token", "form"),
    [
        ("retryPayment", IdentifierForm.CAMEL),
        ("RetryPolicy", IdentifierForm.PASCAL),
        ("HTTPClient", IdentifierForm.ACRONYM),
        ("oauth2Token", IdentifierForm.DIGIT),
        ("max_retries", IdentifierForm.SNAKE),
        ("kw-index-baseline-v1", IdentifierForm.KEBAB),
        ("/api/v1/users", IdentifierForm.URL_PATH),
        ("payment", None),
        ("Payment", None),
        ("2026-10-31", None),
    ],
)
def test_form_of(token: str, form: IdentifierForm | None) -> None:
    assert form_of(token) is form


def test_split_words() -> None:
    assert split_words("retryPayment") == ("retry", "payment")
    assert split_words("HTTPClient") == ("http", "client")
    assert split_words("oauth2Token") == ("oauth", "token")
    assert split_words("max_retries") == ("max", "retries")
    assert split_words("kw-index-baseline-v1") == ("kw", "index", "baseline", "v1")
    assert split_words("/api/v1/users") == ("api", "v1", "users")


def test_candidates_by_form_with_documents() -> None:
    report = identifier_candidates(CHUNKS)
    found = {(c.form, c.identifier): c.documents for c in report.candidates}
    assert found[(IdentifierForm.CAMEL, "retryPayment")] == ((SOURCE, "docs/A.md"), (SOURCE, "docs/B.md"))
    assert found[(IdentifierForm.PASCAL, "RetryPolicy")] == ((SOURCE, "docs/A.md"),)
    assert found[(IdentifierForm.URL_PATH, "/api/v1/users")] == ((SOURCE, "docs/B.md"),)
    assert all(c.identifier != "/hidden/path" for c in report.candidates)  # 호스트가 붙은 경로는 후보가 아니다
    camel = next(c for c in report.candidates if c.identifier == "retryPayment")
    assert dict(camel.word_documents) == {"retry": 3, "payment": 3}  # 대소문자 무시, 문서 단위


def test_form_filter() -> None:
    report = identifier_candidates(CHUNKS, forms=(IdentifierForm.SNAKE,))
    assert [c.identifier for c in report.candidates] == ["max_retries"]


def test_secret_candidates_are_dropped_and_counted() -> None:
    secret = SYNTHETIC["github-classic"]  # `_`가 있어 snake_case 후보 꼴이다
    report = identifier_candidates([*CHUNKS, (SOURCE, "docs/D.md", f"키 {secret} 를 쓴다")])
    assert all(secret not in c.identifier for c in report.candidates)
    assert report.secret_excluded == 1
    assert secret not in repr(report)


def test_recompute_evidence_matches_file(tmp_path: Path) -> None:
    question_set, _ = check_question_set(
        question_set_file(tmp_path, "fixture-identifiers", 1, IDENTIFIERS.read_text(encoding="utf-8"))
    )
    assert question_set is not None
    chunks = [
        (SOURCE, "docs/A.md", "`retryPayment` 함수"),
        (SOURCE, "docs/B.md", "금요일에는"),
        (SOURCE, "docs/B.md", "배포하지 않는다"),  # 문장형은 한 문서의 청크를 합쳐 본다
        (SOURCE, "docs/C.md", "RETRYPAYMENT 금요일"),  # 원형·일부는 대소문자를 가린다
    ]
    assert recompute_evidence(question_set, chunks) == ()
    diffs = recompute_evidence(question_set, [*chunks, (SOURCE, "docs/E.md", "`retryPayment` 다시")])
    assert {(d.question_id, d.missing, d.extra) for d in diffs} == {
        ("camel-01-original", ((SOURCE, "docs/E.md"),), ()),
        ("camel-01-partial", ((SOURCE, "docs/E.md"),), ()),
    }
    diffs = recompute_evidence(question_set, chunks[:1])
    assert {(d.question_id, d.missing, d.extra) for d in diffs} == {("sentence-01", (), ((SOURCE, "docs/B.md"),))}
    for diff in diffs:
        assert "금요일" not in repr(diff)
