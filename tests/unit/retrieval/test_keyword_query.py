"""질의 쪽 키워드 규칙(research R-03 결정 1, spec FR-017, tasks T016)."""

from __future__ import annotations

import pytest

from qello_knowledge.retrieval import keyword_query

V1 = "kw-query-v1"
RAW = "kw-query-raw"


@pytest.mark.parametrize(
    ("question", "terms"),
    [
        ("결제 취소 API 경로가 뭐야?", ("결제", "취소", "API", "경로")),
        ("`retryPayment` 는 어디서 부르나요?", ("retryPayment", "어디서", "부르나요")),
        ("“배포” (금요일) [규칙] <안내> '권한'!", ("배포", "금요일", "규칙", "안내", "권한")),
        ("회의록에서 결정을 알려줘", ("회의록", "결정")),
        ("집에서 일할 때", ("집에서", "일할")),
        ("경로가 경로를 경로", ("경로",)),
        ("커피 OR 차 OR 결제", ("커피", "or", "결제")),
        ("OR", ("or",)),
        ("API api Api", ("API",)),
        ("가 나 결제", ("결제",)),
        ("무엇 어디 어떻게 있나요 뭔가요", ()),
        ("   ", ()),
        ("", ()),
    ],
)
def test_v1_terms(question: str, terms: tuple[str, ...]) -> None:
    assert keyword_query(question, V1) == terms


def test_v1_drops_long_terms_and_keeps_16() -> None:
    long_term = "나" * 65  # 조사로 끝나지 않는 65자
    words = " ".join(f"용어{i:02d}번" for i in range(20))
    assert keyword_query(f"{long_term} 결제", V1) == ("결제",)
    terms = keyword_query(words, V1)
    assert len(terms) == 16 and terms[0] == "용어00번" and terms[-1] == "용어15번"


def test_v1_keeps_identifiers_whole() -> None:
    assert keyword_query("/payments/{id}/cancel max_retry_count", V1) == ("/payments/{id}/cancel", "max_retry_count")


def test_raw_is_whole_question_with_or_lowered() -> None:
    assert keyword_query("결제 취소 API 경로가 뭐야?", RAW) == ("결제 취소 API 경로가 뭐야?",)
    assert keyword_query("커피 OR 차", RAW) == ("커피 or 차",)
    assert keyword_query("   ", RAW) == ()


def test_unknown_rule() -> None:
    with pytest.raises(ValueError):
        keyword_query("결제", "kw-query-v9")
