"""RRF 통합 순위(research R-02, spec FR-003·FR-004·SC-001, tasks T015)."""

from __future__ import annotations

from fractions import Fraction

from qello_knowledge.retrieval import fuse
from tests.unit.retrieval.fakes import keyword_result, vector_result


def test_scores_are_sum_of_reciprocal_ranks() -> None:
    hits = fuse(vector_result(1, 2, 3), keyword_result((3, 2), (4, 1)), 60)
    scores = {h.chunk_id: h.score for h in hits}
    assert scores[3] == float(Fraction(1, 63) + Fraction(1, 61))
    assert scores[1] == float(Fraction(1, 61))
    assert scores[4] == float(Fraction(1, 62))
    assert [h.chunk_id for h in hits][0] == 3


def test_one_sided_chunks_stay_and_ranks_are_recorded() -> None:
    hits = {h.chunk_id: h for h in fuse(vector_result(1, 2), keyword_result((2, 3), (9, 1)), 60)}
    assert set(hits) == {1, 2, 9}
    assert (hits[2].vector_rank, hits[2].keyword_rank, hits[2].keyword_matched) == (2, 1, 3)
    assert (hits[1].keyword_rank, hits[1].keyword_score, hits[1].keyword_matched) == (None, None, None)
    assert (hits[9].vector_rank, hits[9].vector_score) == (None, None)
    assert hits[2].vector_score is not None and hits[2].keyword_score == 3.0


def test_ties_break_by_vector_rank_then_keyword_rank_then_id() -> None:
    # 1/(60+1) + 1/(60+4) 와 1/(60+4) + 1/(60+1)은 정확히 같다. 벡터 순위가 앞선 쪽이 먼저다.
    vector = vector_result(10, 20, 30, 40)
    keyword = keyword_result((40, 1), (50, 1), (60, 1), (10, 1))
    hits = fuse(vector, keyword, 60)
    order = [h.chunk_id for h in hits]
    assert order.index(10) < order.index(40)
    # 한쪽에만 있고 순위가 같은 청크: 벡터에만 있는 쪽이 앞(없는 순위는 가장 뒤)
    only = fuse(vector_result(7), keyword_result((8, 1)), 60)
    assert [h.chunk_id for h in only] == [7, 8]


def test_identical_inputs_give_identical_output() -> None:
    args = (vector_result(5, 3, 1), keyword_result((1, 2), (5, 1)), 60)
    assert fuse(*args) == fuse(*args)


def test_k_changes_scores() -> None:
    a = fuse(vector_result(1), None, 60)[0].score
    b = fuse(vector_result(1), None, 10)[0].score
    assert a != b and b == 1 / 11


def test_ranks_are_consecutive_from_one() -> None:
    hits = fuse(vector_result(1, 2), keyword_result((3, 1)), 60)
    assert [h.rank for h in hits] == [1, 2, 3]


def test_missing_sides() -> None:
    assert fuse(None, None, 60) == ()
    assert [h.chunk_id for h in fuse(None, keyword_result((4, 1)), 60)] == [4]
