# Contract: 임베딩 경계 (`ports/embedder.py`)

후속 명세(QK-SYN-001, QK-RET-001)는 이 문서와 `Embedder` Protocol만 보고 임베딩을 쓴다. 타입은 [data-model.md](../data-model.md) 1절.

## Embedder

```text
embed(request: EmbedRequest) -> EmbedResult
preview(request: EmbedRequest) -> EmbedPreview
```

### embed 처리 순서

1. 활성 또는 지정 인덱스 버전의 모델이 `MODELS`에 없으면 `EmbedError(no_active_index | auth_config)`.
2. 항목별 사전 검사: `empty_input`, (색인용) `no_origin`. 외부 호출 없음.
3. (색인용) 캐시 조회 `Store.find_embeddings`. 적중 항목은 `cached=true`.
4. 남은 항목의 같은 텍스트를 하나로 묶는다(FR-010).
   - 전송 직전 검사: 보낼 텍스트마다 `check_outgoing([OutgoingPiece(text, origin)], policy)`. 걸리면 `secret_blocked`로 끝내고 이후 단계에서 뺀다(FR-005, research R-13).
5. (색인용) 미리 보기 계산. `runnable=false`이고 `allow_partial=false`면 남은 항목 전부 `index_budget`으로 끝낸다. 외부 호출 0건(FR-024).
6. 묶음 나누기(최대 32개·32,768 예상 토큰, 큰 텍스트는 단독, R-05·R-06).
7. 요청마다:
   - 색인용: `UsageLedger.reserve` → 거부면 그 요청과 이후 요청 전부 `index_budget`(부분 실행일 때 이미 끝난 결과는 유지).
   - `EmbeddingProvider.embed_texts` 호출, 실패 분류(research R-09), 3030이면 반으로 나눠 다시.
   - (색인용) 성공 벡터를 `Store.put_embedding`으로 저장(FR-011).
   - 색인용: `UsageLedger.settle`, 질의용: `UsageLedger.record`. 기록이 실패하면 그 호출의 결과는 돌려주고 경고 `usage_unavailable`을 남긴다.
     색인용이면 이후 요청을 보내지 않고 남은 항목을 `usage_unavailable`로 끝낸다(spec Edge Cases). 예약 자체가 실패해도 같다.
   - `provider_quota`면 남은 요청을 보내지 않는다(FR-020).
8. 입력 순서대로 `EmbedItem`을 채우고 `RunSummary`를 붙인다.

### 보장

| 보장 | 근거 |
| --- | --- |
| 결과 길이 = 입력 길이, 순서 같음 | FR-001 |
| 결과·오류에 제공자 고유 타입·HTTP 상태·오류 코드가 없다 | FR-001, SC-007 |
| 자른 입력으로 만든 벡터가 없다 | FR-003, SC-004 |
| 비밀값 규칙에 걸린 텍스트와 출처 없는 색인용 텍스트는 외부로 나가지 않는다. 기록에는 항목 번호·규칙 이름·줄 번호만 남는다 | FR-005, SC-006, QK-SEC-001 FR-013 |
| 질의 벡터는 저장하지 않는다 | FR-012 |
| 사용량 기록에 원문이 없다 | FR-013, SC-003 |
| 색인 사용량 초과 폭 ≤ 요청 하나의 (실제 − 예상) | FR-021, SC-002 |

### preview

`embed`의 1~5단계와 같은 계산을 하고 외부 호출·예약·저장을 하지 않는다. 예상 토큰이 한도를 넘는 항목은 `over_limit_expected`로 센다(US5 AS4).

## EmbeddingProvider

```text
embed_texts(model: ModelSpec, texts: Sequence[str]) -> ProviderBatch
```

- `ProviderBatch(vectors: tuple[tuple[float, ...], ...], neurons: float | None)`. `neurons`는 제공자가 알려 준 값(`cf-ai-neurons`), 없으면 `None`.
- 실패는 `ProviderFailure(kind, retry_after_seconds | None)` 예외. `kind`는 `input_too_long`, `transient`, `provider_quota`, `auth_config`, `bad_response`.
- 재시도는 하지 않는다. 재시도는 `EmbeddingService`가 한다(정책 한 곳).
- 구현: `adapters/workers_ai/rest.py`(색인), `embedding/fake.py`(테스트·개발). Workers 바인딩 구현은 QK-RET-001(research R-10).

### 제공자 계약 테스트 (`tests/contract/embedding_provider_contract.py`)

어떤 구현이든 다음을 통과한다.

1. 텍스트 N개 → 벡터 N개, 각 차원 = `model.dimension`.
2. 같은 텍스트 → 같은 벡터(가짜) / 정해진 응답 사례 재생(REST).
3. 한도 초과 사례 → `ProviderFailure(input_too_long)`.
4. 할당 소진 사례 → `ProviderFailure(provider_quota)`, 일시 오류 사례 → `transient`(+`Retry-After`).
5. 인증 실패 사례 → `auth_config`. 예외 문구에 토큰·계정 ID가 없다.

## UsageLedger

```text
reserve(run_id, model_version, input_count, input_bytes, estimated) -> Reservation | None
settle(reservation, neurons, measured, outcome) -> None
record(run_id, model_version, input_count, input_bytes, estimated, neurons, measured, outcome) -> QueryUsage
today() -> DailyUsage
prune(retention_days=90) -> PruneResult
```

`index_budget`, `query_reserve`는 생성 시 `BudgetSettings`로 받는다. Postgres 구현은 data-model 3절 함수를 한 번씩 부른다.
