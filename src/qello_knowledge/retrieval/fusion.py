"""RRF 통합 순위(QK-RET-001 research R-02, spec FR-003·FR-004).

점수는 `fractions.Fraction`으로 정확하게 비교하고 결과에는 `float`으로 싣는다. 수학적으로 같은 합은 언제나 동점이 된다.
"""

from __future__ import annotations

from fractions import Fraction

from qello_knowledge.domain.retrieval import FusedHit
from qello_knowledge.domain.store import Provenance, SearchResult
from qello_knowledge.ports.retrieval import KeywordSearchResult

_LAST = float("inf")


def fuse(vector: SearchResult | None, keyword: KeywordSearchResult | None, k: int) -> tuple[FusedHit, ...]:
    """두 검색 결과를 합친다. 한 결과 안의 같은 청크 검사는 호출하는 쪽이 먼저 한다."""
    scores: dict[int, Fraction] = {}
    provenance: dict[int, Provenance] = {}
    vector_seen: dict[int, tuple[int, float]] = {}
    keyword_seen: dict[int, tuple[int, int, float]] = {}
    for hit in vector.hits if vector is not None else ():
        scores[hit.chunk_id] = scores.get(hit.chunk_id, Fraction(0)) + Fraction(1, k + hit.rank)
        provenance.setdefault(hit.chunk_id, hit.provenance)
        vector_seen[hit.chunk_id] = (hit.rank, hit.score)
    for item in keyword.hits if keyword is not None else ():
        hit = item.hit
        scores[hit.chunk_id] = scores.get(hit.chunk_id, Fraction(0)) + Fraction(1, k + hit.rank)
        provenance.setdefault(hit.chunk_id, hit.provenance)
        keyword_seen[hit.chunk_id] = (hit.rank, item.matched_terms, hit.score)

    def key(chunk_id: int) -> tuple[Fraction, float, float, int]:
        v = vector_seen.get(chunk_id)
        w = keyword_seen.get(chunk_id)
        return (-scores[chunk_id], v[0] if v else _LAST, w[0] if w else _LAST, chunk_id)

    fused = []
    for rank, chunk_id in enumerate(sorted(scores, key=key), start=1):
        v = vector_seen.get(chunk_id)
        w = keyword_seen.get(chunk_id)
        fused.append(
            FusedHit(
                chunk_id=chunk_id,
                rank=rank,
                score=float(scores[chunk_id]),
                provenance=provenance[chunk_id],
                vector_rank=v[0] if v else None,
                vector_score=v[1] if v else None,
                keyword_rank=w[0] if w else None,
                keyword_matched=w[1] if w else None,
                keyword_score=w[2] if w else None,
            )
        )
    return tuple(fused)
