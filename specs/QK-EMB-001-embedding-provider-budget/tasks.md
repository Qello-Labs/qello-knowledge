---
description: "QK-EMB-001 구현 작업 목록"
---

# Tasks: QK-EMB-001 임베딩 Provider·캐시·사용량 기록·일일 예산·실행 전 미리 보기

**Input**: `specs/QK-EMB-001-embedding-provider-budget/`의 plan.md, spec.md, research.md, data-model.md, contracts/embedder.md, contracts/cli.md, quickstart.md

**Tests**: 포함한다. 명세의 수용 시나리오와 C-12(수용 기준은 검증으로 닫는다)가 자동 테스트를 요구한다. 테스트를 먼저 쓰고 실패를 확인한 뒤 구현한다.

**Organization**: 사용자 스토리별 단계로 나눈다. 우선순위는 US1·US2·US3·US4(P1) → US5(P2)다.
단위·계약 테스트는 외부 호출 0건이다. DB 테스트는 `localdb` 표시를 붙이고 세션 전용 데이터베이스 `qk_test_<무작위>`에서만 돈다(QK-STO-001 research R-10).
실제 Workers AI 호출은 `external` 표시를 붙이고 사람 승인 뒤에만 돌린다(AGENTS.md 3.5·7절).

**선행 조건**: spec.md가 사람 리뷰로 승인되고, 구현용 Jira 이슈·브랜치·`TASK.md`가 준비돼야 시작한다(AGENTS.md 1절, 로드맵 1절 원칙 4).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 다른 파일을 다루고 미완료 작업에 기대지 않아 병렬로 할 수 있다
- **[Story]**: 해당 사용자 스토리(US1~US5)

---

## Phase 1: Setup

- [X] T001 패키지 자리 만들기: `src/qello_knowledge/embedding/__init__.py`, `src/qello_knowledge/adapters/workers_ai/__init__.py`, `tests/unit/embedding/__init__.py`, `tests/localdb/embedding/__init__.py`, `tests/fixtures/workers_ai/`, `tests/external/__init__.py`
- [X] T002 [P] `tests/unit/test_boundaries.py`: `RESTRICTED`에 `embedding`을 더하고 `ALLOWED_INTERNAL`에 `qello_knowledge.embedding`을 더해, `embedding/`이 표준 라이브러리·`domain`·`ports`·자기 자신만 가져오는지 검사한다(plan Structure Decision, SC-007). `embedding/`이 `adapters`를 가져오면 실패해야 한다

---

## Phase 2: Foundational

**목적**: 모든 스토리가 쓰는 타입·경계·가짜 구현·설정. 이 단계가 끝나야 스토리 테스트를 쓸 수 있다.

- [X] T003 [P] `src/qello_knowledge/domain/embedding.py`: data-model.md 1절 타입을 표준 라이브러리 dataclass·`StrEnum`으로 정의한다 — `ModelSpec`과 `MODELS = {"@cf/baai/bge-m3": ModelSpec(dimension=1024, max_input_tokens=8192, neurons_per_million_tokens=1075, bytes_per_token_estimate=3.5)}`, `EmbedPurpose`(`index`, `query`), `EmbedFailureKind`(`empty_input`, `no_origin`, `secret_blocked`, `input_too_long`, `transient`, `provider_quota`, `index_budget`, `bad_response`), `EmbedError(kind)`(`auth_config`, `no_active_index`, `usage_unavailable`), `EmbedInput(text, origin)`(`origin: tuple[str, str] | None`), `EmbedRequest(inputs, purpose, model_version, run_id, allow_partial=False)`, `EmbedItem`("`vector`와 `failure` 중 하나만 있다"를 `__post_init__`에서 검사), `RunSummary`, `EmbedResult`, `EmbedPreview`, `BudgetSettings`, `Reservation`, `DailyUsage`, `QueryUsage`, `PruneResult`, 상수 `HASH_RULE = "emb-hash-v1"`
- [X] T004 [P] `src/qello_knowledge/ports/embedder.py`: contracts/embedder.md의 `Embedder`(`embed`, `preview`), `EmbeddingProvider`(`embed_texts(model, texts) -> ProviderBatch`, 실패는 `ProviderFailure(kind, retry_after_seconds)`), `UsageLedger`(`reserve`, `settle`, `record`, `today`, `prune`)를 Protocol로 채운다. `ProviderBatch`·`ProviderFailure`도 이 파일에 둔다(domain 타입만 쓴다)
- [X] T005 [P] `src/qello_knowledge/ports/store.py`·`src/qello_knowledge/domain/store.py`: `Store.find_embeddings(refs: Sequence[EmbeddingRef]) -> dict[EmbeddingRef, tuple[float, ...]]` 추가(없는 키는 결과에 없음, research R-07). 기존 연산은 바꾸지 않는다
- [X] T006 [P] `src/qello_knowledge/embedding/hashing.py`: `input_hash(text) = "sha256:" + sha256(text.encode("utf-8")).hexdigest()`. 정규화하지 않는다(FR-009, R-07)
- [X] T007 [P] `src/qello_knowledge/embedding/estimate.py`: `estimated_tokens(text, model) = ceil(len(text.encode("utf-8")) / model.bytes_per_token_estimate)`, `estimated_neurons(texts, model)`, 계산 근거 `{bytes_total, bytes_per_token, neurons_per_million_tokens}` 반환(R-04, FR-023)
- [X] T008 [P] `src/qello_knowledge/embedding/fake.py`: `FakeEmbeddingProvider` — 텍스트 SHA-256을 시드로 1,024차원 단위 벡터를 만든다(같은 입력 → 같은 벡터). 호출 기록(`calls`), 호출마다 알려 줄 `neurons`(기본: estimate 값, `None` 지정 가능), 실패 주입(특정 텍스트 → `input_too_long`, n번째 호출 → `transient`/`provider_quota`/`auth_config`, 차원 틀린 응답 → `bad_response` 판정용) 지원(FR-006)
- [X] T009 [P] `tests/unit/fakes.py`: 메모리 `Store`에 `put_embedding`·`find_embedding`·`find_embeddings` 추가, 메모리 `InMemoryUsageLedger`(주입 시계, `reserve`가 "정산된 색인 사용량 + 정산 전 예약 예상량 + 이번 예상량 ≤ index_budget"이면 예약, `today()`는 UTC 날짜 기준) 추가
- [X] T010 `src/qello_knowledge/config/registry.py`: `QK_EMBED_DAILY_ALLOWANCE`(기본 `10000`), `QK_EMBED_INDEX_BUDGET`(기본 `5000`), `QK_EMBED_QUERY_RESERVE`(기본 `3000`) 추가. 비밀 아님, 진입점 `BOTH`, 규칙 "양의 정수"(R-11). `.env.example` 생성 결과(`config/example.py`)에 반영되는지 확인
- [X] T011 `src/qello_knowledge/config/check.py`: 교차 검사 "`QK_EMBED_INDEX_BUDGET + QK_EMBED_QUERY_RESERVE ≤ QK_EMBED_DAILY_ALLOWANCE`"를 보고에 더하고 어기면 실패로 판정(FR-017). 출력에는 숫자만 넣는다. `BudgetSettings.from_settings(...)` 변환 함수도 여기 또는 `embedding/service.py`에 둔다
- [X] T012 [P] `tests/unit/embedding/test_settings.py`: 기본값 10000/5000/3000 통과, `QK_EMBED_INDEX_BUDGET=8000`이면 설정 검사 실패, 0·음수·숫자 아님은 `INVALID`(US4 AS6)
- [X] T013 [P] `tests/unit/embedding/test_estimate.py`: 한국어·영어·빈 문자열의 예상 토큰, 예상 Neurons = 토큰 × 1075 / 1e6, 근거 필드 값(FR-023)

**Checkpoint**: 타입·경계·가짜 구현·설정이 준비됐다. `uv run pytest tests/unit` 통과.

---

## Phase 3: User Story 1 - 텍스트 묶음을 정해진 모델의 벡터로 바꾼다 (P1) 🎯 MVP

**Goal**: `EmbeddingService.embed`가 순서·차원·모델 버전을 지키고, 자르지 않으며, 실패를 항목별로 구분한다.

**Independent Test**: 가짜 제공자로 텍스트 3개 → 1,024차원 벡터 3개, 모델 버전 붙음, 결과에 제공자 타입 없음.

### Tests (US1)

- [X] T014 [P] [US1] `tests/unit/embedding/test_service_basic.py`: AS1(순서·차원 1024·`model_version`), AS5(빈 문자열·공백뿐 → `empty_input`, 제공자 호출 0건), FR-005(색인용 `origin=None` → `no_origin`, 호출 0건; 가짜 토큰을 이어 붙여 만든 텍스트 → `secret_blocked`이고 같은 묶음의 다른 텍스트는 정상 처리, 제공자에 간 텍스트에 가짜 토큰 없음; 해당 출처의 오탐 예외가 있으면 통과; 질의용은 `origin=None`이어도 검사하고 예외는 적용하지 않음; 로그에 텍스트·맞은 문자열 없음, SC-006), `MODELS`에 없는 모델 → `EmbedError(auth_config)`
- [X] T015 [P] [US1] `tests/unit/embedding/test_service_limits.py`: AS2 — 예상 토큰이 6,144를 넘는 텍스트는 단독 요청으로 간다, 여러 텍스트 요청이 `input_too_long`이면 반으로 나눠 원인만 `input_too_long`이고 나머지는 벡터를 받는다, 잘린 벡터 저장 0건(SC-004). 제공자에 자르기 옵션을 넘기지 않는다
- [X] T016 [P] [US1] `tests/unit/embedding/test_service_failures.py`: AS3(`transient` 2회 뒤 성공 → 벡터, 3회 초과 → `transient`, `Retry-After` 대기는 주입 시계로 확인), AS4(`provider_quota` → 재시도 없음, 이후 요청 미전송, FR-020), `auth_config` → `EmbedError`, 차원 1023 응답 → `bad_response`이고 저장 0건
- [X] T017 [P] [US1] `tests/unit/embedding/test_batching.py`: 묶음 최대 32개·예상 토큰 합 32,768로 나뉘고 결과 순서가 입력 순서와 같다(R-06, Edge Cases)
- [X] T018 [P] [US1] `tests/contract/embedding_provider_contract.py`·`tests/contract/test_embedding_providers.py`: contracts/embedder.md "제공자 계약 테스트" 1~5를 함수 묶음으로 만들고 `FakeEmbeddingProvider`에 돌린다. REST 제공자 재생 대상은 T022 뒤에 추가한다

### Implementation (US1)

- [X] T019 [US1] `src/qello_knowledge/embedding/batching.py`: 묶음 나누기(32개·32,768토큰), 큰 텍스트(예상 토큰 > `max_input_tokens × 0.75`) 단독 배치, `input_too_long` 묶음 반으로 나누기 순서 생성(R-05·R-06)
- [X] T020 [US1] `src/qello_knowledge/embedding/service.py`: `EmbeddingService(provider, store, ledger, settings, policy, clock, retry_policy, sleep)`의 `embed` 골격 — `policy`는 `security.policy.SecurityPolicy`. contracts/embedder.md 처리 순서 1·2·4단계의 전송 직전 검사(`security.send_gate.check_outgoing`, research R-13)·6·8단계와 7단계의 제공자 호출·실패 분류·재시도(`sources/retry.py`의 `next_delay`, `domain/source_config.RetryPolicy` 재사용), 차원·개수 검사. 캐시(3·4단계)와 예산(5·7단계 예약)은 US2·US4에서 채운다. 사용량 기록 호출 자리는 `ledger.settle`/`record`로 둔다
- [X] T021 [P] [US1] `tests/fixtures/workers_ai/`: 합성 응답 사례 JSON — 200(벡터 2개, 헤더 `cf-ai-neurons: 0.01`), 200 헤더 없음, 200 차원 불일치, 400 `errors[].code=3030`, 429 `code=3036`, 429 그 밖(`Retry-After: 2`), 500, 401. 실제 응답·토큰·계정 ID를 넣지 않는다(R-14)
- [X] T022 [US1] `src/qello_knowledge/adapters/workers_ai/rest.py`: `WorkersAiRestProvider(account_id, api_token: SecretValue, transport)` — `POST /client/v4/accounts/{account}/ai/run/{model}`에 `{"text": [...]}`(자르기 옵션 없음), `urllib.request` 기본 전송과 테스트용 전송 주입, research R-09 표대로 `ProviderBatch`/`ProviderFailure` 변환, `cf-ai-neurons` 헤더 파싱(없으면 `None`). 토큰은 이 파일 안에서만 `reveal()`하고 예외 문구에 토큰·계정 ID를 넣지 않는다(FR-007)
- [X] T023 [US1] `tests/contract/test_embedding_providers.py`: T021 사례를 재생하는 전송으로 `WorkersAiRestProvider`에 계약 묶음을 돌린다. 예외 `str()`에 토큰 문자열이 없는지 확인

**Checkpoint**: 외부 호출 없이 US1 수용 시나리오 1~5가 통과한다.

---

## Phase 4: User Story 2 - 변경이 없는 텍스트는 다시 임베딩하지 않는다 (P1)

**Goal**: 색인용 텍스트는 (입력 해시, 모델 버전) 캐시를 먼저 보고, 새 벡터만 저장한다.

**Independent Test**: 같은 10개를 두 번 임베딩 → 두 번째 제공자 호출 0건, 같은 벡터(SC-001).

### Tests (US2)

- [X] T024 [P] [US2] `tests/unit/embedding/test_service_cache.py`: AS1(두 번째 실행 호출 0건·같은 벡터·`cached=true`, SC-001), AS2(1개만 바뀐 묶음 → 그 1개만 전송), AS3(다른 `model_version` → 미적중), AS4(묶음 안 같은 텍스트 2개 → 전송 1회, 두 자리 같은 벡터, `deduplicated=1`), AS5(질의용은 `put_embedding` 0건, FR-012), 묶음 중간 `provider_quota`에도 그 전 벡터는 저장돼 있다(FR-011)
- [X] T025 [P] [US2] `tests/localdb/embedding/test_find_embeddings.py`: `find_embeddings`가 있는 키만 돌려주고, 같은 해시·다른 모델 버전은 없다, 빈 목록은 DB를 부르지 않는다

### Implementation (US2)

- [X] T026 [US2] `src/qello_knowledge/adapters/postgres/store.py`: `PostgresStore.find_embeddings` — `(input_hash, model_version)` 목록을 한 질의로 조회(`unnest` 두 배열 JOIN)
- [X] T027 [US2] `src/qello_knowledge/embedding/service.py`: 처리 순서 3·4단계(색인용 캐시 조회, 묶음 안 중복 제거)와 성공 벡터 `put_embedding`(색인용만, 요청 단위로 바로 저장)을 채운다. `RunSummary.cache_hits`·`deduplicated` 집계

**Checkpoint**: US1·US2 단위 테스트와 `test_find_embeddings.py` 통과. 1.G 완료 조건 "변경이 없는 재동기화에서 임베딩 호출 0건"의 임베딩 쪽이 준비됐다.

---

## Phase 5: User Story 3 - 모든 외부 호출의 사용량을 남긴다 (P1)

**Goal**: 외부 호출마다 원문 없이 사용량을 기록하고, 하루(UTC) 합계·용도별 합계를 조회한다.

**Independent Test**: 가짜 제공자가 알려 준 사용량 합 = 기록 합계(SC-003), 헤더 없는 호출은 `measured=false`.

### Tests (US3)

- [X] T028 [P] [US3] `tests/localdb/embedding/test_usage_record.py`: AS1(행 필드: `occurred_at`, `usage_day`, `purpose`, `run_id`, `model_version`, `input_count`, `input_bytes`, `estimated_neurons`, `neurons`, `measured`, `state='settled'`, `outcome`), AS3(실패 호출도 `neurons=0`, `measured=false`, `outcome='input_too_long'`), AS4(`qk.embedding_usage_today`의 `total`·`index_used`·`query_used`·`index_remaining`), AS5(모든 칼럼에 입력 텍스트 문자열이 없다), 체크 제약 "`state = 'settled'`이면 `neurons`, `measured`, `outcome`이 NOT NULL"·"`purpose = 'query'`이면 `state = 'settled'`"을 직접 `INSERT`로 위반해 실패 확인
- [X] T029 [P] [US3] `tests/localdb/embedding/test_day_boundary.py`: `occurred_at`이 `23:59:59+00`과 `00:00:00+00`인 기록이 다른 `usage_day`로 집계된다(US4 AS4의 저장소 쪽)
- [X] T030 [P] [US3] `tests/unit/embedding/test_service_usage.py`: 가짜 제공자 `neurons` 값의 합 = 메모리 장부 합(SC-003), `neurons=None` 응답 → 추정값·`measured=false`(FR-014), AS2(캐시만으로 끝난 요청 → 장부 행 0건, `RunSummary.neurons=0`·`cache_hits` 기록), 장부 `settle`이 예외를 내면 `EmbedError(usage_unavailable)`이고 그 전 벡터는 저장돼 있다(Edge Cases)

### Implementation (US3)

- [X] T031 [US3] `src/qello_knowledge/adapters/postgres/migrations/0003_embedding_usage.sql`: data-model.md 2절 테이블 2개를 글자 그대로 만든다 — `qk.embedding_usage`(`usage_day` date NOT NULL, `purpose` "`index` 또는 `query`", `input_count`·`input_bytes` "≥ 0", `estimated_neurons` numeric(12,2) NOT NULL ≥ 0, `neurons` "정산 전 NULL. 정산 뒤 ≥ 0", `state` "`reserved` 또는 `settled`", `outcome` "`ok`, `input_too_long`, `transient`, `provider_quota`, `bad_response`, `auth_config`", 위 두 체크 제약, 인덱스 `(usage_day, purpose)`), `qk.embedding_usage_daily`(PK `(usage_day, purpose, model_version)`). 함수 `qk.embedding_record`, `qk.embedding_settle`("이미 정산된 행이면 아무것도 안 한다"), `qk.embedding_usage_today`(정산 행은 `neurons`, 예약 행은 `estimated_neurons` 합산). `qk.embedding_reserve`·`qk.embedding_usage_prune`은 US4·폴리시에서 같은 파일에 더한다(첫 PR에서 파일이 확정되도록 한 브랜치에서 끝낸다)
- [X] T032 [US3] `src/qello_knowledge/adapters/postgres/usage.py`: `PostgresUsageLedger(conn_factory, settings)` — `record`·`settle`·`today`가 SQL 함수를 한 번씩 부르고 `jsonb`를 domain 타입으로 바꾼다. DB 오류는 `EmbedError(usage_unavailable)`로 바꾸고 접속 정보를 문구에 넣지 않는다
- [X] T033 [US3] `src/qello_knowledge/embedding/service.py`: 요청마다 `settle`(색인)·`record`(질의) 호출, `input_bytes`·추정값 계산, `RunSummary.neurons`·`estimated_neurons`·`failures` 집계(FR-013~015)
- [X] T034 [US3] `src/qello_knowledge/indexer/cli.py`: `qk-index usage [--json]` — contracts/cli.md 출력 형식, 종료 코드 0/1/2

**Checkpoint**: 사용량 기록과 조회가 끝났다. `QK_REQUIRE_LOCALDB=1 uv run pytest tests/localdb/embedding` 통과.

---

## Phase 6: User Story 4 - 색인이 질의응답 몫을 쓰지 않게 일일 예산을 지킨다 (P1)

**Goal**: 색인용 요청마다 예산을 예약하고, 넘으면 호출하지 않는다. 질의는 막지 않는다.

**Independent Test**: 색인 예산 10 Neurons로 큰 색인 → 예산 안에서 멈추고 `index_budget`, 같은 날 질의는 정상(SC-002).

### Tests (US4)

- [X] T035 [P] [US4] `tests/unit/embedding/test_service_budget.py`: AS1(그날 색인 사용량 = 예산 → 색인 요청 호출 0건, 전 항목 `index_budget`), AS2(같은 상태에서 질의 요청 정상), AS3(`allow_partial=True`이면 예산 안 앞부분만 처리하고 나머지 `index_budget`, 처리분은 캐시에 저장), AS4(주입 시계를 00:00 UTC 뒤로 옮기면 새 예산), AS5(질의 사용량이 `query_reserve`를 넘으면 `RunSummary.warnings`에 경고, 요청은 성공), 제공자 `provider_quota`인데 장부상 남은 예산이 있으면 차이 경고(FR-020)
- [X] T036 [P] [US4] `tests/localdb/embedding/test_reserve_concurrency.py`: 두 스레드가 같은 날 예산 100에 예상 60짜리 예약을 동시에 하면 하나만 `granted`, 정산 전 예약은 예상량으로 합산, 실제 사용량이 예상보다 클 때 초과 폭 ≤ 요청 하나의 (실제 − 예상)(FR-021, SC-002)

### Implementation (US4)

- [X] T037 [US4] `src/qello_knowledge/adapters/postgres/migrations/0003_embedding_usage.sql`: `qk.embedding_reserve(run_id, model_version, input_count, input_bytes, estimated, index_budget) RETURNS jsonb` — 그날(UTC) 키로 `pg_advisory_xact_lock`, "정산된 색인 사용량 + 정산 전 예약 예상량 + 이번 예상량 ≤ index_budget"이면 `reserved` 행 삽입 후 `{granted: true, reservation_id, index_used, index_remaining}`, 아니면 행 없이 `{granted: false, ...}`(R-08)
- [X] T038 [US4] `src/qello_knowledge/adapters/postgres/usage.py`: `reserve` 구현(거부면 `None`)
- [X] T039 [US4] `src/qello_knowledge/embedding/service.py`: 색인 요청 직전 `reserve`, 거부되면 그 요청과 이후 요청 전부 `index_budget`, `provider_quota`면 남은 색인 중단, 질의 사용량 예비분 초과 경고(FR-018~021)

**Checkpoint**: P1 스토리 4개가 끝났다. SC-001~004·SC-006·SC-007을 확인할 수 있다.

---

## Phase 7: User Story 5 - 색인을 돌리기 전에 예상 사용량을 본다 (P2)

**Goal**: 외부 호출 없이 예상 사용량·실행 가능 여부를 보고, 예산 초과면 기본적으로 실행하지 않는다.

**Independent Test**: 100개 중 60개 캐시 → `to_embed=40`, 호출 0건, 예상값과 계산 근거가 나온다.

### Tests (US5)

- [X] T040 [P] [US5] `tests/unit/embedding/test_preview.py`: AS1(`requested=100`, `cache_hits=60`, `to_embed=40`, `estimated_neurons`, `index_remaining`, `runnable`, 제공자 호출 0건·예약 0건·저장 0건), AS2(예상 > 남은 예산 → `runnable=false`, 필요량·남은 양), AS3(`runnable=false`이고 `allow_partial=False`인 `embed` → 호출 0건, 전 항목 `index_budget`), AS4(예상 토큰 > 8192 텍스트 → `over_limit_expected=1`), 묶음 안 중복은 `deduplicated`로 센다

### Implementation (US5)

- [X] T041 [US5] `src/qello_knowledge/embedding/service.py`: `preview(request) -> EmbedPreview`(처리 순서 1~5단계를 부수 효과 없이 계산, `ledger.today()`로 남은 예산), `embed`가 첫 외부 호출 전에 같은 계산으로 FR-024 기본 동작을 지킨다

**Checkpoint**: 모든 스토리가 끝났다.

---

## Phase 8: Polish & Cross-Cutting

- [X] T042 [P] `tests/localdb/embedding/test_prune.py`: 91일 전 기록이 `qk.embedding_usage_daily`로 옮겨지고(`neurons`, `calls`, `estimated_calls`) 호출별 행이 지워진다, 89일 전 기록은 남는다, 두 번째 실행 `{days_rolled_up: 0, rows_deleted: 0}`, 청크·벡터 행 수 불변(FR-025)
- [X] T043 `src/qello_knowledge/adapters/postgres/migrations/0003_embedding_usage.sql`·`src/qello_knowledge/adapters/postgres/usage.py`·`src/qello_knowledge/indexer/cli.py`: `qk.embedding_usage_prune(retention_days int DEFAULT 90)`(날짜 단위 upsert 후 삭제, 한 트랜잭션, R-13), `UsageLedger.prune`, `qk-index usage prune [--retention-days 90]`
- [X] T044 [P] `tests/unit/indexer/test_cli_usage.py`: `qk-index usage`·`usage --json`·`usage prune`이 메모리 장부로 contracts/cli.md 형식과 종료 코드를 지킨다
- [X] T045 [P] `tests/external/test_workers_ai_embedding.py`(`@pytest.mark.external`): 합성 텍스트 20개(한국어 10, 영어·코드 10)를 실제 bge-m3로 임베딩해 차원·순서를 확인하고, 미리 보기 예상 Neurons와 `cf-ai-neurons` 합의 차이를 출력한다. 실행 전 예상 사용량(약 6 Neurons)을 파일 머리 주석에 적는다. 기본 검증에서 돌리지 않는다
- [ ] T046 사람 승인 뒤 T045를 한 번 실행하고 결과(텍스트 수, 언어 비중, 바이트 합, 예상·측정 Neurons, 차이 %, 모델, 실행일)를 PR 본문 또는 `docs/sdd/research/` 아래 기록에 남긴다(SC-005, C-13). 차이가 ±20%를 넘으면 `bytes_per_token_estimate` 수정은 별도 커밋으로 한다. 승인이 없으면 `BLOCKED`로 보고한다
- [X] T047 [P] `README.md` 또는 `docs/` 운영 안내: `qk-index usage`·`usage prune`, `QK_EMBED_*` 설정 3개, 하루 경계(00:00 UTC = 한국 시간 09:00)
- [X] T048 quickstart.md 1~3절과 AGENTS.md 7절 기본 검증 전체 실행: `python scripts/preflight.py`, `git diff --check`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run qk-migrate`(두 번째 `applied=0`), `QK_REQUIRE_LOCALDB=1 uv run pytest`

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 → 스토리 단계. Phase 2(T003~T013)가 끝나야 스토리 테스트를 쓸 수 있다.
- US1(T014~T023)이 `EmbeddingService` 골격(T020)을 만든다. US2·US3·US4·US5는 모두 T020 뒤에 `service.py`를 채운다.
- `service.py`를 고치는 작업(T020 → T027 → T033 → T039 → T041)은 같은 파일이라 순서대로 한다.
- `0003_embedding_usage.sql`을 고치는 작업(T031 → T037 → T043)도 순서대로 한다. 한 브랜치 안에서 끝내 마이그레이션 체크섬이 병합 뒤 바뀌지 않게 한다(QK-STO-001 FR-017).
- US2의 DB 쪽(T025·T026)은 Phase 2 뒤 독립이다.
- US3(T028~T034)은 T020 뒤. US4(T035~T039)는 US3의 테이블(T031)·장부(T032) 뒤.
- US5(T040·T041)는 US2(캐시)·US4(예산) 뒤.
- Polish: T042·T043은 US3 뒤, T044는 T034·T043 뒤, T045는 T022 뒤, T046은 T045와 사람 승인 뒤, T048은 마지막.

### 스토리 완료 순서

```text
Setup → Foundational → US1 → US2 ─────────┐
                          └→ US3 → US4 ──┴→ US5 → Polish
```

## Parallel Opportunities

- Phase 2: T003·T004·T005·T006·T007·T008·T009 동시(파일이 다르다). 그다음 T010 → T011, T012·T013 동시.
- US1: T014·T015·T016·T017·T018 동시, T021은 T019·T020과 동시.
- US2 T025·T026(DB)은 US1 구현과 동시에 할 수 있다.
- US3 테스트 T028·T029·T030 동시.
- US4 테스트 T035·T036 동시.
- Polish T042·T044·T045·T047 동시.

### 예시: US1 테스트를 한 번에 시작

```text
T014 test_service_basic.py
T015 test_service_limits.py
T016 test_service_failures.py
T017 test_batching.py
T018 embedding_provider_contract.py
```

## Implementation Strategy

1. **MVP**: Setup → Foundational → US1 → US2. 가짜 제공자와 REST 제공자로 벡터를 만들고 캐시로 재동기화 호출 0건(SC-001)을 확인한다.
   QK-SYN-001·QK-RET-001이 가짜 제공자로 개발을 시작할 수 있다.
2. **비용 안전**: US3 → US4. 사용량 기록과 예산 예약으로 SC-002·SC-003을 닫는다. **실제 팀 자료의 첫 색인(QK-SYN-001)은 이 단계가 끝난 뒤에만 돌린다.**
3. **실행 전 가드**: US5로 AGENTS.md 3.5의 "실행 전 예상 사용량"을 자동화한다.
4. **실측**: T046(사람 승인)으로 SC-005를 닫는다. 승인 전에는 `BLOCKED`로 남긴다.

## Requirement Coverage

| 요구사항 | 작업 |
| --- | --- |
| FR-001~004 | T003, T004, T014~T017, T019, T020, T022 |
| FR-005 | T003, T014 |
| FR-006 | T008, T018 |
| FR-007 | T022, T023 (Workers 바인딩은 QK-RET-001, research R-10) |
| FR-008~012 | T005, T006, T024~T027 |
| FR-013~016 | T028~T034 |
| FR-017 | T010~T012 |
| FR-018~021 | T035~T039 |
| FR-022~024 | T007, T013, T040, T041 |
| FR-025 | T042, T043 |
| SC-001 | T024 |
| SC-002 | T035, T036 |
| SC-003 | T028, T030 |
| SC-004 | T015 |
| SC-005 | T045, T046(사람 승인) |
| SC-006 | T014 |
| SC-007 | T002, T018, T023 |
