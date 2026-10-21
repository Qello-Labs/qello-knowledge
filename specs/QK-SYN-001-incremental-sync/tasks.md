---
description: "QK-SYN-001 구현 작업 목록"
---

# Tasks: QK-SYN-001 증분 동기화·문서 단위 원자적 교체·실행 기록·스케줄러·CLI

**Input**: `specs/QK-SYN-001-incremental-sync/`의 plan.md, spec.md, research.md(R-01~R-18), data-model.md, contracts/sync.md, contracts/cli.md, quickstart.md

**Tests**: 포함한다. 명세의 수용 시나리오와 C-12가 자동 시험을 요구한다. 시험을 먼저 쓰고 실패를 확인한 뒤 구현한다. 모든 자동 시험은 외부 호출 0건이다(가짜 자료원·재생 전송,
가짜 임베딩 제공자 `embedding/fake.py`, 메모리 사용량 장부 `tests/unit/fakes.py`, 로컬 DB). 실제 원본·Workers AI·운영 저장소는 맨 끝 "사람 단계"다.

**Organization**: 사용자 스토리별 단계. US1 → US2 → US3(모두 P1) → US4 → US5(P2). US2·US3은 US1의 흐름 뼈대(`plan.py`·`execute.py`·`run.py`)를 고쳐 나간다.

**선행 조건**: spec.md·plan.md 사람 승인(2026-10-21), 이 목록의 사람 승인, `TASK.md` Scope를 구현 범위로 갱신(plan.md "구현 Scope 승인이 필요한 것" 표 포함, AGENTS.md 1절).

**공통 규칙**:
- 문서 본문, 검색 헤더, 임베딩 입력 텍스트, 비밀값, 토큰, 접속 주소를 로그·예외 문구·실행 기록·출력에 넣지 않는다(spec FR-028). 원본 식별자·위치·제목·링크는 QK-SEC-001 기록 출력 규칙을 거친다.
- 시험용 합성 문서만 쓰고 대상 저장소 원문을 저장소에 복사하지 않는다(AGENTS.md 6절). 시험을 지우거나 `skip`·`xfail`로 체크포인트를 통과시키지 않는다.
- 로컬 DB 시험은 `tests/localdb/` 아래에 두고 QK-STO-001 방식(세션마다 `qk_test_<무작위>` 데이터베이스 생성·마이그레이션·삭제, `tests/localdb/store/conftest.py`)을 따른다. 공유 `postgres` 데이터베이스는 건드리지 않는다.
- QK-ING-001·002, QK-SEC-001, QK-STO-001 코드는 plan.md Scope 표의 변경만 한다. 기존 시험은 바꾸지 않고 그대로 통과해야 한다(계약 시험에 항목을 더하는 것은 허용).
- `sync/`는 `adapters`를 가져오지 않는다(T002 경계 검사). 저장은 `ports/sync.py`의 `SyncStore`와 QK-STO-001 `Store`만 거친다.

**TDD 순서**: 각 단계에서 시험 작업을 먼저 쓰고 실패(아직 없는 모듈이면 수집 오류 포함)를 확인한 뒤 구현 작업을 한다. [P]는 같은 단계의 시험끼리, 구현끼리 병렬이라는 뜻이다.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 다른 파일을 다루고 미완료 작업에 기대지 않아 병렬로 할 수 있다
- **[Story]**: 해당 사용자 스토리(US1~US5)

---

## Phase 1: Setup

- [ ] T001 패키지 자리 만들기: `src/qello_knowledge/sync/__init__.py`, `tests/unit/sync/__init__.py`, `tests/localdb/sync/__init__.py`, `tests/localdb/sync/conftest.py`(T012 뒤 마이그레이션 0004를 포함한 `db_url`·`store`·`sync_store` 픽스처. `tests/localdb/store/conftest.py`의 `db_url` 방식을 재사용하고 `seed_index_versions`는 쓰지 않는다), `tests/fixtures/sync/`
- [ ] T002 [P] `tests/unit/test_boundaries.py`: 기존 검사는 그대로 두고, `src/qello_knowledge/sync/` 아래 모듈이 `qello_knowledge.adapters`·`psycopg`·`markdown_it`를 가져오면 실패하는 검사와 위반 사례 시험을 더한다.
  허용: 표준 라이브러리, `qello_knowledge.domain`·`ports`·`embedding`·`chunking`·`security`·`sources`(plan.md Structure Decision, research R-01)

---

## Phase 2: Foundational

**목적**: 모든 스토리가 쓰는 타입, 식별값 계산, 수집·보안 경계 확장, 스키마, 저장 경계와 그 두 구현. 이 단계가 끝나야 스토리 시험을 쓸 수 있다.

- [ ] T003 [P] `tests/unit/sync/test_domain.py`: data-model 2절 타입의 생성·불변식 시험. `SourcePlan` 불변식("`holds`에 `ORIGIN_*`나 `INDEX_MISMATCH`가 있거나 `mode=TAKEDOWN_ONLY`면 `PROCESS` 결정이 없다",
  "보류가 막는 작업(2.4 허용표)의 결정은 없다") 위반은 생성 실패, `DocumentDecision`의 `chunked`가 `repr`에 본문을 내지 않음
- [ ] T004 `src/qello_knowledge/domain/sync.py`: data-model 2.2~2.9를 표준 라이브러리 불변 dataclass·`StrEnum`으로 정의한다. `ChangeReason`(`NEW`, `INPUT_CHANGED`, `CHUNKING_CHANGED`, `REINSTATED`, `INDEX_CHANGED`),
  `DocumentOutcome`(`PROCESSED`, `PROCESSED_EMPTY`, `UNCHANGED`, `TAKEN_DOWN`, `PURGED`, `FAILED`, `HELD`, `SKIPPED`), `HoldReason`(`BUDGET_EXCEEDED`, `BUDGET_EXHAUSTED`, `INDEX_MISMATCH`, `TAKEDOWN_RATIO`,
  `ORIGIN_MISMATCH`, `ORIGIN_MISSING`, `COLLECTION_INCOMPLETE`), `TakedownReason`(보안 `security_path`·`security_secret`·`security_access`·`config_excluded`, 일반 `source_missing`·`not_target`·`source_disabled`와
  `is_security` 속성), `Action`(`PROCESS`, `UNCHANGED`, `TAKE_DOWN`, `PURGE`, `FAIL`, `HOLD`, `SKIP`), `DocumentDecision`, `SourcePlan`, `SyncPreview`, `SyncRunResult`, `ActivationCheck`.
  data-model 2.4 허용표를 `ALLOWED: Mapping[HoldReason, frozenset[작업]]` 상수 하나로 두고 `allowed(holds, 작업) -> bool`(여러 보류면 하나라도 막으면 막음)을 제공한다. 미리 보기와 실행이 이 함수만 쓴다
- [ ] T005 [P] `tests/unit/sync/test_keys.py`: `chunk_input_hash`가 본문 해시·위치·원본 제목 각각에 반응하고 원본 버전에는 반응하지 않음, 원본 제목 `None`과 `""`가 같음, `doc_key`가 64자 16진수이고 자료원 이름·종류·식별자 각각에 반응,
  `index_version_id`가 기본 설정에서 결정적이고 네 재료 각각에 반응, `scope_key("github_repo_files", repo="Owner/Repo", ref="Main")`가 `github_repo_files:owner/repo@main`
- [ ] T006 `src/qello_knowledge/sync/keys.py`: research R-03·R-08·R-10·R-12. `chunk_input_hash(content_hash, location, source_title)` = `sha256("qk-chunk-input-v1\0" + content_hash + "\0" + location + "\0" + (source_title or ""))` 16진수,
  `doc_key(source_name, source_kind, source_id)` = `sha256("qk-doc-v1\0" + …)` 16진수 전체, `METADATA_SCHEMA_VERSION = "meta-v1"`, `index_version_id(embedding_model, dimension, chunking_version, metadata_schema_version)` =
  `"iv-" + sha256("\0".join(...)).hexdigest()[:12]`, `scope_key(kind, scope)`(GitHub은 `<owner>/<repo>@<ref>` 소문자, 포함·제외 패턴 제외)
- [ ] T007 [P] 수집 경계 시험: `tests/contract/source_adapter_contract.py`에 "`ListPage.origin`이 있으면 `origin_id`·`origin_name`은 비어 있지 않은 문자열"을 더하고, `tests/unit/sources/test_list_all.py`에
  "첫 페이지 `origin`이 `Listing.origin`으로 간다, 목록이 비거나 불완전·중단이어도 남는다"를, GitHub 재생 응답 시험(`tests/contract/test_github_adapter_contract.py` 또는 `tests/unit/adapters/`)에
  "저장소 응답의 `id`·`full_name`과 확정 커밋이 `origin`에 들어가고 요청 수가 그대로"를 더한다
- [ ] T008 수집 경계 구현(research R-10, contracts/sync.md 3절): `src/qello_knowledge/domain/source.py`에 `SourceOrigin(origin_id: str, origin_name: str, version: str | None)`(앞의 둘 비어 있으면 `ValueError`),
  `ListPage.origin`·`Listing.origin`(`SourceOrigin | None = None`). `src/qello_knowledge/sources/collect.py`의 `list_all`이 첫 페이지 `origin`을 모든 반환 경로의 `Listing`에 담는다.
  `src/qello_knowledge/adapters/github.py`가 이미 받는 저장소 응답의 `id`(문자열로)·`full_name`과 확정 커밋으로 첫 페이지 `origin`을 채운다(`id`·`full_name`이 없으면 `None`, 응답 형식 오류로 바꾸지 않는다).
  `src/qello_knowledge/adapters/fake.py`는 시험 응답의 선택 필드 `origin`을 읽는다. 기존 시험은 그대로 통과
- [ ] T009 [P] `tests/unit/security/test_screen_listing.py`: `screen_source()` 결과의 `listing`이 `list_all` 결과와 같다(항목·완전 여부·중단·`origin`), `source_excluded`가 기존 `_source_excluded`와 같은 결과
  (`./Docs/X.md`·대소문자 다른 패턴 사례 포함), 판정·요약·기록은 바뀌지 않음(기존 보안 시험 통과)
- [ ] T010 QK-SEC-001 경계 구현(research R-18): `src/qello_knowledge/domain/security.py`의 `ScreenResult`에 `listing: Listing | None = None`(`repr=False`)을 더하고, `src/qello_knowledge/security/screen.py`의
  `screen_source()`가 채운다. 같은 파일에 공개 함수 `source_excluded(location, config) -> bool`을 두고 기존 `_source_excluded`는 그것을 부르게 한다(동작 같음)
- [ ] T011 [P] `tests/localdb/sync/test_migration.py`: 0004 적용 뒤 data-model 1절 열·제약이 있다. 확인: `qk.artifact.purge_pending` "NOT NULL DEFAULT '{}'", `takedown_reason` 검사 제약(1.1의 7개 값만),
  `processed_outcome`은 "`chunked`·`empty`·NULL", `qk.sync_source.source_kind` 유일, `qk.sync_run.status` 5개 값, `qk.sync_document_result` 기본 키 `(run_id, doc_key, action)`, 자식 행 `ON DELETE CASCADE`.
  기존 행이 있는 `qk.artifact`에 적용해도 값이 바뀌지 않고, 두 번째 적용은 변경 0(QK-STO-001 FR-017)
- [ ] T012 `src/qello_knowledge/adapters/postgres/migrations/0004_sync.sql`: research R-02, data-model 1.1~1.4. 더하기만 하고 기존 열·제약·함수는 바꾸지 않는다(지우는 마이그레이션 아님). `qk.artifact` 추가 열 11개
  (`source_name`, `chunk_input_hash`, `processed_chunking_version`, `processed_index_version`(`qk.index_version(id)` 참조), `processed_outcome`, `last_seen_version`, `last_seen_at`, `takedown_reason`, `takedown_at`,
  `purge_pending text[] NOT NULL DEFAULT '{}'`, `purge_reason`), `qk.sync_source`, `qk.sync_run`, `qk.sync_run_source`(`holds text[] NOT NULL DEFAULT '{}'` 포함), `qk.sync_document_result`(`lines int[]` 포함)와
  `(source_name, doc_key, outcome)` 인덱스. 불변식 "`purge_pending <> '{}'` ⇔ `purge_reason IS NOT NULL`"은 검사 제약으로 둔다
- [ ] T013 `src/qello_knowledge/ports/sync.py`: contracts/sync.md 2절 `SyncStore` Protocol과 입력·출력 타입(`IndexState`, `StoredDocument`(data-model 1.1 열, 본문 없음), `StoredSource`, `SyncLock`,
  `ArtifactWrite`, `RunInfo`). 표준 라이브러리와 `qello_knowledge.domain`만 가져온다
- [ ] T014 `src/qello_knowledge/adapters/postgres/store.py`: `replace_chunks`의 "이 인덱스 버전 청크 지우기 + 넣기 + 임베딩 id 찾기" 부분을 같은 모듈의 내부 함수(연결을 인자로 받음)로 빼서
  `sync_store.py`가 같이 쓸 수 있게 한다(research R-01). `replace_chunks` 동작·반환값은 그대로. `tests/localdb/store/test_replace.py` 등 기존 시험이 그대로 통과하는지 확인
- [ ] T015 [P] `tests/unit/sync/fake_store.py`: `SyncStore`와 QK-STO-001 `Store`의 `find_embeddings`·`put_embedding`을 메모리로 구현한다. 연산마다 문서 하나 단위로 "전부 반영 또는 전부 취소"를 흉내 내고,
  지정한 `doc_key`의 지정한 연산에서 `StoreError`를 던지는 장애 주입과, 연산 호출 기록(검사용)을 제공한다. 쓰기 연산 수를 셀 수 있다(미리 보기 쓰기 0 검사)
- [ ] T016 [P] `tests/localdb/sync/test_sync_store.py`: `PostgresSyncStore`의 기본 연산 시험. `ensure_index_version` 재실행 안전(`ready` 하나), `load_documents`가 본문 없이 상태 열을 돌려줌,
  `apply_document`가 원본 자료 행·이번 버전 청크·결과 행을 한 트랜잭션에 반영(청크 넣기 중 오류를 주입하면 원본 자료 행·결과 행도 없음), `mark_seen`, `record_outcome`, `begin_run`·`finish_source`·`finish_run`
- [ ] T017 `src/qello_knowledge/adapters/postgres/sync_store.py`: `PostgresSyncStore`(연결은 `connection.connect(url)` autocommit, 문서 연산마다 `conn.transaction()`, 대상 원본 자료 행 `FOR UPDATE`, research R-04).
  이 단계에서 `index_state`, `ensure_index_version`, `load_documents`, `load_sources`, `begin_run`, `apply_document`, `mark_seen`, `record_outcome`, `finish_source`, `finish_run`을 구현한다.
  접근 범위 대응: 도메인 `TEAM` → `'team'`, `RESTRICTED` → `'restricted'`, `UNKNOWN` → `NULL`. 오류는 QK-STO-001 `StoreError` 계열(`InvalidRecord`, `StoreUnavailable`)로 바꾸고 메시지에 접속 정보·본문을 넣지 않는다.
  내림·대기 삭제(US3), 잠금·활성화·정리·조회(US4·US5)는 뒤 단계에서 더한다

**Checkpoint**: `uv run pytest tests/unit/sync tests/unit/test_boundaries.py tests/unit/sources tests/unit/security tests/contract` 통과, `QK_REQUIRE_LOCALDB=1 uv run pytest tests/localdb` 통과.

---

## Phase 3: User Story 1 - 바뀐 문서만 다시 처리하고, 변경이 없으면 임베딩을 부르지 않는다 (P1) 🎯 MVP

**Goal**: 첫 동기화는 전부 처리, 재동기화는 변경 없음, 문서 하나 수정은 그 문서만. 실패·내림·예산·잠금은 뒤 스토리.

**Independent Test**: 가짜 자료원·가짜 임베딩·메모리 저장소로 두 번 동기화해 외부 임베딩 호출 수와 청크 교체 수를 세고, 문서 하나를 고쳐 다시 센다(quickstart 1절 "변경 판단").

- [ ] T018 [P] [US1] `tests/unit/sync/helpers.py`: 가짜 자료원 설정·재생 응답을 만드는 도우미(문서 목록을 받아 `fake` 종류 자료원의 목록·본문 응답 생성, 원본 버전·접근 권한·`origin` 지정 가능), 동기화 의존성 묶음 조립 도우미
  (보안 정책, 기본 `ChunkingSettings`, `EmbeddingService` + `FakeEmbeddingProvider` + `InMemoryUsageLedger` + 메모리 저장소). 합성 Markdown만 쓴다
- [ ] T019 [P] [US1] `tests/unit/sync/test_incremental.py`(spec US1 시나리오 1~6, SC-001·002·006, FR-005·008~011): 첫 동기화 5개 모두 `PROCESSED`·결과 기록 5건, 원본 그대로 재동기화 → 제공자 호출 0·청킹 호출 0
  (`chunk_screened` 감시)·`apply_document` 0·`UNCHANGED` 5건, 무변경 문서도 본문 조회 1회(보안 규칙 재판정), 커밋만 바뀐 원본 → `UNCHANGED`와 `source_version`·`source_url` 그대로·`last_seen_version` 갱신,
  문서 B 한 줄 수정 → B만 `INPUT_CHANGED`, 제목만·위치만 바뀐 사례 → `INPUT_CHANGED`, 청킹 규칙 버전만 다른 저장 상태 → `CHUNKING_CHANGED`, 새 문서 F → `NEW`, 빈 문서 → `PROCESSED_EMPTY`(청크 0개), 두 번 연속 실행 중복 0
- [ ] T020 [US1] `src/qello_knowledge/sync/decide.py`: research R-03 변경 판정 `change_reason(stored, fingerprint, chunking_version, index_version) -> ChangeReason | None`(순서 `NEW` → `INPUT_CHANGED` → `CHUNKING_CHANGED` →
  `REINSTATED`(`status <> 'active'` 또는 접근 범위 `team` 아님) → `INDEX_CHANGED`, 준비 상태 인덱스 버전은 판정에 쓰지 않음)
- [ ] T021 [US1] `src/qello_knowledge/sync/plan.py`: `plan_source()`(contracts/sync.md 1절, research R-18). `screen_source()` → 통과 문서마다 `chunk_input_hash` 계산과 `change_reason` → `PROCESS`로 판정된 문서만
  `chunk_screened()`에 넘김 → `DocumentDecision` 목록. 원본 제목은 `content.title or item.title`(`chunking/service.py:85`와 같은 값). 내림·보류 판정 자리는 비워 두고 US3·US5에서 채운다
- [ ] T022 [US1] `src/qello_knowledge/sync/execute.py`: 쓰기 단계의 처리 경로(research R-17 1·3단계). 바뀐 문서마다 캐시 확인(`embedding.hashing.input_hash` + 모델 버전으로 `Store.find_embeddings`) → 모두 있으면
  `embed()` 없이, 아니면 `EmbedRequest`(문서 하나, `purpose=INDEX`, `origin=(source_name, location)`) → 모든 항목 벡터면 `apply_document`. `ChunkInput`의 `embedding`에 `EmbeddingRef`를 채운다.
  변경 없음 문서는 `mark_seen` 한 번. 캐시 직접 반영 문서의 임베딩 요약은 `requested` = `cache_hits` = 항목 수, `provider_calls` 0, `neurons` 0(data-model 2.8)
- [ ] T023 [US1] `src/qello_knowledge/sync/run.py`: `run_sync()` 뼈대(contracts/sync.md 1절 3~5·7·8단계). 실행 전 점검·잠금은 주입한 함수로 받아 이 단계에서는 통과만 한다(US5에서 채움). `run_id` = `sync-<UTC 시각>-<무작위 8자>`,
  `begin_run` → 활성 버전 없으면 `ensure_index_version(index_version_id(...))` → 자료원마다 `plan_source` → `execute` → `finish_source`·`finish_run`(data-model 3.2 상태 규칙). `sync/__init__.py`에서 `run_sync` 공개
- [ ] T024 [P] [US1] `tests/localdb/sync/test_incremental_db.py`(SC-001·002, 로드맵 1.G): 로컬 DB와 `PostgresStore`·`PostgresSyncStore`로 첫 동기화 → 준비 버전 청크가 생김(시험 안에서만 그 버전을 SQL로 활성화해 검색 확인) →
  무변경 재동기화의 제공자 호출 0·청크 식별자 그대로 → 문서 하나 수정 시 그 문서의 청크만 새 식별자

**Checkpoint**: US1 시험 통과. 변경 없는 재동기화 임베딩 호출 0을 메모리·로컬 DB 양쪽에서 확인.

---

## Phase 4: User Story 2 - 문서 하나씩 통째로 바꾸고, 실패한 문서는 이전 청크를 지킨다 (P1)

**Goal**: 청킹·임베딩·저장 실패 격리, 실행 소진 상태, 끊김 뒤 일관성.

**Independent Test**: 실패를 주입해 실패 문서의 검색 결과·저장 상태·다음 판단이 이전 그대로이고 다른 문서는 처리되는지 본다(quickstart 1절 "원자 반영").

- [ ] T025 [P] [US2] `tests/unit/sync/test_failures.py`(spec US2 시나리오 1~4·6, FR-014·025, research R-17): 문서 B 청크 하나에 `INPUT_TOO_LONG` → B만 `FAILED(embed, input_too_long)`·A 반영·C 변경 없음, 원인 제거 뒤 B만 처리,
  청킹 실패(줄 길이 초과) → `FAILED(chunk, line_too_long)`, `PROVIDER_QUOTA`·`INDEX_BUDGET`·`USAGE_UNAVAILABLE` 항목 실패와 `usage_unavailable` 경고(정산 실패)와 `EmbedError`(`AUTH_CONFIG`·`USAGE_UNAVAILABLE`)
  각각의 뒤로 제공자 호출 0·캐시에 없는 문서 `HELD(BUDGET_EXHAUSTED)`·캐시 완비 문서 반영, 정산 실패 사례에서 이미 받은 벡터로 끝나는 문서는 반영, 사용량 장부 `today()` 실패에서도 캐시 완비 문서 반영
- [ ] T026 [P] [US2] `tests/localdb/sync/test_atomic.py`(SC-004·006·014): `apply_document` 청크 넣기 중 오류 → 원본 자료 행(지문·처리 버전·접근 범위·상태)·청크·결과 행 모두 이전 그대로이고 다음 실행이 다시 `PROCESS`,
  새 묶음 일부만 검색되는 순간 없음(반영 트랜잭션 중 다른 연결의 검색은 이전 묶음), 문서 반영 직전·직후와 `finish_run` 직전에 프로세스 끊김을 흉내(연결 강제 종료)한 뒤 반영된 문서와 결과 행이 어긋난 경우 0,
  끊김 뒤 같은 동기화 재실행 결과가 끊기지 않은 실행과 같음
- [ ] T027 [US2] `src/qello_knowledge/sync/execute.py`: research R-17 2·3단계 실행 소진 상태(실행 전체에 하나, `execute`에 넘겨 다음 자료원까지 유지). 켜는 신호: 항목 실패 `PROVIDER_QUOTA`·`INDEX_BUDGET`·`USAGE_UNAVAILABLE`,
  요약 경고 `usage_unavailable`, `EmbedError`. 켜진 뒤 캐시에 없는 청크가 있는 문서는 `record_outcome(HOLD, BUDGET_EXHAUSTED)`. 청킹 실패는 `FAILED(chunk, <유형>)`, `apply_document`의 `StoreError`는 `FAILED(store, <오류 종류>)`이고
  `StoreUnavailable`이면 실행을 멈추고 남은 문서는 결과를 남기지 못할 수 있음(최종 상태 없이 남아 다음 실행이 `unfinished`로 닫는다)

**Checkpoint**: US1·US2 시험 통과.

---

## Phase 5: User Story 3 - 검색에 나오면 안 되게 된 문서는 내린다 (P1)

**Goal**: 보안 내림 우선, 일반 내림, 삭제 대기, 내림 비율, 보류 사유별 허용표, 지운 자료원.

**Independent Test**: 로컬 DB에서 지운 문서·권한 미확인·비밀값·제외 패턴 문서가 검색에 안 나오고 보안 사유 문서의 청크 행이 없는지, 불완전 목록에서 일반 내림 0인지 본다(quickstart 1절 "내림").

- [ ] T028 [P] [US3] `tests/unit/sync/test_takedown_decide.py`(research R-05·R-18, data-model 2.4): 사유별 판정(보안 필터 경로 제외·비밀값·접근 보류 → 보안 사유와 규칙 이름·줄 번호, 저장된 위치가 제외 패턴 →
  `config_excluded`(목록 불완전이어도), 포함 패턴에서만 빠짐·목록에 없음 → 목록이 완전할 때만 `source_missing`, `NOT_MARKDOWN` → `not_target`, 판정 실패·본문 조회 실패 → 내림 아님), 제외와 포함 이탈이 겹치면 `config_excluded`,
  제외 패턴 대소문자·`./` 정규화 사례, 비율 판정(기준 = 일반 사유로 내려지지 않은 저장 문서 수, 기준 0이고 대상 ≥ 1이면 초과, 20% 경계값 양쪽), 허용표 모든 칸(보류 7종 × 작업 7종, 여러 보류 조합)
- [ ] T029 [P] [US3] `tests/localdb/sync/test_takedown.py`(spec US3 시나리오 1~9, SC-003·005·015): 지운 문서 → 검색·문맥 확장 0·청크 행 유지·`source_missing`, 권한 미확인·비밀값·설정 제외 → 검색 0·그 문서 모든 버전 청크 행 0
  (`body`·`search_text` 함께), 불완전 목록·수집 중단 → `source_missing` 0·실행 `stopped`·이미 판정된 보안 내림은 적용, 비율 초과 → 일반 내림 0·보안 내림은 검색 제외 + `purge_pending`·`purge_reason`,
  확인 옵션 실행 → 대기 본문 0(그 사이 원본에서 사라진 문서 포함), 준비 버전 둘에 청크가 있는 문서를 삭제 보류한 뒤 본문을 고쳐 한 버전만 다시 처리 → `active` + 다른 버전 대기 유지·확인 옵션 뒤 0,
  한 실행 안 `PURGE`→`PROCESS`·`PURGE`→`UNCHANGED`·일반 내림 뒤 `PURGE`의 결과 행이 작업마다 하나, 빈 문서 보안 내림 비율 보류 시 대기 목록·사유 비움, 내려진 문서가 다시 팀 공용이면 `REINSTATED`로 처리,
  설정에서 지운 자료원 → `TAKEDOWN_ONLY`로 `source_disabled`, 비공개 전환(전체 접근 보류)·인덱스 버전 불일치·예산 초과 각각에 비밀값 문서를 더한 실행에서 보안 사유 문서 검색 0
- [ ] T030 [US3] `src/qello_knowledge/adapters/postgres/sync_store.py`: `take_down`(일반: `status='deleted'`·사유·결과 행, 청크 유지 / 보안 삭제 허용: 접근 범위 판정값·모든 인덱스 버전 청크 행 삭제·`purge_pending='{}'`·`purge_reason` NULL /
  보안 삭제 보류: 청크가 남은 버전 목록과 사유, 남은 청크가 없으면 둘 다 비움), `purge_pending_bodies`(목록의 버전 청크만 삭제, 상태는 그대로), `apply_document`의 `purge_pending`에서 이번 버전 빼기(비면 사유도 비움).
  모두 문서 하나 = 트랜잭션 하나, 결과 행 포함(research R-04 표)
- [ ] T031 [US3] `src/qello_knowledge/sync/decide.py`·`plan.py`: research R-18 내림 판정(`ScreenResult.verdicts`, `ScreenResult.listing`의 완전 여부·중단, 저장된 문서의 `source_excluded`·`in_scope(location, include, ())`),
  `TakedownReason`, 비율 판정(research R-05, 확인 옵션 `confirm_takedown`), `COLLECTION_INCOMPLETE` 보류, `mode=TAKEDOWN_ONLY` 계획(설정에서 빠졌거나 꺼진 저장 자료원, `source_disabled`). 메모리 저장소 구현(T015)에도 내림 연산을 맞춘다
- [ ] T032 [US3] `src/qello_knowledge/sync/execute.py`·`run.py`: 쓰기 순서(contracts/sync.md 1절 7단계) 보안 내림 → 일반 내림 → 대기 본문 지우기 → 처리 → `mark_seen` → 보류·건너뜀·실패 기록. 각 작업은 `domain.sync.allowed(holds, 작업)`로만 거른다.
  `INDEX_MISMATCH`(활성 버전이 있고 현재 설정 버전과 다름) 판정을 `run.py` 4단계에 넣는다. 수집 중단으로 본문을 받지 못한 문서는 `SKIP`

**Checkpoint**: US1~US3 시험 통과. 1.G의 "지운 문서·접근 범위 미확인 문서가 검색되지 않는다"를 로컬 DB로 확인.

---

## Phase 6: User Story 4 - 실행 전에 비용을 보고, 실행 뒤에 무엇을 했는지 안다 (P2)

**Goal**: 미리 보기(쓰기 0), 실행 전체 예산 판정, 실행 기록의 요약·내부 식별값·보안 근거·수집 요약, 원문 비노출.

**Independent Test**: 미리 보기 뒤 실제 실행의 대상 집합을 비교하고, 실패 주입 실행의 기록을 문서별 결과와 대조한다(quickstart 1절 "미리 보기·예산", "실행 기록").

- [ ] T033 [P] [US4] `tests/unit/sync/test_preview_budget.py`(spec US4 시나리오 1~3, SC-007·008, FR-022~025): 미리 보기 쓰기 연산 0·제공자 호출 0(확인 옵션·부분 실행 옵션을 준 미리 보기 포함), 같은 상태 실제 실행과 처리·변경 없음·내림 대상 집합 100% 일치,
  실패 없는 통제 시험에서 처리 성공 수도 같음, 예상 Neurons와 계산 근거가 `EmbedPreview`와 같음, 예산 초과 + 옵션 없음 → 제공자 호출 0·`apply_document` 0·보안 내림·일반 내림·`mark_seen`은 함·종료 상태 `stopped`,
  두 자료원 각각은 예산 안이지만 합계가 넘으면 둘 다 보류, `--allow-partial-budget` → 예산 안 문서만 반영
- [ ] T034 [P] [US4] `tests/unit/sync/test_run_record.py`(spec US4 시나리오 4·5, SC-009, FR-026~028): 요약 수치 = 결과 행 수(작업별·사유별·보류별), 수집 요약(`FetchResult.to_dict()`에서 항목 목록 제외)·필터·청킹·임베딩 요약 있음,
  캐시 직접 반영 문서가 임베딩 요약의 요청·캐시 적중 수에 들어감, 보안 내림 결과에 규칙 이름·줄 번호만, 표지 문자열(`QK-SYN-001-LEAK-MARKER`)과 합성 비밀값을 본문·오류 메시지에 넣은 실행에서 실행 기록·`--json` 출력·`caplog` 전체에 표지·비밀값·토큰 모양·주소 0,
  원본 식별자가 출력 규칙에 걸려 가려진 문서와 처음 처리에 실패한 새 문서를 `doc_key`로 다음 목록에서 다시 찾음
- [ ] T035 [US4] `src/qello_knowledge/sync/preview.py`: `preview()`(research R-07, data-model 2.7). 모든 대상의 `SourcePlan`을 받아 처리할 문서의 임베딩 입력을 모아 `Embedder.preview()` 한 번, 허용표(`allowed`)로 행동별 예정 수 계산,
  인덱스 버전 상태. 잠금·실행 기록·기준값 등록·저장소 쓰기 없음. `sync/__init__.py`에서 공개
- [ ] T036 [US4] `src/qello_knowledge/sync/run.py`: contracts/sync.md 1절 5·6단계. 모든 대상의 `plan_source`를 먼저 만들고 실행 전체 예상량으로 `Embedder.preview()`를 한 번 불러, 실행 불가이고 부분 실행 옵션이 없으면 모든 자료원에
  `BUDGET_EXCEEDED` 보류(research R-17)
- [ ] T037 [US4] `src/qello_knowledge/sync/report.py`: 자료원·실행 요약 만들기(data-model 2.8, contracts/cli.md 4절 JSON 키), `doc_display`는 QK-SEC-001 `policy.output_context(kind)`로 원본 식별자에 기록 출력 규칙 적용,
  사람용 출력. `sync_store.py`의 결과 행에 `rule`·`lines`·`change_reason`을 채우고 `finish_source`·`finish_run`의 `summary`에 요약을 넣는다

**Checkpoint**: US1~US4 시험 통과.

---

## Phase 7: User Story 5 - 정해진 주기로 돌고, 명령 하나로 다룬다 (P2)

**Goal**: 실행 전 점검과 자료원 식별, 종류별 잠금·끝나지 않은 기록, 첫 인덱스 버전 활성화, 실행 기록 조회·정리, `qk-index` 명령, 주기 실행 워크플로.

**Independent Test**: CLI를 가짜 자료원·가짜 임베딩·로컬 DB로 돌려 종료 코드와 출력을 보고, 같은 종류 두 실행을 겹치고, 워크플로 파일 내용을 검사한다(quickstart 1절 "동시 실행", "정체성·점검", "점검 무쓰기", "주기 실행 정의").

- [ ] T038 [P] [US5] `tests/unit/sync/test_identity.py`(FR-002, SC-011, research R-10): 같은 종류 활성 자료원 둘 → 점검 실패·원본 요청 0·쓰기 0, 같은 이름의 `scope_key` 다름 → 실패, 저장된 A를 설정에서 지우기만 함 → `TAKEDOWN_ONLY`,
  A를 지우고 같은 종류 B를 추가 → 첫 쓰기 전 실패, 수집 뒤 `origin_id`만 다름·`origin_name`만 다름·`origin` 없음 → 그 자료원 처리 0·일반 내림 0·`mark_seen` 0·보안 내림은 함, 기준값 없는 첫 실행 → 첫 문서 쓰기 직전 등록,
  첫 실행에서 일부 문서를 반영한 뒤 끊고 정체성을 바꿔 재실행 → 바뀐 정체성을 기준값으로 받지 않음, 빈 목록·불완전 목록에서도 `origin`·원본 버전이 실행 기록에 남음, 미리 보기 뒤 기준값 없음
- [ ] T039 [P] [US5] `tests/localdb/sync/test_concurrency.py`(FR-029, SC-010·014, research R-06): 같은 자료원 두 동기화를 겹치면 하나는 종료 코드 6·쓰기 0, 같은 종류·다른 이름·같은 원본 식별자 두 자료원(설정 파일 둘)의 동시 첫 실행에서 하나만 진행,
  잠금을 쥔 연결을 강제로 끊은 뒤 다음 실행이 진행되고 이전 `running` 기록을 `unfinished`로 닫음, 다른 종류 자료원의 `running` 기록은 그대로, 동기화 중 첫 버전 활성화 거부, 실행 중 `runs prune`이 `running` 기록을 남김
- [ ] T040 [P] [US5] `tests/localdb/sync/test_index_version.py`(FR-019~021, SC-014, research R-08·R-09): 활성 버전 없음 → 준비 버전 하나 생성·재사용, 활성화 전 변경 없는 재실행 `PROCESS` 0, 활성화 전 설정 변경 → 새 준비 버전에 모든 문서 처리(`INDEX_CHANGED`),
  활성화 조건 (1)~(5) 각각 못 채운 경우 거부와 실패 조건 이름(옛 준비 버전, 마지막 실행 `partial`·`stopped`·`unfinished`·`running`, 검색될 문서 0, 벡터 없는 청크), 조건 충족 시 활성화와 검색 결과, 활성 버전이 있으면 거부,
  동기화가 활성화한 경우 0, 활성 버전과 현재 설정이 다르면 `INDEX_MISMATCH`로 교체 0·일반 내림 0·보안 검색 제외 적용
- [ ] T041 [P] [US5] `tests/unit/indexer/test_run_cli.py`(US5 시나리오 1~3·5~7, FR-030~033, contracts/cli.md): `qk-index run`·`run --preview`·`runs list`·`runs show --failures`·`runs prune`·`index status`·`index activate`의 출력과 종료 코드 0~6,
  설정·자료원·개인 정보 확인 기록·보안 규칙·예산 설정 점검 실패와 원격 대상 `--allow-remote` 없음(종료 코드 3)과 `config/store_policy.toml` 없음(종료 코드 1)에서 원본 요청 0·저장소 쓰기 0, `--preview`와 `--trigger` 함께 → 인자 오류,
  `runs prune --retention-days 0` 거부, 기존 하위 명령(`check`, `sources check`, `security check`, `usage`, `usage prune`) 출력·종료 코드 회귀(`tests/unit/indexer/test_cli.py`·`test_cli_usage.py` 그대로 통과).
  의존성(전송·임베딩 제공자·저장소)은 `main()`의 주입 인자로 바꿔 끼운다(`ledger_factory`와 같은 방식). 고정 입력은 `tests/fixtures/sync/`(가짜 자료원 설정·개인 정보 확인 기록·재생 응답)
- [ ] T042 [P] [US5] `tests/unit/indexer/test_schedule_workflow.py`(FR-034~037, research R-14): `.github/workflows/index-sync.yml`을 줄 단위 텍스트로 읽어(새 의존성 없음) `schedule` cron `30 0 * * *`, `workflow_dispatch`,
  `if: vars.QK_SYNC_ENABLED == 'true'`, `permissions: contents: read`, `concurrency` `index-sync`·`cancel-in-progress: false`, `timeout-minutes: 30`, `persist-credentials: false`, `uv sync --locked --extra index --extra postgres`,
  `qk-index run --allow-remote --trigger schedule --json`, `if: always()`인 `usage prune --allow-remote`·`runs prune --allow-remote`, Secret 이름 `DATABASE_URL`·`QK_GITHUB_API_TOKEN`(→ `GITHUB_API_TOKEN`)·`CLOUDFLARE_API_TOKEN`·`CLOUDFLARE_ACCOUNT_ID`이 `secrets.`로만 쓰이고 값 모양 문자열이 없음
- [ ] T043 [US5] `src/qello_knowledge/sync/identity.py`·`run.py`: research R-10 (a)~(d) 점검(잠금 전과 잠금 뒤 두 번), 대상 자료원 목록(`FULL`·`TAKEDOWN_ONLY`, `--source` 선택), 수집 뒤 정체성 비교와 `ORIGIN_MISMATCH`·`ORIGIN_MISSING` 보류,
  첫 문서 쓰기 직전 `register_origin`. `sync_store.py`에 `register_origin`(종류 유일 제약 위반은 `StoreError`)
- [ ] T044 [US5] `src/qello_knowledge/adapters/postgres/sync_store.py`·`sync/run.py`: research R-06 잠금. `try_lock(source_kinds)`는 같은 연결에서 종류별 `pg_try_advisory_lock`과 전역 `qk-sync-index` `pg_try_advisory_lock_shared`(키는 고정 문자열의 `hashtext`나 상수),
  하나라도 실패하면 잡은 것을 놓고 `None`. `begin_run`이 잠근 종류의 `running` 기록을 `unfinished`로 닫는다. 잠금 연결은 실행 내내 유지하고 재연결하지 않는다. 미리 보기는 잠그지 않는다
- [ ] T045 [US5] `src/qello_knowledge/adapters/postgres/sync_store.py`·`src/qello_knowledge/sync/activate.py`: research R-09 `activation_check`, `activate`(전역 배타 잠금 안 한 트랜잭션, 조건 (1)~(5), 실패 조건 이름 목록), `activate_first_index()` 공개.
  `list_runs`, `run_detail`, `run_failures`, `prune_runs(retention_days)`(`status <> 'running'`, 기간 1 이상, 함수 하나 = 트랜잭션 하나, 두 번째 실행 0건, `qk.sync_source`는 지우지 않음)
- [ ] T046 [US5] `src/qello_knowledge/indexer/sync_cli.py`·`src/qello_knowledge/indexer/cli.py`: contracts/cli.md 1~4절. `qk-index run`을 동기화 실행으로 바꾸고(기존 점검 단계·옵션 유지), `--preview`, `--trigger`, `--allow-remote`, `--allow-partial-budget`,
  `--confirm-takedown`, `--source`, `--json`, `--env-file`; `runs list|show|prune`, `index status|activate` 하위 명령. 원격 대상 판정은 `adapters/postgres/connection.target_label`, 원격이면 `--allow-remote`와 `config/store_policy.toml`
  (필수 항목: 제공자, 확인 날짜, 결정 기록 경로) 확인(research R-13). 의존성 조립(`GitHubRepoFilesAdapter`·`HttpsTransport`, `WorkersAiRestProvider`, `PostgresUsageLedger`, `PostgresStore`, `PostgresSyncStore`)은 이 파일에서만 하고 주입 인자로 바꿀 수 있게 한다.
  종료 코드 research R-16(4와 5가 함께면 5)
- [ ] T047 [US5] `.github/workflows/index-sync.yml`: contracts/cli.md 5절 그대로. 저장소 변수 `QK_SYNC_ENABLED`가 없으면 작업이 건너뛰어진다는 주석과, Secret·변수 등록은 사람 단계 H07이라는 주석을 단다

**Checkpoint**: 전체 단위·로컬 DB 시험 통과.

---

## Phase 8: Polish & Cross-Cutting

- [ ] T048 [P] `tests/localdb/sync/test_perf.py`(SC-013, research R-15): `tests/unit/chunking/test_perf.py`의 시드 `20261021` 합성 문서 79개 생성기를 재사용(가져오거나 같은 도우미로 옮김)해 가짜 자료원으로 넘기고,
  빈 로컬 DB 첫 동기화와 이어서 변경 없는 동기화를 각각 3번 반복한 중앙값이 60초·30초 이하. 회귀 감시이고 측정 장비는 실행 기록에 남긴다
- [ ] T049 [P] `specs/QK-SYN-001-incremental-sync/quickstart.md`: 구현과 다른 명령·옵션·시험 파일 이름이 있으면 고친다(계약과 다르면 계약을 먼저 고치고 사람 승인). 4절 추적표의 시험 사례 이름을 실제 시험 함수에 맞춘다
- [ ] T050 기본 검증(AGENTS.md 7절): `python scripts/preflight.py`, `git diff --check`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run qk-dev db up`, `uv run qk-migrate`(두 번째 `applied=0`), `QK_REQUIRE_LOCALDB=1 uv run pytest`.
  실패는 원인을 고치고 시험을 지우거나 건너뛰지 않는다. 실행 결과(통과 수, 소요)를 이 파일 끝 실행 기록에 남긴다

---

## 사람 단계 (구현 뒤, quickstart 3절)

각 단계는 사람의 승인 뒤에만 한다(AGENTS.md 3.5, spec FR-033·FR-036). H01~H03은 이 작업의 완료 판정(spec SC-012)에 쓴다.

- [ ] H01 로컬 DB에 실제 자료원 미리 보기: `uv run qk-index run --preview --json`(GitHub 약 83회, 0 Neurons). 처리 예정 문서 수와 예상 Neurons를 기록하고 실행 승인을 받는다
- [ ] H02 로컬 DB에 첫 실제 색인과 재실행: `uv run qk-index run --json` 두 번(예상 약 325 Neurons, H01 값으로 확인). 두 번째 `embedding.provider_calls == 0`. spec SC-012 측정 조건(대상 커밋, 보안·청킹 규칙 버전, 인덱스 버전, 실행 환경, 날짜)과 원본 요청 수, 소요 시간, 처리 문서 수, 청크 수, 소비 Neurons를 기록
- [ ] H03 로컬 DB에서 `qk-index index status` → `qk-index index activate <버전>` → 검색 확인(질의 임베딩 소량). 활성화 요약과 검색 결과 출처 기록
- [ ] H04 운영 저장소 제공자 데이터 처리 정책 확인(ADR-008·ADR-019에 출처·조회일)과 `config/store_policy.toml` PR
- [ ] H05 운영 저장소 연결이 세션 advisory lock을 유지하는 직접 연결인지 확인(research R-06 남는 위험)
- [ ] H06 운영 저장소 첫 실제 색인(`--allow-remote`)과 활성화(H02와 같은 Neurons, spec SC-012)
- [ ] H07 GitHub Actions 무료 할당 확인, Secret 등록, 저장소 변수 `QK_SYNC_ENABLED=true`, 첫 예약 실행 결과 확인

H04~H07은 운영 저장소가 정해진 뒤 1.G 완료 리뷰 전까지 한다.

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 → US1(Phase 3) → US2(Phase 4) → US3(Phase 5) → US4(Phase 6) → US5(Phase 7) → Polish(Phase 8) → 사람 단계.
- Phase 2 안: T004 → T006 → T013. T008(수집 경계)·T010(보안 경계)·T012(마이그레이션)·T014(저장 내부 함수)는 서로 독립. T017은 T012·T013·T014 뒤. T015는 T013 뒤.
- US2~US5는 US1의 `plan.py`·`execute.py`·`run.py`를 고친다. 같은 파일을 고치는 작업은 순서대로 한다: `execute.py`(T022 → T027 → T032), `run.py`(T023 → T032 → T036 → T043 → T044),
  `plan.py`·`decide.py`(T020·T021 → T031), `sync_store.py`(T017 → T030 → T037 → T043 → T044 → T045).
- US5의 CLI(T046)는 T043~T045 뒤, 워크플로(T047)는 T046 뒤.
- 각 단계의 시험 작업([P])을 먼저 쓰고 실패를 확인한 뒤 구현 작업을 한다.

## Parallel Opportunities

- Phase 1: T002는 T001과 병렬.
- Phase 2: 시험 T003·T005·T007·T009·T011·T016과 메모리 저장소 T015(T013 뒤)를 먼저 병렬로 쓴다. 구현 T008·T010·T012·T014는 서로 병렬.
- US1: T018·T019·T024. US2: T025·T026. US3: T028·T029. US4: T033·T034. US5: T038~T042. 각 묶음은 서로 병렬.
- Polish: T048·T049 병렬, T050은 맨 마지막.

## Implementation Strategy

1. **MVP = Phase 1~3(US1)**: 바뀐 문서만 처리하고 변경 없는 재동기화에서 임베딩 0. 로드맵 1.G 첫 조건을 로컬에서 확인할 수 있다.
2. US2·US3으로 실패 격리와 내림을 더하면 1.G의 "그 문서의 청크만 교체", "지운 문서·접근 미확인 문서 미노출"을 닫는다.
3. US4·US5로 미리 보기·실행 기록·CLI·잠금·활성화·주기 실행을 더하면 사람 단계 H01~H03(실제 첫 색인)을 할 수 있다.
4. 운영 저장소가 정해지면 H04~H07로 주기 실행을 켠다.

## 실행 기록

(구현 에이전트가 단계마다 RED/GREEN, 판단, 환경 제약을 남긴다.)
