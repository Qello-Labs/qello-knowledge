"""키워드 검색 텍스트 규칙 식별자와 인덱스 버전 대응표(QK-RET-001 research R-03~R-05).

청킹 규칙 버전은 해시라 거꾸로 풀 수 없고, 해시 계산은 Workers 번들에 못 넣는다. 그래서 계산 결과를 상수로 두고
단위 시험이 계산값과 같은지 확인한다. 표에 없는 인덱스 버전은 `unknown`이다.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

QUERY_RULES = ("kw-query-v1", "kw-query-raw")
INDEX_BASELINE = "kw-index-baseline-v1"
INDEX_IDSPLIT = "kw-index-idsplit-v1"
INDEX_RULES = (INDEX_BASELINE, INDEX_IDSPLIT)

INDEX_KEYWORD_RULES: Mapping[str, str] = MappingProxyType(
    {
        "iv-4c0bc4fcc642": INDEX_BASELINE,  # bge-m3, chk-md-20d966f730bb, meta-v1
    }
)


def index_rule_for(index_version: str | None) -> str:
    if index_version is None:
        return "unknown"
    return INDEX_KEYWORD_RULES.get(index_version, "unknown")
