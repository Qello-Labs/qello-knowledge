---
description: "QK-STO-001 구현 작업 목록"
---

# Tasks: QK-STO-001 저장 스키마·마이그레이션·검색 질의

**Input**: `specs/QK-STO-001-storage-schema-search/`의 plan.md, spec.md, research.md, data-model.md, contracts/store.md, contracts/cli.md, quickstart.md

**Tests**: 포함한다. 명세의 수용 시나리오와 C-12(수용 기준은 검증으로 닫는다)가 자동 테스트를 요구한다. 테스트를 먼저 쓰고 실패를 확인한 뒤 구현한다.

**Organization**: 사용자 스토리별 단계로 나눈다. 우선순위는 US1·US2·US3(P1) → US4·US5(P2) → US6(P3)이다.
모든 DB 테스트는 `localdb` 표시를 붙이고 세션 전용 데이터베이스 `qk_test_<무작위>`에서만 돈다(research R-10). 공유 `postgres` 데이터베이스는 건드리지 않는다.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 다른 파일을 다루고 미완료 작업에 기대지 않아 병렬로 할 수 있다
- **[Story]**: 해당 사용자 스토리(US1~US6)

---

## Phase 1: Setup

**Purpose**: 의존성과 패키지 자리 만들기

- [x] T001 `pyproject.toml`: `[project.optional-dependencies] postgres = ["psycopg[binary]>=3.2"]` 추가(런타임 `dependencies`는 비워 둔다, research R-09), `[project.scripts]`에 `qk-migrate = "qello_knowledge.adapters.postgres.migrate:main"` 추가, `uv lock`으로 `uv.lock` 갱신
- [x] T002 [P] 패키지 자리: `src/qello_knowledge/adapters/postgres/__init__.py`, `src/qello_knowledge/adapters/postgres/migrations/`(패키지 데이터로 포함되는지 `uv build` 산출물에서 확인), `tests/unit/store/__init__.py`, `tests/localdb/store/__init__.py`

---

## Phase 2: Foundational

**Purpose**: 모든 스토리가 쓰는 도메인 타입, 경계, 연결, 기본 스키마, 테스트 DB. 끝나야 스토리 작업을 시작한다

- [x] T003 [P] `src/qello_knowledge/domain/store.py`: contracts/store.md 타입 표의 dataclass(`ArtifactRecord`, `ChunkInput`, `EmbeddingRef`, `SearchFilter`, `Provenance`, `SearchHit`, `SearchResult`, `NeighborResult`, `StoreUsage`)와 `ReplaceOutcome`(`"replaced" | "unchanged"`), 오류 `InvalidRecord`·`StoreUnavailable`·`StoreError`, 상수 `EMBEDDING_DIMENSION = 1024`, `TOP_N_LIMIT = 50`. 표준 라이브러리만 쓴다(QK-FND-001 R-04)
- [x] T004 [P] `src/qello_knowledge/ports/store.py`: `Store` Protocol에 contracts/store.md 연산 10개(`upsert_artifact`, `replace_chunks`, `mark_deleted`, `put_embedding`, `find_embedding`, `search_vector`, `search_keyword`, `chunk_neighbors`, `trace_chunk`, `usage`)를 domain 타입으로 정의
- [x] T005 `src/qello_knowledge/adapters/postgres/connection.py`: `DATABASE_URL`(없으면 로컬 개발 DB 기본값)로 psycopg 연결을 열고, `devtools.db.is_local_target`으로 `local`/`remote`를 판정한다. 연결 실패는 `StoreUnavailable`로 바꾸고 메시지에 호스트·사용자·비밀번호를 넣지 않는다
- [x] T006 `src/qello_knowledge/adapters/postgres/migrations/0001_initial_schema.sql`: data-model.md 그대로 `qk` 스키마와 테이블 4개(`schema_migration`은 실행기가 만든다). 제약을 글자 그대로 넣는다 — `index_version.dimension` "`= 1024`", `status` "`ready`·`active`·`archived` 중 하나", 활성 하나는 "부분 고유 인덱스 `ON ((true)) WHERE status = 'active'`"; `artifact` "`(source_kind, source_id)` 고유", `source_url`·`source_version` "NOT NULL, 빈 문자열 금지", `status` "`active`·`archived`·`deleted`, 기본 `active`", `access_scope` "NULL 허용. NULL은 미확인"; `embedding.vector` "`vector(1024)`", "`(input_hash, model_version)` 고유", HNSW `vector_cosine_ops`; `chunk.locator` "NOT NULL, `{}` 금지", `ordinal` "`>= 0`", "`(artifact_id, index_version, ordinal)` 고유", PGroonga 인덱스(`search_text`); `schema_migration` "`version`별 `success` 행은 하나 이하". `CREATE EXTENSION IF NOT EXISTS vector, pgroonga` 포함
- [x] T007 `src/qello_knowledge/adapters/postgres/migrate.py` 핵심: 마이그레이션 파일 목록 읽기(`NNNN_<설명>.sql`, 번호 순), SHA-256 체크섬, `pg_advisory_lock`, `qk` 스키마와 `qk.schema_migration`을 적용 전에 `IF NOT EXISTS`로 만들기(첫 마이그레이션 실패도 기록하려고), 성공 기록 없는 파일을 하나씩 트랜잭션 하나로 적용하고 `success` 기록(research R-08). 재적용·체크섬·실패·파괴적 표시는 US3에서 채운다
- [x] T008 `tests/localdb/store/conftest.py`: 세션 fixture가 로컬 DB에 `qk_test_<무작위>`를 만들고 `migrate`로 전체 적용, 세션 끝에 지운다. 테스트마다 `TRUNCATE ... RESTART IDENTITY CASCADE`(`schema_migration` 제외). 합성 데이터 빌더(`make_artifact`, `make_chunks`, 고정 시드 1,024차원 벡터, 활성 인덱스 `v1`·보관 인덱스 `v0` 행)와 `PostgresStore` fixture
- [x] T009 [P] `tests/unit/test_boundaries.py`가 새 `domain/store.py`·`ports/store.py`에서도 통과하는지 확인한다(수정 불필요하면 그대로 둔다)

**Checkpoint**: 빈 DB에 스키마가 올라가고 테스트 DB가 준비된다

---

## Phase 3: User Story 1 - 모든 청크를 원본 위치로 되돌릴 수 있게 저장한다 (P1) 🎯 MVP

**Goal**: 원본 자료·청크·임베딩을 저장하고 어떤 청크든 출처·버전·규칙 버전·모델 버전으로 되짚는다

**Independent Test**: 원본 자료 1개·청크 5개를 저장하고 청크마다 출처 6항목을 조회한다. 출처 누락·차원 불일치는 거부된다

### Tests (US1)

- [x] T010 [P] [US1] `tests/unit/store/test_domain.py`: `ChunkInput`·`ArtifactRecord`의 출처 필드(원본 링크, 원본 버전, 위치)가 비면 `InvalidRecord`, 벡터 길이가 1,024가 아니면 `InvalidRecord`(어댑터 입력 검증 함수 단위)
- [x] T011 [P] [US1] `tests/localdb/store/test_provenance.py`: AS1 — 청크 조회 결과에 원본 링크·원본 버전·위치·청킹 규칙 버전·임베딩 모델 버전·인덱스 버전이 모두 있다(SC-001, 무작위 청크 전부). AS2 — 출처 누락 청크 저장 거부(경계 검증과 DB 제약 둘 다: 경계를 우회한 직접 `INSERT`도 실패). AS3 — 3차원 벡터 저장 거부

### Implementation (US1)

- [x] T012 [US1] `src/qello_knowledge/adapters/postgres/store.py`: `PostgresStore.upsert_artifact`, `trace_chunk`(`(source_kind, source_id)` 기준 `INSERT ... ON CONFLICT DO UPDATE`, artifact id 반환)와 입력 검증
- [x] T013 [US1] `src/qello_knowledge/adapters/postgres/store.py`: `put_embedding`(`ON CONFLICT DO NOTHING`)과 청크 저장 내부 함수(임베딩 참조를 id로 풀기). DB 오류 `CheckViolation`·`DataException`은 `InvalidRecord`로 바꾼다

**Checkpoint**: US1 테스트 통과

---

## Phase 4: User Story 2 - 권한·상태·버전 조건을 지킨 벡터 검색과 키워드 검색 (P1)

**Goal**: 노출 조건을 질의 안에 넣은 두 검색 함수와 주변 청크 조회

**Independent Test**: 팀 공용·미확인·제한, 활성·삭제, 활성·보관 버전 청크를 섞고 두 검색을 실행해 허용 청크만 나오는지 본다

### Tests (US2)

- [x] T014 [P] [US2] `tests/localdb/store/test_search_filters.py`: AS1(미확인 범위 제외), AS2(삭제 자료 제외, 두 검색 모두), AS3(보관 인덱스 버전만 있는 청크 제외), 제한 범위 제외, AS6(`source_kinds` 필터), AS7(결과마다 `rank`·`score`·`chunk_id`·출처, `rank`는 1부터), 섞인 검증 세트에서 금지 청크 0건(SC-002)
- [x] T015 [P] [US2] `tests/localdb/store/test_keyword.py`: AS4 — 함수명(`retryPayment` 등), URL 경로(`/payments/{id}/cancel` 등), snake_case(`max_retry_count` 등) 각 5개 이상을 원형으로 검색해 상위 20건 안에 100%(SC-007). AS5 — 한국어 단어("재시도", "개발" 등). 특수 문자 `(a OR "b`가 오류 없이 처리. 빈 문자열·공백뿐인 검색어는 질의 없이 `hits=()`
- [x] T016 [P] [US2] `tests/localdb/store/test_no_active_index.py`: 활성 인덱스가 없으면 `status="no_active_index"`·`hits=()`이고 예외가 없다. `top_n=500`은 50건 이하로 잘린다(FR-010). 데이터 60건으로 확인
- [x] T017 [P] [US2] `tests/localdb/store/test_neighbors.py`: `chunk_neighbors`가 같은 자료·같은 인덱스 버전의 앞뒤 청크와 상위 절(제목 경로가 접두인 청크)을 돌려주고, 노출 조건을 똑같이 건다(삭제 자료 청크 id로 부르면 `None`)

### Implementation (US2)

- [x] T018 [US2] `src/qello_knowledge/adapters/postgres/migrations/0002_search_functions.sql`: `qk.visible_access_scope()`(`'team'`), `qk.search_vector(query vector(1024), top_n int, source_kinds text[], artifact_kinds text[]) RETURNS jsonb`(함수 속성 `SET hnsw.iterative_scan = relaxed_order`, `score = 1 - (vector <=> query)`), `qk.search_keyword(query text, ...)`(`search_text &@~ pgroonga_query_escape(query)`, `pgroonga_score(tableoid, ctid)`), `qk.chunk_neighbors(chunk_id bigint, before int, after int) RETURNS jsonb`. 모두 `least(greatest(top_n, 1), 50)`, 노출 조건은 `WHERE`에서만, 반환 키는 contracts/store.md `SearchHit`·`Provenance` 필드 이름(research R-03~R-06)
- [x] T019 [US2] `src/qello_knowledge/adapters/postgres/store.py`: `search_vector`·`search_keyword`·`chunk_neighbors`가 SQL 함수를 부르고 `jsonb`를 domain 타입으로 바꾼다. 빈 검색어는 DB를 부르지 않는다. 결과를 다시 거르지 않는다

**Checkpoint**: US1·US2로 저장·검색 MVP 완료

---

## Phase 5: User Story 3 - 스키마 변경을 버전 순서대로, 다시 실행해도 안전하게 적용 (P1)

**Goal**: 재적용 0건, 체크섬 불일치 중단, 실패 시 부분 반영 없음, 파괴적 변경 보호, CI 검사

**Independent Test**: 빈 DB에 두 번 적용해 두 번째가 `applied=0`, 실패하는 마이그레이션 뒤 스키마가 그대로인지 본다

### Tests (US3)

- [x] T020 [P] [US3] `tests/unit/store/test_migrate_files.py`: 파일 이름 파싱(번호·설명), 번호 중복·형식 오류 거부, 체크섬 계산, 첫 줄 `-- qk:destructive` 인식
- [x] T021 [P] [US3] `tests/localdb/store/test_migrate.py`(임시 마이그레이션 디렉터리와 별도 `qk_test_<무작위>` DB 사용): AS1(빈 DB 적용 후 기록에 버전·시각·`success`), AS2(재적용 `applied=0`, SC-004), AS3(두 번째 문장에서 실패하는 파일 → 첫 문장 변경도 없음, `failed` 기록, 종료 코드 1), 적용된 파일 내용을 바꾸면 종료 코드 2로 아무것도 적용 안 함, AS4(`remote`로 판정되는 대상 + 파괴적 파일 → `--allow-destructive` 없이는 종료 코드 3. 원격 판정은 함수 주입으로 흉내 내고 실제 원격에는 연결하지 않는다)

### Implementation (US3)

- [x] T022 [US3] `src/qello_knowledge/adapters/postgres/migrate.py`: 체크섬 불일치 중단, 실패 시 롤백 후 별도 트랜잭션에 `failed`·오류 분류 기록(접속 정보 제외), 파괴적 표시 보호, `--dry-run`, 출력 형식과 종료 코드 0~4(contracts/cli.md), `main(argv)`
- [x] T023 [US3] `.github/workflows/ci.yml` `test` job: `Start local DB` 뒤에 `uv run qk-migrate`를 두 번 실행하고 두 번째 출력에 `applied=0`이 없으면 실패하는 단계 추가(research R-11, FR-020)

**Checkpoint**: 마이그레이션 계약 완료

---

## Phase 6: User Story 4 - 문서 하나의 청크를 한 번에 교체 (P2)

**Goal**: 원자적·멱등·동시 실행 안전한 교체와 삭제 상태 전환

**Independent Test**: 청크 5개 문서를 3개로 바꾸며 실패를 넣고, 실패 뒤 5개·재실행 뒤 3개가 보이는지 본다

### Tests (US4)

- [x] T024 [P] [US4] `tests/localdb/store/test_replace.py`: AS1(5개 → 3개, 다른 문서 청크 불변), AS2·SC-003(마지막 청크 위치를 `{}`로 줘서 제약 위반 → 다른 연결의 검색 결과가 교체 전과 같고 `InvalidRecord`), AS3(같은 요청 두 번째는 `unchanged`, 행 수 동일), AS4(두 스레드가 같은 문서를 동시에 교체 → 한쪽 묶음만 남고 섞이지 않음), 교체 도중 다른 연결은 이전 묶음만 본다(첫 트랜잭션을 잠시 붙잡는 방식)
- [x] T025 [P] [US4] `tests/localdb/store/test_mark_deleted.py`: `mark_deleted` 직후 두 검색 모두에서 해당 자료 청크가 빠지고, 다시 불러도 오류가 없다(FR-014)

### Implementation (US4)

- [x] T026 [US4] `src/qello_knowledge/adapters/postgres/store.py`: `replace_chunks` — 트랜잭션 하나에서 `SELECT ... FOR UPDATE`, `(source_version, chunk_set_hash)`가 같으면 `unchanged`, 다르면 해당 인덱스 버전 청크 삭제 → 새 청크 삽입 → `artifact.source_version`·`chunk_set_hash`·`updated_at` 갱신(research R-07). `chunk_set_hash`는 청크 입력을 정렬된 JSON으로 직렬화한 SHA-256
- [x] T027 [US4] `src/qello_knowledge/adapters/postgres/store.py`: `mark_deleted`

**Checkpoint**: 교체 계약 완료

---

## Phase 7: User Story 5 - 같은 임베딩 입력의 벡터를 다시 쓴다 (P2)

**Goal**: (입력 해시, 모델 버전)으로 저장된 벡터 조회

**Independent Test**: (H, M) 저장 뒤 같은 키는 같은 벡터, 모델 버전만 다르면 `None`

- [x] T028 [P] [US5] `tests/localdb/store/test_embedding_reuse.py`: AS1(같은 벡터, 부동소수 오차 허용), AS2(`None`), 같은 키로 두 번 `put_embedding`해도 행 하나
- [x] T029 [US5] `src/qello_knowledge/adapters/postgres/store.py`: `find_embedding`(벡터 텍스트를 `tuple[float, ...]`로 변환. pgvector 타입이 경계 밖으로 나가지 않는다)

**Checkpoint**: P2 완료

---

## Phase 8: User Story 6 - 운영 저장소 정책·한국어 검색 확인 (P3)

**Goal**: ADR-008 Follow-ups의 두 확인을 결정 기록에 남긴다

**Independent Test**: ADR-008에 정책 확인 결과(출처 URL·조회일)와 PGroonga 확인 결과(일자·방법)가 있다

- [x] T030 [US6] Oracle Cloud 데이터 처리 정책(학습 사용 여부, 서비스 종료 뒤 보존 기간)을 공식 문서·약관에서 조회해 `docs/sdd/decisions/ADR-008-runtime-and-cost-cap.md` 변경 제안 절에 출처 URL·조회일과 함께 남긴다. 확인하지 못한 항목은 "확인 못 함"으로 적는다
- [ ] T031 [US6] (BLOCKED, 2026-10-19 사용자 결정: 운영 인스턴스를 만드는 후속 작업에서 확인) 운영 PGroonga 확인: Oracle Cloud Always Free A1 인스턴스에서 `supabase/postgres:17.11.0.004`로 `CREATE EXTENSION pgroonga`·`vector`가 되는지 확인하고 결과(일자·방법)를 ADR-008 변경 제안 절에 적는다. 인스턴스 생성은 이 작업 범위 밖이라 사람이 만들거나 확인한다(research R-13). 유휴 회수 대응이 정해지기 전에는 운영 저장소에 실제 팀 자료를 넣지 않는다. 그 전까지 이 작업은 `BLOCKED`다

---

## Phase 9: Polish & Cross-Cutting

- [x] T032 [P] `src/qello_knowledge/adapters/postgres/store.py`: `usage`(`pg_database_size(current_database())`, 청크 수, 임베딩 수, FR-023)와 `tests/localdb/store/test_usage.py`
- [x] T033 `src/qello_knowledge/devtools/bench.py`와 `devtools/db.py` 하위 명령 `store bench`: 로컬 전용 `qk_bench` DB에 합성 데이터(`--text-bytes` 기본 1,100,000), 벡터·키워드 상위 20건 각 100회 p50·p95, `EXPLAIN`의 인덱스 사용 여부, `usage`, 원문 대비 배율, 측정 조건 첫 줄 출력, 끝나면 DB 삭제. 원격 대상 거부(contracts/cli.md)
- [x] T034 `uv run qk-dev store bench`를 실행하고 결과를 quickstart.md 4절 기록 표에 조건과 함께 남긴다(SC-005, SC-006). 목표를 못 맞추면 수치를 그대로 적고 사람 결정으로 넘긴다
- [x] T035 [P] `README.md`의 로컬 시작 절차에 `uv run qk-migrate` 단계를 추가하고 quickstart.md로 연결한다
- [x] T036 AGENTS.md 7절 기본 검증과 quickstart.md 1~3절 전체 실행: `python scripts/preflight.py`, `git diff --check`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run qk-dev db up`, `uv run qk-migrate` 두 번, `QK_REQUIRE_LOCALDB=1 uv run pytest`. 결과를 TASK.md Validation에 반영한다

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 → 스토리 단계. Phase 2(T003~T008)가 끝나야 DB 테스트를 돌릴 수 있다.
- US1(T010~T013) → US2(T014~T019): 검색 테스트가 US1의 저장 연산을 쓴다.
- US3(T020~T023)는 Phase 2 뒤 US1·US2와 독립이다. T023(CI)은 T022 뒤.
- US4(T024~T027)는 US2의 검색 함수(T018·T019)에 기댄다(교체 중 검색 결과 확인).
- US5(T028~T029)는 US1의 `put_embedding`(T013) 뒤 독립이다.
- US6(T030~T031)은 코드와 독립이라 아무 때나 할 수 있다. T031은 사람 확인이 필요하다.
- Polish: T032는 Phase 2 뒤 언제든, T033은 US2 뒤, T034는 T033 뒤, T036은 마지막.

### 스토리 완료 순서

```text
Setup → Foundational → US1 → US2 → US4
                     ├→ US3
                     ├→ US5 (US1 T013 뒤)
                     └→ US6 (코드와 독립)
→ Polish
```

## Parallel Opportunities

- Phase 2: T003·T004 동시, 그다음 T005 → T006 → T007 → T008.
- US1: T010·T011 동시.
- US2: T014·T015·T016·T017 동시(테스트 파일이 다르다), 그다음 T018 → T019.
- US3 테스트 T020·T021은 US2 구현과 동시에 쓸 수 있다.
- US4 T024·T025 동시. US5 T028은 US4와 동시.
- US6 T030은 처음부터 병렬로 할 수 있다.

## Implementation Strategy

1. **MVP**: Setup → Foundational → US1 → US2. 이 시점에 후속 명세(QK-RET-001)가 쓸 저장·검색 경계가 생기고 SC-001·SC-002·SC-007을 확인할 수 있다.
2. **안전성**: US3(재적용·실패·파괴적 보호·CI)와 US4(원자 교체)로 SC-003·SC-004를 닫는다. 이슈 #33 완료 조건 1·2가 여기서 끝난다.
3. **보조**: US5, Polish의 사용량·bench(SC-005·SC-006).
4. **결정 기록**: US6과 ADR-007 승인으로 SC-008(완료 조건 3)을 닫는다. T031은 사람 확인 결과에 따라 `BLOCKED`로 남을 수 있다.

## Requirement Coverage

| 요구사항 | 작업 |
| --- | --- |
| FR-001~005 | T003, T006, T010~T013 |
| FR-006~011 | T014~T019 |
| FR-012~015 | T004, T024~T027, T019(타입 변환) |
| FR-016~020 | T006, T007, T020~T023 |
| FR-021 | 완료(`docs/sdd/decisions/ADR-007-storage-schema.md`, 2026-10-19 승인) |
| FR-022 | T030, T031 |
| FR-023 | T032 |
| SC-001~004, SC-007 | T011, T014, T015, T021, T024 |
| SC-005, SC-006 | T033, T034 |
| SC-008 | T030, T031(BLOCKED), ADR-007 승인(2026-10-19) |
