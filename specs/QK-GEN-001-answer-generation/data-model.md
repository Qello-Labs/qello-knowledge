# Data Model: QK-GEN-001 답변 생성

모든 도메인 타입은 `src/qello_knowledge/domain/generation.py`에 두고 표준 라이브러리만 쓴다(C-06). 원문(질문·답변·청크 본문·생성 입력)을 담는 필드는 `repr=False`이고
요약·기록 타입에는 원문 필드가 없다(spec FR-012).

## 1. 설정

### `GenerationSettings`

| 필드 | 기본값 | 범위(설정 검사) | 근거 |
| --- | --- | --- | --- |
| `model_id` | `@cf/qwen/qwen3-30b-a3b-fp8` | `@cf/qwen/qwen3-` 접두어 | spec FR-018, R-12 |
| `max_tokens` | 800 | 1~4,096 | spec FR-018 |
| `temperature` | 0.2 | 0~1 | spec FR-018 |
| `timeout_seconds` | 20 | 1~60 | spec FR-022, R-07 |
| `prompt_version` | `gen-p1` | 등록된 프롬프트 이름 | spec FR-005, R-02 |
| `bytes_per_token` | 3.5 | QK-RET-001과 같음 | R-08 |
| `underestimate_factor` | 2.0 | 1.0~4.0 | spec FR-019 |
| `context_window` | 32,768 | 고정 | ADR-009 |
| `input_price_per_m` | 4,625 | > 0 | spike 3.2 |
| `output_price_per_m` | 30,475 | > 0 | spike 3.2 |
| `max_attempts` | 2 | 고정(재시도 1회) | spec FR-022 |
| `deadline_seconds` | `2 × timeout_seconds + 5`(기본 45) | 직접 주면 `2 × timeout_seconds + 5` 이상 ~ 130 | R-07(마감 안에서만 재시도, 설정만으로 재시도가 꺼지지 않게) |

환경값은 `QK_GEN_MODEL`, `QK_GEN_MAX_TOKENS`, `QK_GEN_TEMPERATURE`, `QK_GEN_TIMEOUT_SECONDS`, `QK_GEN_PROMPT_VERSION` 5개다(R-12). 나머지 필드는 조립 코드가 바꾼다.

설정 검사는 R-08 (1)식을 `RetrievalSettings`(Context 예산, 질문 길이 상한)와 함께 본다.

### `PromptSpec`

`name`(`gen-p1`·`gen-base`), `system`(글), `user_template`(`{context}`·`{question}` 자리, ` /no_think`로 끝남), `render_rule`(`render-v1`·`render-base`), `version`(R-02 해시 식별자, 계산값).
불변식: `user_template`은 ` /no_think`로 끝난다(SC-005). 렌더러는 템플릿 밖에서 글을 붙이지 않는다.

## 2. 입력

### `GenerationRequest`

| 필드 | 설명 |
| --- | --- |
| `question` | 질문 원문(`repr=False`). 검색에 넘긴 글과 같다. 생성은 앞뒤 공백을 걷어 쓴다(검색과 같음) |
| `retrieval` | QK-RET-001 `RetrievalResult` 그대로 |
| `prompt_version` | 생략하면 설정값 |
| `run_id` | 사용량 기록용. 생략하면 새로 만든다(`answer-<uuid>`) |

### `RenderedBlock`

`source_id`, `block: ContextBlock`(원본 참조. 출처 목록은 이것과 `raw_title`로 만든다), `raw_title`(무력화 전 제목), `title`(무력화 뒤, 생성 입력용), `modified_label`(`YYYY-MM-DD` 또는 `수정 미상`),
`text`(머리줄·절 줄·생략 줄·발췌문을 이은 글, `repr=False`), `excerpt_urls: frozenset[str]`(무력화 전 청크 본문에서 R-04 4단계 규칙으로 뽑은 URL), `estimated_tokens`.

### `RenderedInput`

`system`, `user`(둘 다 `repr=False`), `blocks: tuple[RenderedBlock, ...]`(검사 통과분), `dropped: tuple[DroppedBlock, ...]`, `neutralized: int`, `estimated_input_tokens: int`.
불변식: `blocks`의 Source ID는 검색 결과 Context의 Source ID 부분집합이고 순서가 같다. `user` 안에서 FR-013 규칙으로 인식되는 꼴은 각 머리줄의 `[S번호]` 하나뿐이다(SC-004).
SC-004는 `user`에만 적용한다. `system`의 인용 예시는 승인 원문이다(research R-03).

### `DroppedBlock`

`source_id`, `rules: tuple[str, ...]`(걸린 비밀값 규칙 이름). 본문·맞은 문자열은 없다.

## 3. 제공자 경계 값

### `ProviderReply`

| 필드 | 설명 |
| --- | --- |
| `text` | 모델 출력 원문(`repr=False`) |
| `input_tokens`, `output_tokens` | 응답 `usage`. 없으면 `None` |
| `neurons` | 헤더 `cf-ai-neurons`. 없으면 `None` |
| `finish_reason` | `stop`·`length`·`None`(모름) |
| `shape` | `ResponseShape` |

### `ResponseShape`

`top_keys`, `result_keys`(키 이름 튜플), `has_usage`, `has_neurons_header`, `has_finish_reason`, `parsed_as`(`response`·`choices`·`None`). 값·본문은 담지 않는다(R-01, H01).

### `GenerationProviderFailure` (예외)

`kind: GenerationFailure`(생성 전용 enum, 4절), `retry_after_seconds`, `billable: bool`(R-06 과금 가능성), `neurons: float | None`(200 응답 헤더 값 등 측정값이 있으면),
`input_tokens`·`output_tokens`(있으면), `shape: ResponseShape | None`. 메시지에 토큰·계정·본문을 넣지 않는다. QK-EMB-001 `ProviderFailureKind`는 쓰지 않는다(`timeout`이 없다).

## 4. 결과

### `GenerationStatus` (StrEnum)

`answered`, `cannot_confirm`, `retrieval_failed`, `outgoing_blocked`, `generation_failed`.

### `GenerationFailure` (StrEnum, `generation_failed`일 때)

`transient`, `timeout`, `provider_quota`, `auth_config`, `bad_response`, `input_too_long`.

### `CannotConfirmReason` (StrEnum, `cannot_confirm`일 때)

`no_results`, `empty_context`, `all_blocks_blocked`, `model_cannot_confirm`(FR-009 가), `model_unconfirmable_parts`(FR-009 나).

### `Citation`

`source_id`, `title`(무력화 전 `raw_title`), `source_url`, `source_version`, `source_modified_at: datetime | None`, `collected_at: datetime`. 값은 모두 원본 `ContextBlock`에서 온다(spec FR-011·FR-016).

### `GenerationFlags`

`unsupported_answer`(출처 확인 안 됨, FR-015), `truncated`(FR-023), `usage_record_failed`(FR-020), `thinking_detected`(Edge Cases).

### `GenerationSummary`

| 필드 | 설명 |
| --- | --- |
| `status`, `failure`, `cannot_confirm_reason`, `retrieval_failure` | 상태 값 |
| `prompt_version`, `model_id`, `max_tokens`, `temperature`, `no_think` | 생성 조건(C-13) |
| `blocks_sent`, `dropped` | 보낸 묶음 수, 뺀 묶음(Source ID, 규칙 이름) — 출처 없이 검사해 뺀 묶음 수(규칙별)는 여기서 센다 |
| `estimated_input_tokens`, `input_tokens`, `output_tokens` | 토큰 |
| `neurons`, `measured` | 시도 합계, 모두 측정이면 `True` |
| `attempts`, `latency_ms` | 시도 횟수, 생성 단계 전체 지연 |
| `removed_citations`, `unrecognized_citations`, `uncited_sentences`, `removed_urls`, `removed_source_lines`, `neutralized` | 후처리 수치. 후처리 전 모델 품질 지표(SC-008) |
| `flags` | `GenerationFlags` |
| `generation_calls`, `total_calls` | 생성 단계 실제 외부 호출 수, 검색 요약 `external_calls`를 더한 질의 전체 수 |
| `usage_today` | 마지막 기록 뒤의 `AnswerUsageToday`(임베딩·생성·질의응답 합계·예비분 초과). 기록이 없거나 실패면 `None` |
| `response_shape` | 마지막 시도의 `ResponseShape`(H01 확인용) |

질문·답변·청크 본문·URL은 없다.

### `GenerationResult`

`status`, `answer: str`(`repr=False`. 생성 실패·검색 실패·전송 차단이면 빈 글), `citations: tuple[Citation, ...]`, `summary: GenerationSummary`, `retrieval: RetrievalSummary`(QK-RET-001 그대로).

불변식:

- `status == cannot_confirm`이면 `citations == ()`.
- `citations`의 Source ID는 `answer`의 코드 표기 밖에서 FR-013 규칙으로 인식되는 인용의 ID 집합과 같고 번호 순서다. 인식하지 못한 꼴(`[S01]`, `[S9,]` 등)과 코드 안 글은 셈에 들지 않는다.
- `flags.unsupported_answer`이면 `status == answered`이고 `citations == ()`.

## 5. 사용량 기록

### `GenerationUsage` (시도마다 한 건)

`run_id`, `model_id`, `prompt_version`, `attempt`(1·2), `input_tokens`, `output_tokens`(모르면 `None`), `estimated_input_tokens`, `neurons`, `measured`, `outcome`(`ok` 또는 `GenerationFailure` 값),
`truncated`. 용도는 저장소가 `generate`로 고정한다. 시각·하루는 저장소가 정한다. 결과 종류와 Neurons는 research R-06 표로 정한다. 성공 응답 시도는 후처리 뒤에 기록해 빈 결과면 `bad_response`로 남는다.

### `AnswerUsageToday`

`usage_day`, `generation_used`, `query_embedding_used`, `answer_total`(앞의 둘의 합), `index_used`, `day_total`(하루 전체), `query_reserve`, `query_reserve_exceeded`(`answer_total` 기준).
`qk-index usage`의 `query_used`(질의 임베딩만)와 값이 다를 수 있다(R-06 남는 차이).

## 6. 저장 스키마 (`0006_generation_usage.sql`, 추가만)

```text
qk.generation_usage(
  id bigint identity PK, purpose text not null default 'generate' check (purpose = 'generate'),
  occurred_at timestamptz default now(), usage_day date generated (UTC),
  run_id text, model_id text, prompt_version text, attempt smallint check (attempt in (1, 2)),
  input_tokens int null check (>= 0), output_tokens int null check (>= 0), estimated_input_tokens int check (>= 0),
  neurons numeric(14,6) check (>= 0), measured boolean, truncated boolean,
  outcome text check (outcome in ('ok','transient','timeout','provider_quota','auth_config','bad_response','input_too_long'))
)
index (usage_day)
qk.generation_usage_daily(usage_day, model_id, neurons numeric(16,6), calls int, estimated_calls int, PK(usage_day, model_id))
qk.generation_record(...) returns jsonb          -- 행 하나 넣고 AnswerUsageToday 값을 돌려준다
qk.generation_usage_today(query_reserve int) returns jsonb
qk.generation_usage_prune(retention_days int default 90) returns jsonb
```

기존 `qk.embedding_*` 테이블·함수와 앞 마이그레이션 0001~0005는 바꾸지 않는다. `generation_usage_today`는 `qk.embedding_used(day, 'query')`·`qk.embedding_used(day, 'index')`를 읽기만 한다.
`qk-index usage prune`이 `qk.generation_usage_prune`도 부른다(R-06).

## 7. 상태 전이

```text
요청 → [R-05 판정 1~7] ─┬→ outgoing_blocked | retrieval_failed | cannot_confirm(no_results·empty_context·all_blocks_blocked) | generation_failed(input_too_long)   (생성 호출 0)
                         └→ 생성 호출(시도 1) ─ 일시 실패·시간 초과 → (마감 안이면) 대기 → 시도 2 ─ 실패 → generation_failed(transient·timeout)
                                              ├ 할당·인증·응답 오류 → generation_failed(해당 종류)
                                              └ 성공 → 후처리(R-04) → answered(+flags) | cannot_confirm(model_*) | generation_failed(bad_response: 빈 결과)
```

시도마다 사용량 기록을 쓰고, 기록 실패는 상태를 바꾸지 않고 `flags.usage_record_failed`만 세운다.
