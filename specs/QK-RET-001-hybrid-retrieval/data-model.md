# Data Model: QK-RET-001 하이브리드 검색

검색 흐름의 타입은 `domain/retrieval.py`, 규칙 대응표는 `domain/keyword_rules.py`, 저장소 쪽 새 함수는 `0005_retrieval.sql`에 둔다.
저장 스키마의 테이블·열은 바꾸지 않는다. 질문 원문은 어떤 타입에도 저장되지 않고, `RetrievalRequest`에서만 메모리로 지난다(spec FR-008).

## 1. 설정과 요청

### 1.1 `RetrievalSettings` (research R-12)

| 필드 | 기본 | 범위 | spec |
| --- | --- | --- | --- |
| `candidates` | 20 | 1~50 | FR-002, FR-028 |
| `rrf_k` | 60 | 1~1,000 | FR-003 |
| `expand_top` | 8 | 1~20 | FR-012. 문맥 확장을 끄려면 `want_context=False` |
| `before`, `after` | 1, 1 | 0~3 | FR-012 |
| `context_budget` | 2,000 | 1~8,000 | FR-016 |
| `question_max_chars` | 2,000 | 1~8,000 | FR-009 |
| `query_rule` | `kw-query-v1` | `QUERY_RULES` 안 | FR-017 |
| `bytes_per_token` | 3.5 | QK-EMB-001 모델 설정과 같음 | FR-016 |

범위를 벗어나면 생성 때 `ValueError`(설정 검사 실패). 환경값은 `QK_RETRIEVAL_CONTEXT_BUDGET`만 받는다.

### 1.2 `RetrievalRequest`

| 필드 | 뜻 |
| --- | --- |
| `question` | 질문 문장. 저장·기록하지 않는다 |
| `mode` | `hybrid` / `vector` / `keyword` (spec FR-022) |
| `filters` | QK-STO-001 `SearchFilter` |
| `want_context` | `False`면 문맥 확장·담기를 하지 않는다(FR-023) |
| `overrides` | `RetrievalSettings`의 일부 값(평가·확인 명령용). 합친 값도 1.1 범위 검사를 받는다 |

## 2. 결과

### 2.1 `FusedHit`

| 필드 | 뜻 |
| --- | --- |
| `chunk_id` | 청크 식별자 |
| `rank`, `score` | 통합 순위(1부터), RRF 점수(단일 방식이면 그 검색의 순위로 계산한 같은 식) |
| `vector_rank`, `vector_score` | 벡터 검색 순위·원래 점수(1 − 코사인 거리). 없으면 `None` |
| `keyword_rank`, `keyword_matched`, `keyword_score` | 키워드 검색 순위, 서로 다른 맞은 낱말 수, PGroonga 점수(OR 질의 한 번). 없으면 `None` |
| `provenance` | QK-STO-001 `Provenance` |

### 2.2 `ContextChunk`

| 필드 | 뜻 |
| --- | --- |
| `chunk_id`, `ordinal`, `heading_path`, `locator` | 청크 식별자, 같은 자료 안 순서, 제목 경로, 위치 |
| `role` | `center` / `section_first` / `before` / `after` |
| `body`, `estimated_tokens` | 본문, 예상 토큰(`ceil(UTF-8 바이트 ÷ bytes_per_token)`) |

### 2.3 `ContextBlock` (문서 하나, spec FR-013·FR-015)

| 필드 | 뜻 |
| --- | --- |
| `source_id` | `S1`, `S2`…. Context 안 묶음 순서대로 붙인다. 같은 입력이면 같다 |
| `rank` | 묶음 안 중심 청크의 가장 높은 통합 순위 |
| `source_url`, `source_version`, `source_modified_at`, `collected_at` | 문서 단위 출처 |
| `chunks` | `ContextChunk` 목록, `ordinal` 오름차순 |
| `centers` | 중심 청크 `(chunk_id, rank)` 목록 |
| `gaps` | 순서가 끊긴 자리 `(앞 ordinal, 뒤 ordinal)` 목록. 생성 입력에서 생략 표시로 쓴다 |
| `estimated_tokens` | 청크 예상 토큰 합 |

불변식: 한 청크는 Context 전체에서 한 묶음에 한 번만 있다. 묶음은 `rank` 오름차순이다. 모든 청크가 같은 자료·같은 인덱스 버전이다.

### 2.4 `Skipped`

| 필드 | 뜻 |
| --- | --- |
| `chunk_id`, `role` | 담지 못한 청크와 역할 |
| `reason` | `larger_than_budget` / `budget_exhausted` / `not_visible`(주변 조회가 다시 확인해 뺀 중심) |

같은 청크는 한 번만 남긴다. 처음 건너뛴 때의 역할과 사유를 쓰고, 뒤에 담기면 목록에서 뺀다.

### 2.5 `RetrievalSummary` (spec FR-024)

`mode`, `candidates`, `rrf_k`, `query_rule`, `index_rule`(R-05 대응표, 없으면 `unknown`), `index_version`, `omitted`(생략한 검색과 사유 목록),
`vector_count`, `keyword_count`, `keyword_terms`(검색어 낱말 수. 낱말 자체는 넣지 않는다), `block_count`, `used_tokens`, `budget`, `skipped`(2.4),
`embedding`(QK-EMB-001 `RunSummary`의 호출 수·Neurons·캐시), `external_calls`(FR-026 기준으로 센 수), `source_revisions`(자료원별 색인 원본 리비전. `retrieve()`는 비워 두고
확인 명령·평가가 `qk.sync_run_source.origin_version`에서 채운다, research R-09). 질문 원문, 검색어, 청크 본문은 없다.

### 2.6 `RetrievalResult`

`status`(`ok` / `no_results` / 실패 종류), `hits`(`FusedHit` 목록), `context`(`ContextBlock` 목록, `want_context=False`면 비어 있음), `summary`.

### 2.7 실패 종류 `RetrievalFailure` (spec FR-011, research R-14)

`empty_question`, `question_too_long`, `no_active_index`, `store_unavailable`, `index_version_changed`, `query_embedding_failed`, `outgoing_blocked`,
`keyword_search_failed`, `both_searches_failed`. spec FR-011의 아홉 종류 그대로다. 벡터 전용의 벡터 검색 `StoreError`는 `store_unavailable`로 대응한다. 매핑은 research R-14. 하이브리드의 축소 동작은 실패가 아니라 `omitted`에 남는다.

## 3. 키워드 규칙 (research R-03·R-04·R-05)

| 식별자 | 쪽 | 동작 |
| --- | --- | --- |
| `kw-query-v1` | 질의 | 낱말 정리·조사 제거, 낱말 배열 최대 16개(R-03). 운영 기본값 |
| `kw-query-raw` | 질의 | 질문 전체를 낱말 하나로, 대문자 `OR`만 소문자로(비교용, AND 검색) |
| `kw-index-baseline-v1` | 색인 | 검색 헤더 + 본문(QK-CHK-002 FR-020). 운영 기본값. 해시 재료에 넣지 않는다 |
| `kw-index-idsplit-v1` | 색인 | 기준선 + 식별자 분해 낱말 줄. 해시 재료에 `keyword_text_rule`로 들어간다 |

`INDEX_KEYWORD_RULES`: `{"iv-4c0bc4fcc642": "kw-index-baseline-v1", "<구현 때 계산>": "kw-index-idsplit-v1"}`. 단위 시험이 계산값과 비교한다.

## 4. 저장소 함수 (0005)

### 4.1 `qk.search_keyword_terms` (research R-03)

입력: `terms text[]`(최대 16개, 넘으면 앞 16개), `top_n int`(1~50), `source_kinds text[]`, `artifact_kinds text[]`.
설정: `SET pgroonga.match_escalation_threshold = -1`, `SET enable_seqscan = off`, `SET search_path = qk, public, extensions`. `STABLE`, 쓰기 없음.
출력: `{"active_index_version", "hits": [hit_json의 키 + "matched_terms"]}`. 정렬 `matched_terms DESC, score DESC, chunk_id`. 순위는 1부터.
`score`는 낱말을 ` OR `로 이은 질의 한 번의 `pgroonga_score`이고, 그 질의에 없는 행은 0이다. 낱말 배열에 대문자 `OR`가 없다는 것은 두 질의 쪽 규칙(`kw-query-v1`, `kw-query-raw`)이 모두 보장한다.
낱말마다 `pgroonga_query_escape`를 거친다. `terms`가 비면 `hits`는 빈 배열이고 `active_index_version`은 채운다.

### 4.2 `qk.chunk_context` (research R-06)

입력: `center_ids bigint[]`(앞 20개만), `before int`, `after int`(각 0~3으로 자름).

출력:

```text
{
  "active_index_version": text | null,
  "items": [
    {
      "center": Item,
      "section_first": Item | null,
      "before": [Item...],   // ordinal 오름차순
      "after": [Item...]
    }
  ]
}
Item = hit_json의 키(chunk_id, rank=0, score=0, body, provenance) + "ordinal" + "artifact_id"
```

- 활성 인덱스 버전이 없으면 `items`는 빈 배열이다.
- 중심 청크가 없거나 노출 조건(`qk.is_visible`)을 통과하지 못하면 그 중심의 항목이 없다.
- 주변 청크는 중심과 같은 `artifact_id`·`index_version`만이다(자료가 같으므로 노출 조건도 같다).
- `section_first`: `ordinal < center.ordinal`이고 `heading_path <> center.heading_path`인 청크 중 가장 큰 `ordinal` 다음 청크. 그런 청크가 없으면 그 자료의 가장 작은 `ordinal`.
  그 청크가 중심이면 `null`.
- `STABLE`, `SET search_path = qk, public, extensions`. 쓰기 없음.

## 5. 평가용 색인 (research R-09)

| 항목 | 값 |
| --- | --- |
| 데이터베이스 이름 | `qk_eval_<baseline|idsplit>_<커밋 SHA 앞 12자>`. 준비 중에는 뒤에 `__preparing` |
| 대상 접속 | 로컬 컨테이너 주소 + 준비용 이름(`DATABASE_URL`을 쓰지 않음) |
| 원본 | `DATABASE_URL` 또는 `--from-url-env`의 데이터베이스. 읽기만 |
| 복사 | `qk.embedding`의 `(input_hash, model_version, vector)`, `model_version = '@cf/baai/bge-m3'` |
| 자료원 설정·범위 검토 | `config/sources.toml`과 범위 검토 파일의 임시 사본에서 대상 자료원의 `ref`만 커밋 SHA로 바꿈. 저장소 파일은 그대로 |
| 청커 설정 | `ChunkingSettings(keyword_text_rule=<규칙>)`. 활성화 버전도 같은 설정으로 계산 |
| 결과 출력 | 이름, 규칙, 커밋, 인덱스 버전, 복사 벡터 수, 임베딩 호출 수·Neurons, 활성화 결과 |
