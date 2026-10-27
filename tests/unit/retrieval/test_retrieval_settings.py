"""검색 설정의 기본값과 범위 검사(spec FR-028, data-model 1.1)."""

from __future__ import annotations

import pytest

from qello_knowledge.domain.retrieval import RetrievalSettings

DEFAULTS = {
    "candidates": 20,
    "rrf_k": 60,
    "expand_top": 8,
    "before": 1,
    "after": 1,
    "context_budget": 3000,  # ADR-025
    "question_max_chars": 2000,
    "query_rule": "kw-query-v1",
    "bytes_per_token": 3.5,
}

RANGES = {
    "candidates": (1, 50),
    "rrf_k": (1, 1000),
    "expand_top": (1, 20),
    "before": (0, 3),
    "after": (0, 3),
    "context_budget": (1, 8000),
    "question_max_chars": (1, 8000),
}


def test_defaults() -> None:
    settings = RetrievalSettings()
    for name, value in DEFAULTS.items():
        assert getattr(settings, name) == value


@pytest.mark.parametrize(("name", "bounds"), RANGES.items())
def test_range_edges_are_accepted(name: str, bounds: tuple[int, int]) -> None:
    for value in bounds:
        assert getattr(RetrievalSettings(**{name: value}), name) == value


@pytest.mark.parametrize(("name", "bounds"), RANGES.items())
def test_out_of_range_is_rejected(name: str, bounds: tuple[int, int]) -> None:
    low, high = bounds
    for value in (low - 1, high + 1):
        with pytest.raises(ValueError):
            RetrievalSettings(**{name: value})


@pytest.mark.parametrize("value", [True, 2.0, "20"])
def test_non_integer_is_rejected(value: object) -> None:
    with pytest.raises(ValueError):
        RetrievalSettings(candidates=value)  # type: ignore[arg-type]


def test_unknown_query_rule_is_rejected() -> None:
    with pytest.raises(ValueError):
        RetrievalSettings(query_rule="kw-query-v9")
    assert RetrievalSettings(query_rule="kw-query-raw").query_rule == "kw-query-raw"


def test_bytes_per_token_must_be_positive() -> None:
    with pytest.raises(ValueError):
        RetrievalSettings(bytes_per_token=0)


def test_overrides_are_checked_too() -> None:
    settings = RetrievalSettings().with_overrides({"candidates": 5, "context_budget": 300})
    assert (settings.candidates, settings.context_budget) == (5, 300)
    with pytest.raises(ValueError):
        RetrievalSettings().with_overrides({"expand_top": 0})
    with pytest.raises(ValueError):
        RetrievalSettings().with_overrides({"no_such_setting": 1})
