# Data Model: QK-EMB-001

저장소 쪽은 마이그레이션 `0003_embedding_usage.sql` 하나로 추가한다. 기존 `qk.embedding`(QK-STO-001)은 바꾸지 않고 캐시로 그대로 쓴다.
도메인 타입은 `src/qello_knowledge/domain/embedding.py`에 둔다(research R-02).

## 1. 도메인 타입

### ModelSpec (코드 상수 `MODELS`, R-03)

| 필드 | 값(bge-m3) | 규칙 |
| --- | --- | --- |
| `model_version` | `@cf/baai/bge-m3` | 인덱스 버전의 `embedding_model`과 같은 문자열 |
| `dimension` | 1024 | `qk.embedding.vector` 타입과 같아야 한다 |
| `max_input_tokens` | 8192 | 넘으면 자르지 않고 `input_too_long`(FR-003) |
| `neurons_per_million_tokens` | 1075 | 요금표 값(스파이크 3.2) |
| `bytes_per_token_estimate` | 3.5 | 예상 계산용(R-04) |

### EmbedInput / EmbedRequest

| 타입 | 필드 | 규칙 |
| --- | --- | --- |
| `EmbedInput` | `text: str`, `origin: tuple[str, str] \| None` | `text.strip()`이 비면 `empty_input`. 색인용인데 `origin`이 없으면 `no_origin`. 전송 직전 검사에 걸리면 `secret_blocked`(FR-005, research R-13). 질의용은 `origin=None` |
| `EmbedRequest` | `inputs: tuple[EmbedInput, ...]`, `purpose: EmbedPurpose`, `model_version: str`, `run_id: str`, `allow_partial: bool = False` | `model_version`이 `MODELS`에 없으면 `EmbedError(auth_config)`. `allow_partial`은 색인용에서만 뜻이 있다(FR-024) |

### EmbedItem / EmbedResult

| 타입 | 필드 | 규칙 |
| --- | --- | --- |
| `EmbedItem` | `index: int`, `vector: tuple[float, ...] \| None`, `failure: EmbedFailureKind \| None`, `cached: bool` | `vector`와 `failure` 중 하나만 있다. 입력 순서와 같다(FR-001) |
| `RunSummary` | `requested`, `cache_hits`, `deduplicated`, `provider_calls`, `failures: dict[kind, int]`, `neurons`, `estimated_neurons`, `warnings: tuple[str, ...]` | QK-SYN-001 실행 기록이 그대로 쓴다(FR-015) |
| `EmbedResult` | `items: tuple[EmbedItem, ...]`, `model_version`, `dimension`, `summary: RunSummary` | |

### EmbedFailureKind

`empty_input`, `no_origin`, `secret_blocked`, `input_too_long`, `transient`, `provider_quota`, `index_budget`, `bad_response`, `usage_unavailable`. 묶음 전체를 멈추는 `auth_config`, `no_active_index`,
`usage_unavailable`(첫 외부 호출 전 사용량 조회 실패, R-08)은 `EmbedError(kind)` 예외로 던진다. 이미 만든 벡터는 예외 전에 저장된다(FR-011).
외부 호출 뒤 사용량 기록(예약·정산·질의 기록)이 실패하면 예외를 던지지 않는다. 그 호출의 결과는 돌려주고 `RunSummary.warnings`에
`usage_unavailable`을 남기며, 색인용이면 보내지 않은 항목을 `usage_unavailable` 실패로 끝낸다(spec Edge Cases, 2026-10-20 결정).

### EmbedPreview (FR-022)

| 필드 | 뜻 |
| --- | --- |
| `requested` | 입력 개수 |
| `cache_hits` | 캐시에 있는 개수 |
| `deduplicated` | 같은 묶음 안 중복으로 빠지는 개수 |
| `to_embed` | 새로 보낼 개수 |
| `over_limit_expected` | 예상 토큰이 입력 한도를 넘는 개수 |
| `estimated_neurons` | `to_embed`분 예상 Neurons |
| `basis` | `{bytes_total, bytes_per_token, neurons_per_million_tokens}`(FR-023) |
| `index_budget`, `index_used_today`, `index_remaining` | 그날 색인 예산 상태 |
| `runnable` | `estimated_neurons ≤ index_remaining` |

### BudgetSettings (R-11)

| 필드 | 설정 이름 | 기본값 | 규칙 |
| --- | --- | --- | --- |
| `daily_allowance` | `QK_EMBED_DAILY_ALLOWANCE` | 10000 | 양의 정수 |
| `index_budget` | `QK_EMBED_INDEX_BUDGET` | 5000 | 양의 정수 |
| `query_reserve` | `QK_EMBED_QUERY_RESERVE` | 3000 | 양의 정수. `index_budget + query_reserve ≤ daily_allowance`(FR-017) |

## 2. 저장소 테이블 (`0003_embedding_usage.sql`)

### qk.embedding_usage — 외부 호출 한 번 = 행 하나 (FR-013)

| 칼럼 | 타입 | 규칙 |
| --- | --- | --- |
| `id` | bigint identity | PK |
| `occurred_at` | timestamptz | NOT NULL, 기본 `now()` |
| `usage_day` | date | NOT NULL. `(occurred_at AT TIME ZONE 'UTC')::date`. 하루 경계 00:00 UTC |
| `purpose` | text | `index` 또는 `query` |
| `run_id` | text | NOT NULL. 질의는 질의 요청 식별자(원문 아님) |
| `model_version` | text | NOT NULL |
| `input_count` | int | ≥ 0 |
| `input_bytes` | int | ≥ 0. 텍스트 원문은 저장하지 않는다(FR-013) |
| `estimated_neurons` | numeric(14,6) | NOT NULL, ≥ 0 |
| `neurons` | numeric(14,6) | 정산 전 NULL. 정산 뒤 ≥ 0. 소수 여섯째 자리: 작은 호출의 반올림 누락 방지(2026-10-20 결정) |
| `measured` | boolean | 정산 전 NULL. 제공자 값이면 true, 추정이면 false(FR-014) |
| `state` | text | `reserved`(예약만, 색인용) 또는 `settled` |
| `outcome` | text | 정산 전 NULL. `ok`, `input_too_long`, `transient`, `provider_quota`, `bad_response`, `auth_config` |

- 인덱스: `(usage_day, purpose)`.
- 체크: `state = 'settled'`이면 `neurons`, `measured`, `outcome`이 NOT NULL. `purpose = 'query'`이면 `state = 'settled'`(질의는 예약하지 않는다).
- 하루 사용량 계산: `settled`는 `neurons`, `reserved`는 `estimated_neurons`를 더한다(R-08 보수적 집계).

### qk.embedding_usage_daily — 90일 지난 날의 합계 (FR-025)

| 칼럼 | 타입 | 규칙 |
| --- | --- | --- |
| `usage_day` | date | PK 일부 |
| `purpose` | text | PK 일부 |
| `model_version` | text | PK 일부 |
| `neurons` | numeric(16,6) | 그날 합계(예약은 예상량으로) |
| `calls` | int | 호출 수 |
| `estimated_calls` | int | `measured = false` 또는 미정산 호출 수 |

## 3. SQL 함수 (R-08, R-13)

| 함수 | 입력 | 결과 | 규칙 |
| --- | --- | --- | --- |
| `qk.embedding_reserve` | `run_id, model_version, input_count, input_bytes, estimated, index_budget` | `jsonb {granted, reservation_id, index_used, index_remaining}` | `pg_advisory_xact_lock`(그날 키) 안에서 합산·판정·예약 삽입. 넘으면 `granted=false`, 행 없음(FR-018·021) |
| `qk.embedding_settle` | `reservation_id, neurons, measured, outcome` | void | `reserved` 행만 `settled`로. 이미 정산된 행이면 아무것도 안 한다(재실행 안전) |
| `qk.embedding_record` | `run_id, model_version, input_count, input_bytes, estimated, neurons, measured, outcome` | `jsonb {query_used, query_reserve_exceeded}` | 질의용. `query_reserve`는 인자로 받는다(FR-019) |
| `qk.embedding_usage_today` | `index_budget, query_reserve` | `jsonb {usage_day, total, index_used, query_used, index_remaining, estimated_share}` | 조회 전용(FR-016) |
| `qk.embedding_usage_prune` | `retention_days DEFAULT 90` | `jsonb {days_rolled_up, rows_deleted}` | 날짜 단위로 일 합계 upsert 후 삭제. 한 트랜잭션. 두 번째 실행은 0건. `retention_days < 1`이면 거부 |

## 4. 상태 전이

```text
색인 요청:  (예약 시도) ──granted──▶ reserved ──settle──▶ settled(ok | 실패 종류)
                    └─denied──▶ 행 없음, 항목은 index_budget
질의 요청:  record ──▶ settled
90일 경과:  settled/reserved 행 ──prune──▶ embedding_usage_daily 합계 + 행 삭제
```

## 5. 기존 저장소 경계에 더하는 것

- `Store.find_embeddings(refs: Sequence[EmbeddingRef]) -> dict[EmbeddingRef, tuple[float, ...]]`: 묶음 캐시 조회 한 번(R-07). 없는 키는 결과에 없다.
- 사용량은 `Store`가 아니라 새 `UsageLedger` Protocol(`ports/embedder.py`)로 둔다. 구현은 `adapters/postgres/usage.py`가 위 함수를 부른다.
  메모리 구현은 테스트용으로 `tests/unit/fakes.py` 옆에 둔다.
