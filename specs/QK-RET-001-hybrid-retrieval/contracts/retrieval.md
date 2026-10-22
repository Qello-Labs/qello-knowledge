# Contract: 검색 경계

**명세**: [../spec.md](../spec.md) FR-001~028 · **결정**: [../research.md](../research.md) R-01~R-07, R-12, R-14 · **타입**: [../data-model.md](../data-model.md)

## 1. 공개 함수

```text
retrieval.retrieve(request: RetrievalRequest, deps: RetrievalDeps, settings: RetrievalSettings) -> RetrievalResult
retrieval.keyword_query(question: str, rule: str) -> tuple[str, ...]     # 낱말 배열(최대 16). 저장소 호출 없음
retrieval.fuse(vector: SearchResult | None, keyword: KeywordSearchResult | None, k: int) -> tuple[FusedHit, ...]
retrieval.pack(hits, context: ContextResult, settings) -> (tuple[ContextBlock, ...], tuple[Skipped, ...], used_tokens)
```

`RetrievalDeps`는 `store: RetrievalStore`, `embedder: Embedder`, `new_run_id: Callable[[], str]`, `model_version: str`(질의 임베딩 모델, 기본 `@cf/baai/bge-m3`)이다. `retrieval/`은 `adapters`·`security`·`chunking`을 가져오지 않는다.

## 2. `RetrievalStore` (ports/retrieval.py)

```text
search_vector(query: Sequence[float], top_n: int, filters: SearchFilter) -> SearchResult      # QK-STO-001 그대로
search_keyword_terms(terms: Sequence[str], top_n: int, filters: SearchFilter) -> KeywordSearchResult # 새 연산, 0005 qk.search_keyword_terms
chunk_context(center_ids: Sequence[int], before: int, after: int) -> ContextResult            # 새 연산, 0005 qk.chunk_context
```

`KeywordSearchResult`는 `status`, `index_version`, `hits: tuple[KeywordHit, ...]`이고 `KeywordHit`은 `hit: SearchHit`과 `matched_terms: int`다(`domain/store.py`는 바꾸지 않는다, 2026-10-22 재승인).
`ContextResult`는 `index_version: str | None`과 중심별 `ContextItem(center, section_first, before, after)`이다. 오류는 QK-STO-001과 같은 `StoreUnavailable`·`StoreError`다.

## 3. `retrieve` 처리 순서

1. 질문을 앞뒤 공백 제거로 본다. 비었으면 `empty_question`, 글자 수가 상한을 넘으면 `question_too_long`. 외부 호출 0건.
2. 설정과 `overrides`를 합쳐 범위를 검사한다.
3. 방식이 `hybrid`·`vector`면 질의용 임베딩(R-07). 실패는 R-14 표대로. `keyword`면 부르지 않는다.
4. 방식이 `hybrid`·`keyword`면 `keyword_query`.
5. 벡터 검색(벡터가 있을 때), 키워드 검색(낱말이 0개여도 부른다. 빈 결과와 활성 인덱스 버전을 받는다). 각각 `candidates`개. 실패는 research R-14 순서로 잡는다.
6. 어느 결과든 `no_active_index`면 `no_active_index`로 끝낸다. 두 결과의 `index_version`이 다르면 `index_version_changed`로 끝낸다(다시 검색하지 않음).
7. `fuse`. 결과가 0건이면 `no_results`(Context 비어 있음).
8. `want_context=False`면 9~10을 건너뛴다.
9. 통합 상위 `expand_top`개 청크로 `chunk_context` 한 번. 반환 `index_version`이 6의 버전과 다르면 `index_version_changed`.
   반환에 없는 중심은 `Skipped(not_visible)`.
10. `pack`(spec FR-016 알고리즘). 담긴 청크를 문서별 `ContextBlock`으로 모으고 `source_id`를 붙인다.
11. `RetrievalSummary`를 채운다. `external_calls`는 제공자 호출 + 사용량 기록 + 저장소 호출 수다.

## 4. `pack` 알고리즘 (spec FR-016)

```text
used = 0; taken = {}
for hit in 통합 순위 순서 중 chunk_context가 돌려준 중심:
    t = tokens(center)
    if t > budget: skip(center, larger_than_budget)
    elif used + t > budget: skip(center, budget_exhausted)
    else: take(center)
for hit in 통합 순위 순서 중 담긴 중심:
    for cand in [section_first] + before(가까운 것부터) + after(가까운 것부터):
        if cand is None or cand.chunk_id in taken: continue
        if used + tokens(cand) > budget: skip(cand, budget_exhausted); continue
        take(cand)
# skip은 같은 청크를 한 번만 남기고(처음 역할·사유), 나중에 take되면 skipped에서 뺀다
blocks = 담긴 청크를 artifact별로 모아 ordinal 정렬, gaps 계산, rank = min(중심 순위), rank 순으로 S1, S2…
```

## 5. 보장

| 보장 | 근거 |
| --- | --- |
| 결과·Context의 청크는 모두 저장소 노출 조건을 거쳤다. 노출 조건을 우회하는 캐시·조회가 없다 | FR-007, SC-002 |
| 한 결과의 모든 청크는 같은 인덱스 버전이다 | FR-006 |
| Context 예상 토큰 합 ≤ 예산, 잘린 청크 0, 중복 0 | FR-016, SC-003 |
| 같은 입력·같은 색인이면 같은 결과·Context·Source ID | FR-004, FR-015, SC-001 |
| 외부 호출 ≤ 7(하이브리드, 재시도 포함) | FR-026, SC-007 |
| 단일 방식은 다른 방식 결과로 바꾸지 않는다 | FR-010, SC-011 |
| 요약·기록·오류 메시지에 질문 원문·검색어·본문이 없다 | FR-008, FR-024, SC-008 |
| 호출자는 psycopg·Workers AI 고유 타입을 보지 않는다 | FR-011, C-06 |

## 6. 다른 경계에 더하는 것

| 경계 | 변경 |
| --- | --- |
| `domain/chunking.py` `ChunkingSettings` | `keyword_text_rule: str = "kw-index-baseline-v1"` 추가. 알 수 없는 값은 거부 |
| `chunking/header.py` | `search_text(header, body, rule)`. 기준선은 지금과 같은 결과 |
| `chunking/version.py` | 규칙이 기준선이 아닐 때만 재료에 `keyword_text_rule` 추가(R-04) |
| `adapters/postgres/store.py` `PostgresStore` | `search_keyword_terms`, `chunk_context`, `source_revisions`(확인 명령·평가용, `retrieve()`는 부르지 않음) 추가. 기존 메서드 변경 없음 |
| `adapters/postgres/migrations/0005_retrieval.sql` | `qk.search_keyword_terms`, `qk.chunk_context` 함수 추가. 기존 함수·테이블 변경 없음 |
| `config/registry.py` | `QK_RETRIEVAL_CONTEXT_BUDGET` 등록(질의·색인 진입점) |
| `tests/unit/test_boundaries.py` | `RESTRICTED`에 `retrieval`, `ALLOWED_INTERNAL`에 `qello_knowledge.retrieval` 추가. `retrieval`은 상대 경로 가져오기를 쓰지 않는다(검사가 `level>0`을 보지 않으므로 규칙으로 둔다) |
| `indexer/sync_cli.py` | 조립 함수가 `ChunkingSettings`를 인자로 받고, 활성화의 현재 버전도 그 설정으로 계산(기본값 동작 그대로, research R-09) |
| `config/registry.py` 생성물 | 설정 예시 파일 재생성(`qk_retrieval_context_budget` 항목) |
