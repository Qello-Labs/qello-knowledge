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

- [X] T001 패키지 자리 만들기: `src/qello_knowledge/sync/__init__.py`, `tests/unit/sync/__init__.py`, `tests/localdb/sync/__init__.py`, `tests/localdb/sync/conftest.py`(T012 뒤 마이그레이션 0004를 포함한 `db_url`·`store`·`sync_store` 픽스처. `tests/localdb/store/conftest.py`의 `db_url` 방식을 재사용하고 `seed_index_versions`는 쓰지 않는다), `tests/fixtures/sync/`
- [X] T002 [P] `tests/unit/test_boundaries.py`: 기존 검사는 그대로 두고, `src/qello_knowledge/sync/` 아래 모듈이 `qello_knowledge.adapters`·`psycopg`·`markdown_it`를 가져오면 실패하는 검사와 위반 사례 시험을 더한다.
  허용: 표준 라이브러리, `qello_knowledge.domain`·`ports`·`embedding`·`chunking`·`security`·`sources`(plan.md Structure Decision, research R-01)

---

## Phase 2: Foundational

**목적**: 모든 스토리가 쓰는 타입, 식별값 계산, 수집·보안 경계 확장, 스키마, 저장 경계와 그 두 구현. 이 단계가 끝나야 스토리 시험을 쓸 수 있다.

- [X] T003 [P] `tests/unit/sync/test_domain.py`: data-model 2절 타입의 생성·불변식 시험. `SourcePlan` 불변식("`holds`에 `ORIGIN_*`나 `INDEX_MISMATCH`가 있거나 `mode=TAKEDOWN_ONLY`면 `PROCESS` 결정이 없다",
  "보류가 막는 작업(2.4 허용표)의 결정은 없다") 위반은 생성 실패, `DocumentDecision`의 `chunked`가 `repr`에 본문을 내지 않음
- [X] T004 `src/qello_knowledge/domain/sync.py`: data-model 2.2~2.9를 표준 라이브러리 불변 dataclass·`StrEnum`으로 정의한다. `ChangeReason`(`NEW`, `INPUT_CHANGED`, `CHUNKING_CHANGED`, `REINSTATED`, `INDEX_CHANGED`),
  `DocumentOutcome`(`PROCESSED`, `PROCESSED_EMPTY`, `UNCHANGED`, `TAKEN_DOWN`, `PURGED`, `FAILED`, `HELD`, `SKIPPED`), `HoldReason`(`BUDGET_EXCEEDED`, `BUDGET_EXHAUSTED`, `INDEX_MISMATCH`, `TAKEDOWN_RATIO`,
  `ORIGIN_MISMATCH`, `ORIGIN_MISSING`, `COLLECTION_INCOMPLETE`), `TakedownReason`(보안 `security_path`·`security_secret`·`security_access`·`config_excluded`, 일반 `source_missing`·`not_target`·`source_disabled`와
  `is_security` 속성), `Action`(`PROCESS`, `UNCHANGED`, `TAKE_DOWN`, `PURGE`, `FAIL`, `HOLD`, `SKIP`), `DocumentDecision`, `SourcePlan`, `SyncPreview`, `SyncRunResult`, `ActivationCheck`.
  data-model 2.4 허용표를 `ALLOWED: Mapping[HoldReason, frozenset[작업]]` 상수 하나로 두고 `allowed(holds, 작업) -> bool`(여러 보류면 하나라도 막으면 막음)을 제공한다. 미리 보기와 실행이 이 함수만 쓴다
- [X] T005 [P] `tests/unit/sync/test_keys.py`: `chunk_input_hash`가 본문 해시·위치·원본 제목 각각에 반응하고 원본 버전에는 반응하지 않음, 원본 제목 `None`과 `""`가 같음, `doc_key`가 64자 16진수이고 자료원 이름·종류·식별자 각각에 반응,
  `index_version_id`가 기본 설정에서 결정적이고 네 재료 각각에 반응, `scope_key("github_repo_files", repo="Owner/Repo", ref="Main")`가 `github_repo_files:owner/repo@main`
- [X] T006 `src/qello_knowledge/sync/keys.py`: research R-03·R-08·R-10·R-12. `chunk_input_hash(content_hash, location, source_title)` = `sha256("qk-chunk-input-v1\0" + content_hash + "\0" + location + "\0" + (source_title or ""))` 16진수,
  `doc_key(source_name, source_kind, source_id)` = `sha256("qk-doc-v1\0" + …)` 16진수 전체, `METADATA_SCHEMA_VERSION = "meta-v1"`, `index_version_id(embedding_model, dimension, chunking_version, metadata_schema_version)` =
  `"iv-" + sha256("\0".join(...)).hexdigest()[:12]`, `scope_key(kind, scope)`(GitHub은 `<owner>/<repo>@<ref>` 소문자, 포함·제외 패턴 제외)
- [X] T007 [P] 수집 경계 시험: `tests/contract/source_adapter_contract.py`에 "`ListPage.origin`이 있으면 `origin_id`·`origin_name`은 비어 있지 않은 문자열"을 더하고, `tests/unit/sources/test_list_all.py`에
  "첫 페이지 `origin`이 `Listing.origin`으로 간다, 목록이 비거나 불완전·중단이어도 남는다"를, GitHub 재생 응답 시험(`tests/contract/test_github_adapter_contract.py` 또는 `tests/unit/adapters/`)에
  "저장소 응답의 `id`·`full_name`과 확정 커밋이 `origin`에 들어가고 요청 수가 그대로"를 더한다
- [X] T008 수집 경계 구현(research R-10, contracts/sync.md 3절): `src/qello_knowledge/domain/source.py`에 `SourceOrigin(origin_id: str, origin_name: str, version: str | None)`(앞의 둘 비어 있으면 `ValueError`),
  `ListPage.origin`·`Listing.origin`(`SourceOrigin | None = None`). `src/qello_knowledge/sources/collect.py`의 `list_all`이 첫 페이지 `origin`을 모든 반환 경로의 `Listing`에 담는다.
  `src/qello_knowledge/adapters/github.py`가 이미 받는 저장소 응답의 `id`(문자열로)·`full_name`과 확정 커밋으로 첫 페이지 `origin`을 채운다(`id`·`full_name`이 없으면 `None`, 응답 형식 오류로 바꾸지 않는다).
  `src/qello_knowledge/adapters/fake.py`는 시험 응답의 선택 필드 `origin`을 읽는다. 기존 시험은 그대로 통과
- [X] T009 [P] `tests/unit/security/test_screen_listing.py`: `screen_source()` 결과의 `listing`이 `list_all` 결과와 같다(항목·완전 여부·중단·`origin`), `source_excluded`가 기존 `_source_excluded`와 같은 결과
  (`./Docs/X.md`·대소문자 다른 패턴 사례 포함), 판정·요약·기록은 바뀌지 않음(기존 보안 시험 통과)
- [X] T010 QK-SEC-001 경계 구현(research R-18): `src/qello_knowledge/domain/security.py`의 `ScreenResult`에 `listing: Listing | None = None`(`repr=False`)을 더하고, `src/qello_knowledge/security/screen.py`의
  `screen_source()`가 채운다. 같은 파일에 공개 함수 `source_excluded(location, config) -> bool`을 두고 기존 `_source_excluded`는 그것을 부르게 한다(동작 같음)
- [X] T011 [P] `tests/localdb/sync/test_migration.py`: 0004 적용 뒤 data-model 1절 열·제약이 있다. 확인: `qk.artifact.location` 열, `qk.artifact.purge_pending` "NOT NULL DEFAULT '{}'", `takedown_reason` 검사 제약(1.1의 7개 값만),
  `processed_outcome`은 "`chunked`·`empty`·NULL", `qk.sync_source.source_kind` 유일, `qk.sync_run.status` 5개 값, `qk.sync_document_result` 기본 키 `(run_id, doc_key, action)`, 자식 행 `ON DELETE CASCADE`.
  기존 행이 있는 `qk.artifact`에 적용해도 값이 바뀌지 않고, 두 번째 적용은 변경 0(QK-STO-001 FR-017)
- [X] T012 `src/qello_knowledge/adapters/postgres/migrations/0004_sync.sql`: research R-02, data-model 1.1~1.4. 더하기만 하고 기존 열·제약·함수는 바꾸지 않는다(지우는 마이그레이션 아님). `qk.artifact` 추가 열 12개
  (`source_name`, `location`, `chunk_input_hash`, `processed_chunking_version`, `processed_index_version`(`qk.index_version(id)` 참조), `processed_outcome`, `last_seen_version`, `last_seen_at`, `takedown_reason`, `takedown_at`,
  `purge_pending text[] NOT NULL DEFAULT '{}'`, `purge_reason`), `qk.sync_source`, `qk.sync_run`, `qk.sync_run_source`(`holds text[] NOT NULL DEFAULT '{}'` 포함), `qk.sync_document_result`(`lines int[]` 포함)와
  `(source_name, doc_key, outcome)` 인덱스. 불변식 "`purge_pending <> '{}'` ⇔ `purge_reason IS NOT NULL`"은 검사 제약으로 둔다
- [X] T013 `src/qello_knowledge/ports/sync.py`: contracts/sync.md 2절 `SyncStore` Protocol과 입력·출력 타입(`IndexState`, `StoredDocument`(data-model 1.1 열, 본문 없음), `StoredSource`, `SyncLock`,
  `ArtifactWrite`(`location` 포함), `RunInfo`). 표준 라이브러리와 `qello_knowledge.domain`만 가져온다
- [X] T014 `src/qello_knowledge/adapters/postgres/store.py`: `replace_chunks`의 "이 인덱스 버전 청크 지우기 + 넣기 + 임베딩 id 찾기" 부분을 같은 모듈의 내부 함수(연결을 인자로 받음)로 빼서
  `sync_store.py`가 같이 쓸 수 있게 한다(research R-01). `replace_chunks` 동작·반환값은 그대로. `tests/localdb/store/test_replace.py` 등 기존 시험이 그대로 통과하는지 확인
- [X] T015 [P] `tests/unit/sync/fake_store.py`: `SyncStore`와 QK-STO-001 `Store`의 `find_embeddings`·`put_embedding`을 메모리로 구현한다. 연산마다 문서 하나 단위로 "전부 반영 또는 전부 취소"를 흉내 내고,
  지정한 `doc_key`의 지정한 연산에서 `StoreError`를 던지는 장애 주입과, 연산 호출 기록(검사용)을 제공한다. 쓰기 연산 수를 셀 수 있다(미리 보기 쓰기 0 검사)
- [X] T016 [P] `tests/localdb/sync/test_sync_store.py`: `PostgresSyncStore`의 기본 연산 시험. `ensure_index_version` 재실행 안전(`ready` 하나), `load_documents`가 본문 없이 상태 열을 돌려줌,
  `apply_document`가 원본 자료 행·이번 버전 청크·결과 행을 한 트랜잭션에 반영(청크 넣기 중 오류를 주입하면 원본 자료 행·결과 행도 없음), `mark_seen`, `record_outcome`, `begin_run`·`finish_source`·`finish_run`
- [X] T017 `src/qello_knowledge/adapters/postgres/sync_store.py`: `PostgresSyncStore`(연결은 `connection.connect(url)` autocommit, 문서 연산마다 `conn.transaction()`, 대상 원본 자료 행 `FOR UPDATE`, research R-04).
  이 단계에서 `index_state`, `ensure_index_version`, `load_documents`, `load_sources`, `begin_run`, `apply_document`, `mark_seen`, `record_outcome`, `finish_source`, `finish_run`을 구현한다.
  `apply_document`는 `qk.artifact.location`을 처리한 본문의 위치로 채우고 `load_documents`가 돌려준다. 접근 범위 대응: 도메인 `TEAM` → `'team'`, `RESTRICTED` → `'restricted'`, `UNKNOWN` → `NULL`. 오류는 QK-STO-001 `StoreError` 계열(`InvalidRecord`, `StoreUnavailable`)로 바꾸고 메시지에 접속 정보·본문을 넣지 않는다.
  내림·대기 삭제(US3), 잠금·활성화·정리·조회(US4·US5)는 뒤 단계에서 더한다

**Checkpoint**: `uv run pytest tests/unit/sync tests/unit/test_boundaries.py tests/unit/sources tests/unit/security tests/contract` 통과, `QK_REQUIRE_LOCALDB=1 uv run pytest tests/localdb` 통과.

---

## Phase 3: User Story 1 - 바뀐 문서만 다시 처리하고, 변경이 없으면 임베딩을 부르지 않는다 (P1) 🎯 MVP

**Goal**: 첫 동기화는 전부 처리, 재동기화는 변경 없음, 문서 하나 수정은 그 문서만. 실패·내림·예산·잠금은 뒤 스토리.

**Independent Test**: 가짜 자료원·가짜 임베딩·메모리 저장소로 두 번 동기화해 외부 임베딩 호출 수와 청크 교체 수를 세고, 문서 하나를 고쳐 다시 센다(quickstart 1절 "변경 판단").

- [X] T018 [P] [US1] `tests/unit/sync/helpers.py`: 가짜 자료원 설정·재생 응답을 만드는 도우미(문서 목록을 받아 `fake` 종류 자료원의 목록·본문 응답 생성, 원본 버전·접근 권한·`origin` 지정 가능), 동기화 의존성 묶음 조립 도우미
  (보안 정책, 기본 `ChunkingSettings`, `EmbeddingService` + `FakeEmbeddingProvider` + `InMemoryUsageLedger` + 메모리 저장소). 합성 Markdown만 쓴다
- [X] T019 [P] [US1] `tests/unit/sync/test_incremental.py`(spec US1 시나리오 1~6, SC-001·002·006, FR-005·008~011): 첫 동기화 5개 모두 `PROCESSED`·결과 기록 5건, 원본 그대로 재동기화 → 제공자 호출 0·청킹 호출 0
  (`chunk_screened` 감시)·`apply_document` 0·`UNCHANGED` 5건, 무변경 문서도 본문 조회 1회(보안 규칙 재판정), 커밋만 바뀐 원본 → `UNCHANGED`와 `source_version`·`source_url` 그대로·`last_seen_version` 갱신,
  문서 B 한 줄 수정 → B만 `INPUT_CHANGED`, 제목만·위치만 바뀐 사례 → `INPUT_CHANGED`, 청킹 규칙 버전만 다른 저장 상태 → `CHUNKING_CHANGED`, 새 문서 F → `NEW`, 빈 문서 → `PROCESSED_EMPTY`(청크 0개), 두 번 연속 실행 중복 0
- [X] T020 [US1] `src/qello_knowledge/sync/decide.py`: research R-03 변경 판정 `change_reason(stored, fingerprint, chunking_version, index_version) -> ChangeReason | None`(순서 `NEW` → `INPUT_CHANGED` → `CHUNKING_CHANGED` →
  `REINSTATED`(`status <> 'active'` 또는 접근 범위 `team` 아님) → `INDEX_CHANGED`, 준비 상태 인덱스 버전은 판정에 쓰지 않음)
- [X] T021 [US1] `src/qello_knowledge/sync/plan.py`: `plan_source()`(contracts/sync.md 1절, research R-18). `screen_source()` → 통과 문서마다 `chunk_input_hash` 계산과 `change_reason` → `PROCESS`로 판정된 문서만
  `chunk_screened()`에 넘김 → `DocumentDecision` 목록. 원본 제목은 `content.title or item.title`(`chunking/service.py:85`와 같은 값). 내림·보류 판정 자리는 비워 두고 US3·US5에서 채운다
- [X] T022 [US1] `src/qello_knowledge/sync/execute.py`: 쓰기 단계의 처리 경로(research R-17 1·3단계). 바뀐 문서마다 캐시 확인(`embedding.hashing.input_hash` + 모델 버전으로 `Store.find_embeddings`) → 모두 있으면
  `embed()` 없이, 아니면 `EmbedRequest`(문서 하나, `purpose=INDEX`, `origin=(source_name, location)`) → 모든 항목 벡터면 `apply_document`. `ChunkInput`의 `embedding`에 `EmbeddingRef`를 채운다.
  변경 없음 문서는 `mark_seen` 한 번. 캐시 직접 반영 문서의 임베딩 요약은 `requested` = `cache_hits` = 항목 수, `provider_calls` 0, `neurons` 0(data-model 2.8)
- [X] T023 [US1] `src/qello_knowledge/sync/run.py`: `run_sync()` 뼈대(contracts/sync.md 1절 3~5·7·8단계). 실행 전 점검·잠금은 주입한 함수로 받아 이 단계에서는 통과만 한다(US5에서 채움). `run_id` = `sync-<UTC 시각>-<무작위 8자>`,
  `begin_run` → 활성 버전 없으면 `ensure_index_version(index_version_id(...))` → 자료원마다 `plan_source` → `execute` → `finish_source`·`finish_run`(data-model 3.2 상태 규칙). `sync/__init__.py`에서 `run_sync` 공개
- [X] T024 [P] [US1] `tests/localdb/sync/test_incremental_db.py`(SC-001·002, 로드맵 1.G): 로컬 DB와 `PostgresStore`·`PostgresSyncStore`로 첫 동기화 → 준비 버전 청크가 생김(시험 안에서만 그 버전을 SQL로 활성화해 검색 확인) →
  무변경 재동기화의 제공자 호출 0·청크 식별자 그대로 → 문서 하나 수정 시 그 문서의 청크만 새 식별자

**Checkpoint**: US1 시험 통과. 변경 없는 재동기화 임베딩 호출 0을 메모리·로컬 DB 양쪽에서 확인.

---

## Phase 4: User Story 2 - 문서 하나씩 통째로 바꾸고, 실패한 문서는 이전 청크를 지킨다 (P1)

**Goal**: 청킹·임베딩·저장 실패 격리, 실행 소진 상태, 끊김 뒤 일관성.

**Independent Test**: 실패를 주입해 실패 문서의 검색 결과·저장 상태·다음 판단이 이전 그대로이고 다른 문서는 처리되는지 본다(quickstart 1절 "원자 반영").

- [X] T025 [P] [US2] `tests/unit/sync/test_failures.py`(spec US2 시나리오 1~4·6, FR-014·025, research R-17): 문서 B 청크 하나에 `INPUT_TOO_LONG` → B만 `FAILED(embed, input_too_long)`·A 반영·C 변경 없음, 원인 제거 뒤 B만 처리,
  청킹 실패(줄 길이 초과) → `FAILED(chunk, line_too_long)`, `PROVIDER_QUOTA`·`INDEX_BUDGET`·`USAGE_UNAVAILABLE` 항목 실패와 `usage_unavailable` 경고(정산 실패)와 `EmbedError`(`AUTH_CONFIG`·`USAGE_UNAVAILABLE`)
  각각의 뒤로 제공자 호출 0·캐시에 없는 문서 `HELD(BUDGET_EXHAUSTED)`·캐시 완비 문서 반영, 정산 실패 사례에서 이미 받은 벡터로 끝나는 문서는 반영, 사용량 장부 `today()` 실패에서도 캐시 완비 문서 반영
- [X] T026 [P] [US2] `tests/localdb/sync/test_atomic.py`(SC-004·006·014): `apply_document` 청크 넣기 중 오류 → 원본 자료 행(지문·처리 버전·접근 범위·상태)·청크·결과 행 모두 이전 그대로이고 다음 실행이 다시 `PROCESS`,
  새 묶음 일부만 검색되는 순간 없음(반영 트랜잭션 중 다른 연결의 검색은 이전 묶음), 문서 반영 직전·직후와 `finish_run` 직전에 프로세스 끊김을 흉내(연결 강제 종료)한 뒤 반영된 문서와 결과 행이 어긋난 경우 0,
  끊김 뒤 같은 동기화 재실행 결과가 끊기지 않은 실행과 같음
- [X] T027 [US2] `src/qello_knowledge/sync/execute.py`: research R-17 2·3단계 실행 소진 상태(실행 전체에 하나, `execute`에 넘겨 다음 자료원까지 유지). 켜는 신호: 항목 실패 `PROVIDER_QUOTA`·`INDEX_BUDGET`·`USAGE_UNAVAILABLE`,
  요약 경고 `usage_unavailable`, `EmbedError`. 켜진 뒤 캐시에 없는 청크가 있는 문서는 `record_outcome(HOLD, BUDGET_EXHAUSTED)`. 청킹 실패는 `FAILED(chunk, <유형>)`, `apply_document`의 `StoreError`는 `FAILED(store, <오류 종류>)`이고
  `StoreUnavailable`이면 실행을 멈추고 남은 문서는 결과를 남기지 못할 수 있음(최종 상태 없이 남아 다음 실행이 `unfinished`로 닫는다)

**Checkpoint**: US1·US2 시험 통과.

---

## Phase 5: User Story 3 - 검색에 나오면 안 되게 된 문서는 내린다 (P1)

**Goal**: 보안 내림 우선, 일반 내림, 삭제 대기, 내림 비율, 보류 사유별 허용표, 지운 자료원.

**Independent Test**: 로컬 DB에서 지운 문서·권한 미확인·비밀값·제외 패턴 문서가 검색에 안 나오고 보안 사유 문서의 청크 행이 없는지, 불완전 목록에서 일반 내림 0인지 본다(quickstart 1절 "내림").

- [X] T028 [P] [US3] `tests/unit/sync/test_takedown_decide.py`(research R-05·R-18, data-model 2.4): 사유별 판정(보안 필터 경로 제외·비밀값·접근 보류 → 보안 사유와 규칙 이름·줄 번호, 저장된 위치가 제외 패턴 →
  `config_excluded`(목록 불완전이어도), 포함 패턴에서만 빠짐·목록에 없음 → 목록이 완전할 때만 `source_missing`, `NOT_MARKDOWN` → `not_target`, 판정 실패·본문 조회 실패 → 내림 아님), 제외와 포함 이탈이 겹치면 `config_excluded`,
  제외 패턴 대소문자·`./` 정규화 사례, 비율 판정(기준 = 일반 사유로 내려지지 않은 저장 문서 수, 기준 0이고 대상 ≥ 1이면 초과, 20% 경계값 양쪽), 허용표 모든 칸(보류 7종 × 작업 7종, 여러 보류 조합)
- [X] T029 [P] [US3] `tests/localdb/sync/test_takedown.py`(spec US3 시나리오 1~9, SC-003·005·015): 지운 문서 → 검색·문맥 확장 0·청크 행 유지·`source_missing`, 권한 미확인·비밀값·설정 제외 → 검색 0·그 문서 모든 버전 청크 행 0
  (`body`·`search_text` 함께), 불완전 목록·수집 중단 → `source_missing` 0·실행 `stopped`·이미 판정된 보안 내림은 적용, 비율 초과 → 일반 내림 0·보안 내림은 검색 제외 + `purge_pending`·`purge_reason`,
  확인 옵션 실행 → 대기 본문 0(그 사이 원본에서 사라진 문서 포함), 준비 버전 둘에 청크가 있는 문서를 삭제 보류한 뒤 본문을 고쳐 한 버전만 다시 처리 → `active` + 다른 버전 대기 유지·확인 옵션 뒤 0,
  한 실행 안 `PURGE`→`PROCESS`·`PURGE`→`UNCHANGED`·일반 내림 뒤 `PURGE`의 결과 행이 작업마다 하나, 빈 문서 보안 내림 비율 보류 시 대기 목록·사유 비움, 내려진 문서가 다시 팀 공용이면 `REINSTATED`로 처리,
  설정에서 지운 자료원 → `TAKEDOWN_ONLY`로 `source_disabled`, 비공개 전환(전체 접근 보류)·인덱스 버전 불일치·예산 초과 각각에 비밀값 문서를 더한 실행에서 보안 사유 문서 검색 0
- [X] T030 [US3] `src/qello_knowledge/adapters/postgres/sync_store.py`: `take_down`(일반: `status='deleted'`·사유·결과 행, 청크 유지 / 보안 삭제 허용: 접근 범위 판정값·모든 인덱스 버전 청크 행 삭제·`purge_pending='{}'`·`purge_reason` NULL /
  보안 삭제 보류: 청크가 남은 버전 목록과 사유, 남은 청크가 없으면 둘 다 비움), `purge_pending_bodies`(목록의 버전 청크만 삭제, 상태는 그대로), `apply_document`의 `purge_pending`에서 이번 버전 빼기(비면 사유도 비움).
  모두 문서 하나 = 트랜잭션 하나, 결과 행 포함(research R-04 표)
- [X] T031 [US3] `src/qello_knowledge/sync/decide.py`·`plan.py`: research R-18 내림 판정(`ScreenResult.verdicts`, `ScreenResult.listing`의 완전 여부·중단, 저장된 문서의 `source_excluded`·`in_scope(location, include, ())`),
  `TakedownReason`, 비율 판정(research R-05, 확인 옵션 `confirm_takedown`), `COLLECTION_INCOMPLETE` 보류, `mode=TAKEDOWN_ONLY` 계획(설정에서 빠졌거나 꺼진 저장 자료원, `source_disabled`). 메모리 저장소 구현(T015)에도 내림 연산을 맞춘다
- [X] T032 [US3] `src/qello_knowledge/sync/execute.py`·`run.py`: 쓰기 순서(contracts/sync.md 1절 7단계) 보안 내림 → 일반 내림 → 대기 본문 지우기 → 처리 → `mark_seen` → 보류·건너뜀·실패 기록. 각 작업은 `domain.sync.allowed(holds, 작업)`로만 거른다.
  `INDEX_MISMATCH`(활성 버전이 있고 현재 설정 버전과 다름) 판정을 `run.py` 4단계에 넣는다. 수집 중단으로 본문을 받지 못한 문서는 `SKIP`

**Checkpoint**: US1~US3 시험 통과. 1.G의 "지운 문서·접근 범위 미확인 문서가 검색되지 않는다"를 로컬 DB로 확인.

---

## Phase 6: User Story 4 - 실행 전에 비용을 보고, 실행 뒤에 무엇을 했는지 안다 (P2)

**Goal**: 미리 보기(쓰기 0), 실행 전체 예산 판정, 실행 기록의 요약·내부 식별값·보안 근거·수집 요약, 원문 비노출.

**Independent Test**: 미리 보기 뒤 실제 실행의 대상 집합을 비교하고, 실패 주입 실행의 기록을 문서별 결과와 대조한다(quickstart 1절 "미리 보기·예산", "실행 기록").

- [X] T033 [P] [US4] `tests/unit/sync/test_preview_budget.py`(spec US4 시나리오 1~3, SC-007·008, FR-022~025): 미리 보기 쓰기 연산 0·제공자 호출 0(확인 옵션·부분 실행 옵션을 준 미리 보기 포함), 같은 상태 실제 실행과 처리·변경 없음·내림 대상 집합 100% 일치,
  실패 없는 통제 시험에서 처리 성공 수도 같음, 예상 Neurons와 계산 근거가 `EmbedPreview`와 같음, 예산 초과 + 옵션 없음 → 제공자 호출 0·`apply_document` 0·보안 내림·일반 내림·`mark_seen`은 함·종료 상태 `stopped`,
  두 자료원 각각은 예산 안이지만 합계가 넘으면 둘 다 보류, `--allow-partial-budget` → 예산 안 문서만 반영
- [X] T034 [P] [US4] `tests/unit/sync/test_run_record.py`(spec US4 시나리오 4·5, SC-009, FR-026~028): 요약 수치 = 결과 행 수(작업별·사유별·보류별), 수집 요약(`FetchResult.to_dict()`에서 항목 목록 제외)·필터·청킹·임베딩 요약 있음,
  캐시 직접 반영 문서가 임베딩 요약의 요청·캐시 적중 수에 들어감, 보안 내림 결과에 규칙 이름·줄 번호만, 표지 문자열(`QK-SYN-001-LEAK-MARKER`)과 합성 비밀값을 본문·오류 메시지에 넣은 실행에서 실행 기록·`--json` 출력·`caplog` 전체에 표지·비밀값·토큰 모양·주소 0,
  원본 식별자가 출력 규칙에 걸려 가려진 문서와 처음 처리에 실패한 새 문서를 `doc_key`로 다음 목록에서 다시 찾음
- [X] T035 [US4] `src/qello_knowledge/sync/preview.py`: `preview()`(research R-07, data-model 2.7). 모든 대상의 `SourcePlan`을 받아 처리할 문서의 임베딩 입력을 모아 `Embedder.preview()` 한 번, 허용표(`allowed`)로 행동별 예정 수 계산,
  인덱스 버전 상태. 잠금·실행 기록·기준값 등록·저장소 쓰기 없음. `sync/__init__.py`에서 공개
- [X] T036 [US4] `src/qello_knowledge/sync/run.py`: contracts/sync.md 1절 5·6단계. 모든 대상의 `plan_source`를 먼저 만들고 실행 전체 예상량으로 `Embedder.preview()`를 한 번 불러, 실행 불가이고 부분 실행 옵션이 없으면 모든 자료원에
  `BUDGET_EXCEEDED` 보류(research R-17)
- [X] T037 [US4] `src/qello_knowledge/sync/report.py`: 자료원·실행 요약 만들기(data-model 2.8, contracts/cli.md 4절 JSON 키), `doc_display`는 QK-SEC-001 `policy.output_context(kind)`로 원본 식별자에 기록 출력 규칙 적용,
  사람용 출력. `sync_store.py`의 결과 행에 `rule`·`lines`·`change_reason`을 채우고 `finish_source`·`finish_run`의 `summary`에 요약을 넣는다

**Checkpoint**: US1~US4 시험 통과.

---

## Phase 7: User Story 5 - 정해진 주기로 돌고, 명령 하나로 다룬다 (P2)

**Goal**: 실행 전 점검과 자료원 식별, 종류별 잠금·끝나지 않은 기록, 첫 인덱스 버전 활성화, 실행 기록 조회·정리, `qk-index` 명령, 주기 실행 워크플로.

**Independent Test**: CLI를 가짜 자료원·가짜 임베딩·로컬 DB로 돌려 종료 코드와 출력을 보고, 같은 종류 두 실행을 겹치고, 워크플로 파일 내용을 검사한다(quickstart 1절 "동시 실행", "정체성·점검", "점검 무쓰기", "주기 실행 정의").

- [X] T038 [P] [US5] `tests/unit/sync/test_identity.py`(FR-002, SC-011, research R-10): 같은 종류 활성 자료원 둘 → 점검 실패·원본 요청 0·쓰기 0, 같은 이름의 `scope_key` 다름 → 실패, 저장된 A를 설정에서 지우기만 함 → `TAKEDOWN_ONLY`,
  A를 지우고 같은 종류 B를 추가 → 첫 쓰기 전 실패, 수집 뒤 `origin_id`만 다름·`origin_name`만 다름·`origin` 없음 → 그 자료원 처리 0·일반 내림 0·`mark_seen` 0·보안 내림은 함, 기준값 없는 첫 실행 → 첫 문서 쓰기 직전 등록,
  첫 실행에서 일부 문서를 반영한 뒤 끊고 정체성을 바꿔 재실행 → 바뀐 정체성을 기준값으로 받지 않음, 빈 목록·불완전 목록에서도 `origin`·원본 버전이 실행 기록에 남음, 미리 보기 뒤 기준값 없음
- [X] T039 [P] [US5] `tests/localdb/sync/test_concurrency.py`(FR-029, SC-010·014, research R-06): 같은 자료원 두 동기화를 겹치면 하나는 종료 코드 6·쓰기 0, 같은 종류·다른 이름·같은 원본 식별자 두 자료원(설정 파일 둘)의 동시 첫 실행에서 하나만 진행,
  잠금을 쥔 연결을 강제로 끊은 뒤 다음 실행이 진행되고 이전 `running` 기록을 `unfinished`로 닫음, 다른 종류 자료원의 `running` 기록은 그대로, 동기화 중 첫 버전 활성화 거부, 실행 중 `runs prune`이 `running` 기록을 남김
- [X] T040 [P] [US5] `tests/localdb/sync/test_index_version.py`(FR-019~021, SC-014, research R-08·R-09): 활성 버전 없음 → 준비 버전 하나 생성·재사용, 활성화 전 변경 없는 재실행 `PROCESS` 0, 활성화 전 설정 변경 → 새 준비 버전에 모든 문서 처리(`INDEX_CHANGED`),
  활성화 조건 (1)~(5) 각각 못 채운 경우 거부와 실패 조건 이름(옛 준비 버전, 마지막 실행 `partial`·`stopped`·`unfinished`·`running`, 검색될 문서 0, 벡터 없는 청크), 조건 충족 시 활성화와 검색 결과, 활성 버전이 있으면 거부,
  동기화가 활성화한 경우 0, 활성 버전과 현재 설정이 다르면 `INDEX_MISMATCH`로 교체 0·일반 내림 0·보안 검색 제외 적용
- [X] T041 [P] [US5] `tests/unit/indexer/test_run_cli.py`(US5 시나리오 1~3·5~7, FR-030~033, contracts/cli.md): `qk-index run`·`run --preview`·`runs list`·`runs show --failures`·`runs prune`·`index status`·`index activate`의 출력과 종료 코드 0~6,
  설정·자료원·개인 정보 확인 기록·보안 규칙·예산 설정 점검 실패와 원격 대상 `--allow-remote` 없음(종료 코드 3)과 `config/store_policy.toml` 없음(종료 코드 1)에서 원본 요청 0·저장소 쓰기 0, `--preview`와 `--trigger` 함께 → 인자 오류,
  `runs prune --retention-days 0` 거부, 기존 하위 명령(`check`, `sources check`, `security check`, `usage`, `usage prune`) 출력·종료 코드 회귀(`tests/unit/indexer/test_cli.py`·`test_cli_usage.py` 그대로 통과).
  **2026-10-21 사용자 승인 예외**: 기존 `test_cli.py`의 정상 run 경로 3개에만 가짜 의존성을 주입하고 새 출력에 맞춘다(점검 통과 검증 유지, 실패 경로·다른 명령은 그대로).
  의존성(전송·임베딩 제공자·저장소)은 `main()`의 주입 인자로 바꿔 끼운다(`ledger_factory`와 같은 방식). 고정 입력은 `tests/fixtures/sync/`(가짜 자료원 설정·개인 정보 확인 기록·재생 응답)
- [X] T042 [P] [US5] `tests/unit/indexer/test_schedule_workflow.py`(FR-034~037, research R-14): `.github/workflows/index-sync.yml`을 줄 단위 텍스트로 읽어(새 의존성 없음) `schedule` cron `30 0 * * *`, `workflow_dispatch`,
  `if: vars.QK_SYNC_ENABLED == 'true'`, `permissions: contents: read`, `concurrency` `index-sync`·`cancel-in-progress: false`, `timeout-minutes: 30`, `persist-credentials: false`, `uv sync --locked --extra index --extra postgres`,
  `qk-index run --allow-remote --trigger schedule --json`, `if: always()`인 `usage prune --allow-remote`·`runs prune --allow-remote`, Secret 이름 `DATABASE_URL`·`QK_GITHUB_API_TOKEN`(→ `GITHUB_API_TOKEN`)·`CLOUDFLARE_API_TOKEN`·`CLOUDFLARE_ACCOUNT_ID`이 `secrets.`로만 쓰이고 값 모양 문자열이 없음
- [X] T043 [US5] `src/qello_knowledge/sync/identity.py`·`run.py`: research R-10 (a)~(d) 점검(잠금 전과 잠금 뒤 두 번), 대상 자료원 목록(`FULL`·`TAKEDOWN_ONLY`, `--source` 선택), 수집 뒤 정체성 비교와 `ORIGIN_MISMATCH`·`ORIGIN_MISSING` 보류,
  첫 문서 쓰기 직전 `register_origin`. `sync_store.py`에 `register_origin`(종류 유일 제약 위반은 `StoreError`)
- [X] T044 [US5] `src/qello_knowledge/adapters/postgres/sync_store.py`·`sync/run.py`: research R-06 잠금. `try_lock(source_kinds)`는 같은 연결에서 종류별 `pg_try_advisory_lock`과 전역 `qk-sync-index` `pg_try_advisory_lock_shared`(키는 고정 문자열의 `hashtext`나 상수),
  하나라도 실패하면 잡은 것을 놓고 `None`. `begin_run`이 잠근 종류의 `running` 기록을 `unfinished`로 닫는다. 잠금 연결은 실행 내내 유지하고 재연결하지 않는다. 미리 보기는 잠그지 않는다
- [X] T045 [US5] `src/qello_knowledge/adapters/postgres/sync_store.py`·`src/qello_knowledge/sync/activate.py`: research R-09 `activation_check`, `activate`(전역 배타 잠금 안 한 트랜잭션, 조건 (1)~(5), 실패 조건 이름 목록), `activate_first_index()` 공개.
  `list_runs`, `run_detail`, `run_failures`, `prune_runs(retention_days)`(`status <> 'running'`, 기간 1 이상, 함수 하나 = 트랜잭션 하나, 두 번째 실행 0건, `qk.sync_source`는 지우지 않음)
- [X] T046 [US5] `src/qello_knowledge/indexer/sync_cli.py`·`src/qello_knowledge/indexer/cli.py`: contracts/cli.md 1~4절. `qk-index run`을 동기화 실행으로 바꾸고(기존 점검 단계·옵션 유지), `--preview`, `--trigger`, `--allow-remote`, `--allow-partial-budget`,
  `--confirm-takedown`, `--source`, `--json`, `--env-file`; `runs list|show|prune`, `index status|activate` 하위 명령. 원격 대상 판정은 `adapters/postgres/connection.target_label`, 원격이면 `--allow-remote`와 `config/store_policy.toml`
  (필수 항목: 제공자, 확인 날짜, 결정 기록 경로) 확인(research R-13). 의존성 조립(`GitHubRepoFilesAdapter`·`HttpsTransport`, `WorkersAiRestProvider`, `PostgresUsageLedger`, `PostgresStore`, `PostgresSyncStore`)은 이 파일에서만 하고 주입 인자로 바꿀 수 있게 한다.
  종료 코드 research R-16(4와 5가 함께면 5)
- [X] T047 [US5] `.github/workflows/index-sync.yml`: contracts/cli.md 5절 그대로. 저장소 변수 `QK_SYNC_ENABLED`가 없으면 작업이 건너뛰어진다는 주석과, Secret·변수 등록은 사람 단계 H07이라는 주석을 단다

**Checkpoint**: 전체 단위·로컬 DB 시험 통과.

---

## Phase 8: Polish & Cross-Cutting

- [X] T048 [P] `tests/localdb/sync/test_perf.py`(SC-013, research R-15): `tests/unit/chunking/test_perf.py`의 시드 `20261021` 합성 문서 79개 생성기를 재사용(가져오거나 같은 도우미로 옮김)해 가짜 자료원으로 넘기고,
  빈 로컬 DB 첫 동기화와 이어서 변경 없는 동기화를 각각 3번 반복한 중앙값이 60초·30초 이하. 회귀 감시이고 측정 장비는 실행 기록에 남긴다
- [X] T049 [P] `specs/QK-SYN-001-incremental-sync/quickstart.md`: 구현과 다른 명령·옵션·시험 파일 이름이 있으면 고친다(계약과 다르면 계약을 먼저 고치고 사람 승인). 4절 추적표의 시험 사례 이름을 실제 시험 함수에 맞춘다
- [X] T050 기본 검증(AGENTS.md 7절): `python scripts/preflight.py`, `git diff --check`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run qk-dev db up`, `uv run qk-migrate`(두 번째 `applied=0`), `QK_REQUIRE_LOCALDB=1 uv run pytest`.
  실패는 원인을 고치고 시험을 지우거나 건너뛰지 않는다. 실행 결과(통과 수, 소요)를 이 파일 끝 실행 기록에 남긴다

---

## 사람 단계 (구현 뒤, quickstart 3절)

각 단계는 사람의 승인 뒤에만 한다(AGENTS.md 3.5, spec FR-033·FR-036). H01~H03은 이 작업의 완료 판정(spec SC-012)에 쓴다.

- [X] H01 로컬 DB에 실제 자료원 미리 보기: `uv run qk-index run --preview --json`(GitHub 약 83회, 0 Neurons). 처리 예정 문서 수와 예상 Neurons를 기록하고 실행 승인을 받는다
- [X] H02 로컬 DB에 첫 실제 색인과 재실행: `uv run qk-index run --json` 두 번(예상 약 325 Neurons, H01 값으로 확인). 두 번째 `embedding.provider_calls == 0`. spec SC-012 측정 조건(대상 커밋, 보안·청킹 규칙 버전, 인덱스 버전, 실행 환경, 날짜)과 원본 요청 수, 소요 시간, 처리 문서 수, 청크 수, 소비 Neurons를 기록
- [X] H03 로컬 DB에서 `qk-index index status` → `qk-index index activate <버전>` → 검색 확인(질의 임베딩 소량). 활성화 요약과 검색 결과 출처 기록
- [ ] H04 운영 저장소 제공자 데이터 처리 정책 확인(ADR-008·ADR-019에 출처·조회일)과 `config/store_policy.toml` PR
  - 2026-10-22 기록(SCRUM-103·#50): 운영 저장소는 팀원 테넌시(PAYG, `ap-osaka-1`)의 OCI A1 공유 인스턴스 위 자체 운영 PostgreSQL이다. 정책 확인 결과는 ADR-008 "데이터 처리 정책" 절, ADR-019에 적었고
    `config/store_policy.toml`을 더했다(2026-10-23 사용자 승인). 남은 것: 팀원 계정이 동의한 Cloud Services Agreement 판 확인, PR 리뷰.
- [X] H05 운영 저장소 연결이 세션 advisory lock을 유지하는 직접 연결인지 확인(research R-06 남는 위험)
  - 2026-10-23: 연결 풀러가 없다. 예약 실행은 같은 인스턴스의 systemd 타이머(ADR-020)에서 `127.0.0.1:5432`로, 로컬 CLI는 OCI Bastion 경유 SSH 터널로 PostgreSQL에 직접 붙는다.
    마이그레이션·첫 색인을 이 터널로 실행했다. 두 실행을 동시에 띄워 잠금 거절을 보는 시험은 하지 않았다.
- [X] H06 운영 저장소 첫 실제 색인(`--allow-remote`)과 활성화(H02와 같은 Neurons, spec SC-012)
  - 2026-10-23 조건: 대상 커밋 `6aeccd039b825dcd7a2b6c046a34ef72089a1f78`, 규칙 `sec-7222e5dd1d6e`, 청킹 `chk-md-20d966f730bb`, 인덱스 `iv-4c0bc4fcc642`,
    운영 DB `supabase/postgres:17.11.0.004`(pgvector 0.8.2·PGroonga 3.2.5), 작업자 PC에서 터널 경유. 마이그레이션 0001~0004 `applied=4`, 재실행 `applied=0`.
  - 미리 보기: 문서 80(PASSED 79·SECRET_BLOCKED 1), 청크 1,291, 원본 요청 83, 예상 368.93 Neurons, 임베딩 호출 0.
  - 1회차 `sync-20261023T075442-2f24051c`: PROCESS 79·SKIP 1, 청크 1,291, 제공자 호출 94, **894.50 Neurons**(H02와 같음). 2회차 `sync-20261023T080122-16d16ba5`: UNCHANGED 79, 제공자 호출 0, 0 Neurons.
  - `qk-index index activate iv-4c0bc4fcc642 --allow-remote`: 문서 79, 청크 1,291, 벡터 없는 청크 0, 실패 조건 없음. `index status`: active=current, matches=true.
- [ ] H07 GitHub Actions 무료 할당 확인, Secret 등록, 저장소 변수 `QK_SYNC_ENABLED=true`, 첫 예약 실행 결과 확인
  - 2026-10-23: 저장소가 공개라 GitHub Actions 셀프 호스티드 러너 대신 OCI 인스턴스의 systemd 타이머로 예약 실행한다(ADR-020, 사용자 결정). 이 항목의 "GitHub Actions 무료 할당 확인, Secret 등록,
    `QK_SYNC_ENABLED`"는 타이머 구성·비밀값 파일·첫 타이머 실행 확인으로 바꾼다. `index-sync.yml`은 쓰지 않고 남겨 둔다. 남은 것: 타이머 설치, 비밀값 입력(사람), `main` 병합 뒤 첫 실행 확인.

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

### 2026-10-21 실행 세션 — Phase 1 / Phase 2 시작 전 BLOCKED

- 시작: `git status --short` 출력 없음, 브랜치 `feat/SCRUM-102-gh-48-incremental-sync`, HEAD `2367a72` 확인. 이 세션은 실행만 맡고 커밋·독립 리뷰는 Claude 세션에 남긴다.
- Phase 1: T001의 패키지·시험 디렉터리와 격리 DB용 `db_url`·`store` 재사용 기반을 만들었다. T012/T017 이후 추가할 `sync_store` 픽스처가 없으므로 T001은 아직 체크하지 않았다.
- T002 RED: `uv run pytest tests/unit/test_boundaries.py -q` → 9 failed, 4 passed(새 `sync_violations` 미정의). GREEN: 같은 명령 → 13 passed, 0.12초.
  절대·상대 import, `from qello_knowledge import adapters` 우회, 허용 import를 검사한다. 기존 시험 본문은 변경하지 않았다.
- 실행 환경: 모든 uv 명령에 `UV_CACHE_DIR=/private/tmp/qk-syn-uv UV_OFFLINE=1`. 최초 기본 캐시 접근은 샌드박스 권한 오류였고 임시 캐시로 해소했다.
- Phase 2 사전 인터페이스 대조에서 BLOCKED: T013 `StoredDocument`/T017 `load_documents`가 T031/R-18에 넘겨야 하는 **저장된 위치**를 승인된 저장 스키마가 보존하지 않는다.
  기존 `0001_initial_schema.sql`의 `qk.artifact`·`ArtifactRecord`에 `location`이 없고 data-model 1.1/T012의 추가 열 11개에도 없다. 위치는 `qk.chunk.locator`에만 둘 수 있는데,
  FR-011 빈 문서는 청크 0개이고 FR-015 보안 삭제는 청크를 모두 지운다. 이때 원본 목록도 불완전하면 현재 목록에서도 위치를 복구할 수 없다.
  공통 `SourceItem`에서 `source_id`와 `location`은 별도 값이므로 원본 식별자를 위치로 대신 쓰는 것은 일반적으로 성립하지 않는다.
  R-18/FR-016 (2)는 목록 완전 여부와 상관없이 저장된 위치로 `config_excluded`를 판정하도록 요구한다.
- 사람 결정 필요(사용자 지시/T049): 권장안은 0004에 원본 위치를 보존하는 열을 추가하고 data-model 1.1, T012/T013, 쓰기·조회 계약을 함께 승인하는 것이다.
  대안은 `source_id == location`인 자료원으로 이 동작을 제한하거나 위치를 알 수 없는 문서의 처리 정책을 따로 승인하는 것이며, 공통 형식·FR-016 요구사항 조정이 필요하다.
  승인된 산출물은 고치지 않았고 Phase 2 구현·추가 시험은 시작하지 않았다. H01~H07, 외부 호출, 스테이징·커밋·push·브랜치 변경 없음.
- BLOCKED 시 기본 검증(T050 명령 실행, T050 완료 판정 아님):
  - `python scripts/preflight.py` → PASS, 504개 텍스트 파일 검사.
  - `git diff --check` → PASS.
  - `uv run ruff check .` → PASS.
  - `uv run ruff format --check .` → PASS, 338개 파일.
  - `COMPOSE_DISABLE_ENV_FILE=1 uv run qk-dev db up --env-file /dev/null` → PASS. 최초 Docker 소켓 권한 오류 뒤 자동 승인된 로컬 권한 실행으로 해소.
  - 임시 `qk_test_<무작위>` DB에서 `uv run qk-migrate --env-file /dev/null` 두 번 → PASS, 첫 `applied=3 skipped=0`, 다음 `applied=0 skipped=3`; 끝에 임시 DB 삭제.
    접속 설정은 메모리에서만 전달하고 출력하지 않았다. 0004는 구현 전이므로 이 검증에 포함되지 않는다.
  - `COMPOSE_DISABLE_ENV_FILE=1 QK_REQUIRE_LOCALDB=1 uv run pytest -q` → PASS, **1108 passed, 2 deselected, 8.50초**. 제외 2개는 기존 기본 설정의 external 시험이다.
    최초 샌드박스 실행은 로컬 DB 소켓 제한으로 2 failed, 1020 passed, 86 errors였으며 자동 승인된 로컬 권한 재실행에서 해소됐다. 새 skip·xfail·경고 suppress 없음.
- 계산한 첫 설정 버전: `iv-4c0bc4fcc642`(모델 `@cf/baai/bge-m3`, 차원 1024, 청킹 `chk-md-20d966f730bb`, 메타데이터 `meta-v1`). DB에 생성·활성화하지 않았다.
  평가 세트 해당 없음, 성능 시험 T048 미실행(동기화 구현 전), 실제 사용량 0 Neurons.
- 한계: 위 검증은 현재 Phase 1 변경과 기존 구현을 대상으로 한다. QK-SYN-001 요구사항 완료·독립 리뷰 통과·병합 가능 판정이 아니다.

### 2026-10-21 재개 — Phase 1·2

- 사용자 승인 location 보완을 확인. 시작 브랜치·HEAD 동일; 앞 실행 및 사람이 보완한 TASK/data-model/research/tasks 변경을 보존했다.
- T001 완료: 0004 포함 격리 DB·store·sync_store 픽스처. T002 앞 실행 RED/GREEN 재사용.
- T003/T004: `uv run pytest tests/unit/sync/test_domain.py -q` RED 모듈 미구현 수집 오류 1건 → GREEN 22 passed.
- T005/T006: `uv run pytest tests/unit/sync/test_keys.py -q` RED 모듈 미구현 수집 오류 1건 → GREEN 4 passed. 첫 버전 `iv-4c0bc4fcc642`.
- T007/T008: `uv run pytest tests/unit/sources/test_list_all.py tests/contract/test_github_adapter_contract.py -q` RED 4 failed/10 passed → 계약 전체 포함 GREEN 46 passed.
- T009/T010: `uv run pytest tests/unit/security/test_screen_listing.py -q` RED 5 failed → 보안 전체 GREEN 142 passed.
- T011/T012: `QK_REQUIRE_LOCALDB=1 uv run pytest tests/localdb/sync/test_migration.py -q` RED 2 failed → GREEN 2 passed.
- T013~T017: 경계 타입·메모리 저장소·DB 저장 구현. T016 RED 미구현 모듈 수집 오류 1건 → `QK_REQUIRE_LOCALDB=1 uv run pytest tests/localdb/sync -q` GREEN 5 passed.
  store.py는 청크 SQL 블록만 내부 함수로 분리; 기존 `tests/localdb/store/test_replace.py` 6 passed.
- Phase 2 Checkpoint: `uv run pytest tests/unit/sync tests/unit/test_boundaries.py tests/unit/sources tests/unit/security tests/contract -q` 399 passed(0.52초);
  `QK_REQUIRE_LOCALDB=1 uv run pytest tests/localdb -q` 91 passed(6.77초).
- 환경: 오프라인 uv 임시 캐시 유지, 로컬 DB 시험만 소켓 권한으로 실행, DB는 무작위 qk_test 이름으로 생성·삭제. 실제 .env/외부 API 사용 없음. 독립 리뷰·커밋 없음.

### Phase 3·4 — US1·US2

- Phase 3 T019 RED: `uv run pytest tests/unit/sync/test_incremental.py -q` 미구현 run 모듈 수집 오류 1건 → GREEN 4 passed.
  테스트 조립 도우미의 전송 직전 검사 호출 인자를 기존 경계에 맞게 수정했다(검사 생략 없음).
- T024 통합 시험은 흐름 뼈대 구현 뒤 추가해 실제 PostgreSQL의 청크 식별자·검색·임베딩 호출을 검증했다. 단위 시험 RED는 구현 전 확인했으나 통합 시험 작성 순서는 작업 목록보다 늦었다.
  통합·단위 동시 수집 시 기본 pytest import 모드에서 두 sync 시험 패키지가 충돌했다. 허용된 두 __init__.py에서 시험 패키지 경로를 함께 검색하게 하여 해결; 설정 파일 변경 없음.
- Phase 3 Checkpoint: `QK_REQUIRE_LOCALDB=1 uv run pytest tests/localdb/sync/test_incremental_db.py tests/unit/sync -q --tb=short` 31 passed.
- Phase 4 T025 RED: `uv run pytest tests/unit/sync/test_failures.py -q --tb=short` 6 failed → GREEN(단위 sync 전체) 36 passed.
  입력 한도·잘못된 응답·청킹·저장 실패 격리, 할당/인증 실패 뒤 호출 중단과 캐시 완비 문서 반영 확인.
- DB 원자성 시험 추가: 새 청크 쓰기 뒤 장애 시 모든 상태·청크·결과 원복, 트랜잭션 중 다른 연결은 이전 묶음 전체 관측.

- Phase 4 보강: 장부 today/reserve/settle 오류·예약 예산 거절 뒤 새 호출 중단과 캐시 반영, 반영 직전/직후/마감 직전 실제 임시 DB 연결 종료 후 재실행 확인. US1·US2 Checkpoint 51 passed(1.15초).

### Phase 5 — US3

- T028 RED: `uv run pytest tests/unit/sync/test_takedown_decide.py -q --tb=short` 미구현 함수 수집 오류 1건.
  T029 RED: `QK_REQUIRE_LOCALDB=1 uv run pytest tests/localdb/sync/test_takedown.py -q --tb=short` 6 failed.
- T030~T032 구현 후 단위 sync 53 passed, US1~US3 단위·로컬 DB Checkpoint 70 passed(1.98초).
- 내림 허용표 49칸·복수 보류 교집합·20% 경계·불완전 목록에서 설정 제외 우선 확인. 일반 내림 청크 유지/검색 제외, 보안 내림 모든 청크 삭제/비율 초과 시 대기,
  빈 문서의 대기 비움과 확인 실행에서 원본에 없는 대기 문서 정리 확인. 복수 버전 복구·버전 불일치·비활성 자료원 사례도 추가.

### Phase 6 일부 구현 / CLI 연결 사전 대조에서 BLOCKED

- Phase 5 보강 뒤 US1~US3 단위·로컬 DB 73 passed(2.41초).
- T033/T034 RED: `uv run pytest tests/unit/sync/test_preview_budget.py tests/unit/sync/test_run_record.py -q --tb=short` 미구현 preview/report 모듈 수집 오류 2건.
  preview/report·실행 전체 예산 판정을 추가한 뒤 단위 sync 58 passed, 로컬 DB sync 20 passed. 새 시험의 보안 규칙 기대값은 fixture 별칭 github-classic 대신 기존 규칙 이름 github-token으로 바로잡았다.
  미리 보기 쓰기/제공자 호출 0, 실제 실행 대상 수, 보안 내림·확인 시각 유지, 단계별 요약과 원문/오류 메시지 비노출을 확인했다.
- Phase 6는 미완료다. 두 자료원 합계 예산·부분 실행·가려진 식별자 재식별·캐시 요약의 계획된 추가 사례 등이 남아 있어 T033~T037은 체크하지 않았다.
- 완료 표시 재점검: T011은 기존 행이 있는 상태에서 0004 적용·정확한 값 제약 사례 보강이 남고, T028은 경로 제외/대상 아님/조회·판정 실패 사례,
  T029는 수집 중단과 전체 비공개 전환·예산 보류 조합 등의 명시된 모든 사례가 아직 갖춰지지 않아 체크를 해제했다. 기존 GREEN 결과는 사실대로 유지한다.
- 새 BLOCKED(사용자 중단 규칙/T049): T046/CLI 계약은 qk-index run을 실제 동기화로 바꾸지만 T041/Scope는 기존 tests/unit/indexer/test_cli.py를 수정 없이 통과시키도록 요구한다.
  해당 파일 test_run_validates_sources_and_reports_each_source(70행)와 test_run_stops_on_bad_exceptions_without_requests(165행)는 **활성 fake 자료원**을 기본 main으로 실행해
  예전 점검 전용 동작의 종료 코드 0을 기대한다. 전송/임베딩/저장소 주입이 없고, 후자는 ReplayTransport.send를 실패 함수로 바꾼다.
  두 시험의 sources fixture에 enabled=true인 fake 자료원이 있음을 확인했다. 비활성 자료원만 쓰는 test_run_with_valid_settings_reports_and_exits_zero(20행)도 DB를 주입하지 않는다.
  기본 동작에서 fake만 동기화를 생략하는 방식은 FR-001을 어기므로 넣지 않았다. 실제 외부 호출로 재현하지 않았고 CLI 파일·기존 CLI 시험은 수정하지 않았다.
- 필요한 승인(권장): Scope에 tests/unit/indexer/test_cli.py의 위 세 정상 run 사례를 좁게 추가하고, 새 main 주입 인자로 가짜 전송/임베딩/저장소를 넘기도록 시험 조립만 보완한다.
  기존 점검 실패·출력·종료 코드 검증은 유지하고 실제 동기화 호출/원본 쓰기 0 검증을 더한다. T041의 "기존 시험 그대로" 문구도 이 예외를 승인받아야 한다.
  대안은 run의 새 동작/호환 계약을 별도로 승인하는 것이다. 승인 전 Phase 7·8 구현은 진행하지 않는다.
- 현재 library run_sync에는 Phase 7의 실행 전 자료원 정체성·잠금·첫 버전 활성화 게이트가 아직 없다. 실제 실행·CLI 연결에 쓸 수 있는 완성 상태가 아니다.
- T006 공통 SourceScope 입력 점검에서 추가 회귀 시험 RED 1 failed/4 passed(AttributeError) → scope.extra로 읽도록 수정 후 GREEN 5 passed.
- 중단 시 T050 기본 검증(완료 체크는 아님): preflight 530개 파일 PASS; git diff --check PASS; ruff check PASS; ruff format --check 363개 PASS.
  COMPOSE_DISABLE_ENV_FILE=1 및 --env-file /dev/null로 qk-dev db up PASS. 임시 qk_test DB에서 qk-migrate 첫 applied=4 skipped=0, 두 번째 applied=0 skipped=4 PASS 후 DB 삭제.
  QK_REQUIRE_LOCALDB=1 전체 pytest 첫 실행 1197 passed/2 deselected(11.46초); T006 회귀 보강 뒤 최종 재실행 결과는 아래에 덧붙인다.
- index_version iv-4c0bc4fcc642, embedding_model @cf/baai/bge-m3, chunking_version chk-md-20d966f730bb, eval_set_version 해당 없음.
  T048 성능 시험 미실행으로 metrics_with_sample_size 없음. 실제 외부 사용량 0 Neurons. 사람 단계·스테이징·커밋·push·브랜치 변경 없음; 독립 리뷰 미실행.

- 최종 기본 검증: preflight PASS(530개), diff --check PASS, ruff check PASS, ruff format --check PASS(363개), 전체 pytest **1198 passed, 2 deselected, 11.79초**.
  2 deselected는 기존 기본 external 제외다. 새 skip/xfail/경고 suppress/린트 규칙 비활성화 없음.
- T024는 통합 시험의 작성 순서 이탈을 사람 검토 전에 완료로 표현하지 않기 위해 체크를 해제했다. 구현 전 RED를 본 단위 시험과 구현 뒤 추가한 통합 시험을 구분한다.
- 브랜치·HEAD 최종 동일. 이 실행이 승인된 설계/정책을 바꾸지는 않았다. 사람이 보완한 TASK.md/data-model.md/research.md 변경은 그대로 보존했다.

변경 파일(앞 실행의 구현 포함; 위 사람 보완 3개 파일은 제외):
- `specs/QK-SYN-001-incremental-sync/tasks.md`
- `src/qello_knowledge/adapters/fake.py`
- `src/qello_knowledge/adapters/github.py`
- `src/qello_knowledge/adapters/postgres/migrations/0004_sync.sql`
- `src/qello_knowledge/adapters/postgres/store.py`
- `src/qello_knowledge/adapters/postgres/sync_store.py`
- `src/qello_knowledge/domain/security.py`
- `src/qello_knowledge/domain/source.py`
- `src/qello_knowledge/domain/sync.py`
- `src/qello_knowledge/ports/sync.py`
- `src/qello_knowledge/security/screen.py`
- `src/qello_knowledge/sources/collect.py`
- `src/qello_knowledge/sync/__init__.py`
- `src/qello_knowledge/sync/decide.py`
- `src/qello_knowledge/sync/execute.py`
- `src/qello_knowledge/sync/keys.py`
- `src/qello_knowledge/sync/plan.py`
- `src/qello_knowledge/sync/preview.py`
- `src/qello_knowledge/sync/report.py`
- `src/qello_knowledge/sync/run.py`
- `tests/contract/source_adapter_contract.py`
- `tests/contract/test_github_adapter_contract.py`
- `tests/fixtures/sync/.gitkeep`
- `tests/localdb/sync/__init__.py`
- `tests/localdb/sync/conftest.py`
- `tests/localdb/sync/test_atomic.py`
- `tests/localdb/sync/test_incremental_db.py`
- `tests/localdb/sync/test_migration.py`
- `tests/localdb/sync/test_sync_store.py`
- `tests/localdb/sync/test_takedown.py`
- `tests/unit/security/test_screen_listing.py`
- `tests/unit/sources/test_list_all.py`
- `tests/unit/sync/__init__.py`
- `tests/unit/sync/fake_store.py`
- `tests/unit/sync/helpers.py`
- `tests/unit/sync/test_domain.py`
- `tests/unit/sync/test_failures.py`
- `tests/unit/sync/test_incremental.py`
- `tests/unit/sync/test_keys.py`
- `tests/unit/sync/test_preview_budget.py`
- `tests/unit/sync/test_run_record.py`
- `tests/unit/sync/test_takedown_decide.py`
- `tests/unit/test_boundaries.py`

### 2026-10-21 재개 — 사용자 승인 두 건 반영

- 시작 git status에서 기존 구현·사람 문서 변경을 확인하고 보존했다. T041의 기존 정상 run 시험 3개 예외를 사용자 결정대로 작업 설명에 더했다.
- T024 mutation: PostgresSyncStore.mark_seen이 변경 없음 문서의 청크를 DELETE하게 임시 결함 주입. 격리 DB `uv run pytest tests/localdb/sync/test_incremental_db.py -q --tb=short` → RED 1 failed(무변경 재실행의 청크 식별자 snapshot AssertionError).
  finally에서 원본 bytes를 복구하고 SHA-256 일치 확인. 같은 시험 → GREEN 1 passed. 임시 DELETE는 원복되어 diff에 남지 않는다. T024 완료 체크.

### Phase 6 완료 — US4

- 예산 초과 미리 보기의 PROCESS/HOLD 표시 불일치 RED 1 failed → 실제 실행과 같은 constrain/허용표를 적용해 GREEN.
- 가려진 새 문서의 doc_key 결과 누락 RED 1 failed → 보안 차단된 새 문서도 SKIP으로 기록해 GREEN. 두 자료원 합계 예산·부분 실행·캐시 직접 반영 요약·재식별 사례 보강.
- US1~US4 Checkpoint: `QK_REQUIRE_LOCALDB=1 uv run pytest tests/unit/sync tests/localdb/sync -q --tb=short` 83 passed(2.55초).

### Phase 7 완료 — US5

- T038 RED identity 모듈 수집 오류 1건, T039/T040 RED activate 모듈 수집 오류 1건. T041/T042 RED CLI/워크플로 9 failed/1 passed.
- 정체성 점검(잠금 전·뒤), 수집 뒤 원본 비교, 첫 문서 쓰기 직전 기준값 등록, FULL/TAKEDOWN_ONLY 및 --source 선택 구현.
- 종류별 배타 + 전역 공유 세션 잠금, 일부 획득 실패 시 해제, 끊긴 실행은 해당 종류만 unfinished로 닫음. running 기록의 source_kind는 summary에 보존해 첫 문서 전 끊김도 식별.
- 활성화는 전역 배타 잠금·한 트랜잭션에서 조건 확인과 변경. 실행 조회·정리·보관 기간·cascade·running 보존·재실행 0 확인.
- CLI 성공 경로 3개만 승인된 주입/출력 변경. 실패 경로와 다른 명령 시험 본문은 그대로다. 성공용 가짜 전송은 독립 재생 전송이며 실패 경로의 요청 차단을 해제하지 않았다.
- CLI 미리 보기 요약 필드 누락 RED 1 failed → 공통 source_summary로 GREEN. 빈/불완전 목록 정체성 기록 누락 RED 2 failed → 가린 origin 기록으로 GREEN.
- 일반 내림·mark_seen 저장 오류 격리 RED 2 failed → 실패 문서만 FAILED 처리하고 다른 문서는 계속. runs prune의 점검 누락 RED 1 failed → 쓰기 전 설정/자료원/보안·정체성 게이트로 GREEN.
- CLI 시험 46 passed, 실제 두 실행 겹침(같은 이름·다른 이름)·준비 버전 변경·잠금/활성화 DB 시험 14 passed.
- 고정 CLI 입력: tests/fixtures/sync/sources.toml, reviews/docs.toml, responses.json. 전부 합성 값이고 원본·Workers AI 호출 없음.
- 앞 단계 미완료 시험(T011 기존 행 보존/제약, T028 분류, T029 수집 중단/비공개/예산/복수 작업)을 추가해 GREEN. T011·T028·T029 완료 체크.
- Phase 7 Checkpoint는 아래 T050 전체 단위·계약·로컬 DB 실행으로 함께 충족한다.

### Phase 8 — 성능·안내·기본 검증

- T048 `QK_REQUIRE_LOCALDB=1 uv run pytest tests/localdb/sync/test_perf.py -q -s --tb=short`: 1 passed(24.30초).
  합성 79개, 시드 20261021, 입력 1,447,811 bytes, 첫/무변경 각 3회, 중앙값 첫 7.730790초·무변경 0.226075초(기준 60초·30초 이하).
  측정 장비 Mac17,4 / Apple M5 / Darwin 25.6.0 arm64 / 프로젝트 Python 3.13.16. 가짜 원본·가짜 제공자·메모리 사용량 장부·격리 로컬 DB, 실제 외부 대기와 Neurons 0.
  모델 @cf/baai/bge-m3, 청킹 chk-md-20d966f730bb, 인덱스 iv-4c0bc4fcc642, meta-v1, 평가 세트 해당 없음.
- T049 quickstart의 명령·옵션·시험 파일 경로와 4절의 시험 묶음 참조를 구현/계약과 대조했다. 변경할 불일치가 없어 승인된 quickstart·계약·plan은 수정하지 않았다.
- T050 첫 전체 실행 1250 passed/2 deselected(37.98초). 추가한 두 시험의 import 정렬만 ruff로 바로잡았다.
  CLI 고정 입력 파일 연결 뒤 최종 전체 시험을 다시 실행 중이며 최종 결과는 아래에 기록한다.
- 기본 검증: qk-dev db up --env-file /dev/null PASS; 임시 qk_test DB에서 qk-migrate 첫 applied=4 skipped=0, 두 번째 applied=0 skipped=4 PASS 후 삭제.
  COMPOSE_DISABLE_ENV_FILE=1, UV_CACHE_DIR=/private/tmp/qk-syn-uv, UV_OFFLINE=1, QK_REQUIRE_LOCALDB=1을 유지했다. 주소·토큰·본문을 출력하지 않았다.
- scripts/roadmap_status.py는 gh issue list로 실제 GitHub를 호출하므로 이번 외부 호출 금지 범위에서 실행하지 않았다. H01~H07도 요청대로 실행하지 않았다.
  외부 확인과 Jira 완료 판정·커밋·독립 리뷰는 별도 사람/Claude 세션 단계다. 이 실행은 자체 승인이나 병합 판정을 하지 않는다.

### 최종 결과 — T001~T050

- 저장 API 교차 사용 회귀 보강: SyncStore 반영 뒤 기존 Store.replace_chunks가 같은 묶음을 불필요하게 다시 바꾸는 결함을 RED 1 failed로 확인.
  sync apply_document가 같은 트랜잭션에서 chunk_set_hash도 유지하도록 수정했다. 동기화의 변경 판정에는 이 해시를 쓰지 않으며 반영은 여전히 실제 교체다.
  기존 Store 구현은 바꾸지 않았다. 새 회귀와 기존 교체 시험 GREEN 10 passed.
- 최종 전체 `COMPOSE_DISABLE_ENV_FILE=1 QK_REQUIRE_LOCALDB=1 UV_CACHE_DIR=/private/tmp/qk-syn-uv UV_OFFLINE=1 uv run pytest -q --tb=short`: **1251 passed, 2 deselected, 37.77초**.
  Phase 7 전체 Checkpoint 및 T050을 충족했다. 2개 제외는 기존 external 기본 설정이며 새 skip/xfail/경고 suppress 없음.
- `python scripts/preflight.py`: PASS, 543개 파일. `git diff --check`: PASS. `uv run ruff check .`: PASS. `uv run ruff format --check .`: PASS, 372개 파일.
  qk-dev db up 및 qk-migrate 두 번의 PASS는 위 기록과 같다(실제 .env 미사용, 임시 DB 삭제 완료).
- index_version=iv-4c0bc4fcc642, embedding_model=@cf/baai/bge-m3, chunking_version=chk-md-20d966f730bb, metadata_schema_version=meta-v1,
  eval_set_version=해당 없음, estimated_or_used_neurons=0. 최종 코드 성능 측정은 아래에 기록한다.
- status=PASS는 요청된 T001~T050 구현·로컬 시험 범위의 결과다. 독립 리뷰·병합 승인이나 Jira 완료 판정이 아니다. required_human_decisions=구현 범위 추가 결정 없음.
  Claude 독립 리뷰/커밋과 실제 서비스 H01~H07, 외부 조회가 필요한 로드맵 상태 동기화는 이 실행에서 하지 않았다.

최종 변경 파일(사용자가 보완한 위 3개 문서는 보존, 아래 목록에서는 제외):

- `.github/workflows/index-sync.yml`
- `specs/QK-SYN-001-incremental-sync/tasks.md`
- `src/qello_knowledge/adapters/fake.py`
- `src/qello_knowledge/adapters/github.py`
- `src/qello_knowledge/adapters/postgres/migrations/0004_sync.sql`
- `src/qello_knowledge/adapters/postgres/store.py`
- `src/qello_knowledge/adapters/postgres/sync_store.py`
- `src/qello_knowledge/domain/security.py`
- `src/qello_knowledge/domain/source.py`
- `src/qello_knowledge/domain/sync.py`
- `src/qello_knowledge/indexer/cli.py`
- `src/qello_knowledge/indexer/sync_cli.py`
- `src/qello_knowledge/ports/sync.py`
- `src/qello_knowledge/security/screen.py`
- `src/qello_knowledge/sources/collect.py`
- `src/qello_knowledge/sync/__init__.py`
- `src/qello_knowledge/sync/activate.py`
- `src/qello_knowledge/sync/decide.py`
- `src/qello_knowledge/sync/execute.py`
- `src/qello_knowledge/sync/identity.py`
- `src/qello_knowledge/sync/keys.py`
- `src/qello_knowledge/sync/plan.py`
- `src/qello_knowledge/sync/preview.py`
- `src/qello_knowledge/sync/report.py`
- `src/qello_knowledge/sync/run.py`
- `tests/contract/source_adapter_contract.py`
- `tests/contract/test_github_adapter_contract.py`
- `tests/fixtures/sync/.gitkeep`
- `tests/fixtures/sync/responses.json`
- `tests/fixtures/sync/reviews/docs.toml`
- `tests/fixtures/sync/sources.toml`
- `tests/localdb/sync/__init__.py`
- `tests/localdb/sync/conftest.py`
- `tests/localdb/sync/test_atomic.py`
- `tests/localdb/sync/test_concurrency.py`
- `tests/localdb/sync/test_incremental_db.py`
- `tests/localdb/sync/test_index_version.py`
- `tests/localdb/sync/test_migration.py`
- `tests/localdb/sync/test_perf.py`
- `tests/localdb/sync/test_sync_store.py`
- `tests/localdb/sync/test_takedown.py`
- `tests/unit/indexer/test_cli.py`
- `tests/unit/indexer/test_run_cli.py`
- `tests/unit/indexer/test_schedule_workflow.py`
- `tests/unit/security/test_screen_listing.py`
- `tests/unit/sources/test_list_all.py`
- `tests/unit/sync/__init__.py`
- `tests/unit/sync/fake_store.py`
- `tests/unit/sync/helpers.py`
- `tests/unit/sync/test_domain.py`
- `tests/unit/sync/test_failures.py`
- `tests/unit/sync/test_identity.py`
- `tests/unit/sync/test_incremental.py`
- `tests/unit/sync/test_keys.py`
- `tests/unit/sync/test_preview_budget.py`
- `tests/unit/sync/test_run_record.py`
- `tests/unit/sync/test_takedown_decide.py`
- `tests/unit/test_boundaries.py`

- 최종 코드 T048 재측정: `QK_REQUIRE_LOCALDB=1 uv run pytest tests/localdb/sync/test_perf.py -q -s --tb=short` → 1 passed(22.10초).
  metrics_with_sample_size: 합성 문서 n=79, 첫/무변경 각각 3회 중앙값 **7.833703초 / 0.224503초**, 외부 대기 0, 가짜 임베딩, 실제 소비 0 Neurons.
  장비/버전/입력 조건은 위 T048 기록과 같다. 마지막 저장 해시 유지 수정도 이 측정에 포함된다.
- 최종 jira_issue=SCRUM-102, spec_id=QK-SYN-001. failed_checks=없음, blocked_checks=없음(T001~T050 범위).
  assumptions=승인된 location 추가는 인덱스 버전 변경 아님; 외부 실행/H01~H07은 제외 범위.
  risks=실제 GitHub/Workers AI/운영 DB 미검증·독립 리뷰 대기. 브랜치와 HEAD는 시작값 그대로이며 스테이징·커밋·push 없음.

### 독립 리뷰 반영 — 2026-10-21

- 범위: Claude 독립 리뷰의 변경 요청 4건과 TASK.md 끝의 사용자 결정만 반영했다. 승인 설계 문서는 수정하지 않았다.
  아래 uv 명령은 모두 `UV_CACHE_DIR=/private/tmp/qk-syn-uv UV_OFFLINE=1`로 실행했고, 로컬 DB 시험은 추가로
  `COMPOSE_DISABLE_ENV_FILE=1 QK_REQUIRE_LOCALDB=1`을 사용했다. 실제 .env·외부 API·공유 DB는 사용하지 않았다.
- 1. 반복 보안 내림: `uv run pytest tests/unit/sync/test_takedown_decide.py -q --tb=short` RED **4 failed, 19 passed**,
  `uv run pytest tests/localdb/sync/test_takedown.py -k confirmed_security -q --tb=short` RED **4 failed, 13 deselected**.
  비밀값·설정 제외·보안 경로·접근 보류 모두 확인 실행 뒤 다음 실행이 stopped로 돌아가는 것을 재현했다.
  처음 추가한 접근 범위 시험의 합성 입력 private은 fake 판정상 UNKNOWN이므로 계약값 restricted로 바로잡은 뒤 RED를 다시 확인했다.
  같은 보안 사유·같은 접근 범위·deleted·대기 없음일 때만 재내림을 생략하고 purge 비율·결과 행에서 제외했다.
  사유 변경·접근 범위 변경·삭제 대기·복원 처리는 유지한다. GREEN: 위 단위 시험 **23 passed**,
  `uv run pytest tests/localdb/sync/test_takedown.py -q --tb=short` **17 passed**.
  5개 문서 중 2개 보안 내림을 확인한 뒤 2회 반복 성공, purge=0, 추가 결과는 무변경 3개뿐임을 메모리·DB에서 검증했다.
- 2. 첫 버전 활성화: `uv run pytest tests/localdb/sync/test_index_version.py -q --tb=short` RED **1 failed, 8 passed**.
  과거 unfinished 때문에 최신 succeeded를 거부함을 재현했다. 현재 running만 전역 차단하고 대상 버전의 최신 상태 검사는 유지했다.
  같은 명령 GREEN **9 passed**(과거 unfinished 허용, 다른 버전 running 거부, 최신 unfinished 포함 실패 상태 거부).
- 3. 정체성 기준 등록 오류: `uv run pytest tests/unit/sync/test_identity.py -q --tb=short` RED **1 failed, 8 passed**.
  register_origin의 StoreError가 빠져나오는 것을 재현했다. 연결 사용 불가(StoreUnavailable)의 기존 중단 계약은 유지하고,
  등록 제약 오류는 ORIGIN_MISMATCH로 계획을 제한한 뒤 자료원·실행 기록을 stopped로 닫는다.
  data-model 2.4대로 처리·일반 내림·mark_seen·purge는 막고 보안 숨김·본문 삭제만 허용한다.
  같은 명령 GREEN **9 passed**. 이전 문서 보존, 임베딩 0, 보안 본문 삭제, 오류 원문 미기록도 확인했다.
- 4. 자료원별 CLI 보고: 기존 승인된 성공 경로 사례에 활성 docs의 성공·FULL·PROCESS=5와 old-docs 비활성 검증을 더했다.
  실패 경로·사례 수·점검 통과 검증은 유지했다.
  `uv run pytest tests/unit/indexer/test_cli.py::test_run_validates_sources_and_reports_each_source -q --tb=short`
  RED **1 failed**(자료원별 줄 없음). 사람 출력에 안전한 자료원 이름·상태·모드·작업 수와 비활성 항목을 추가했다.
  `uv run pytest tests/unit/indexer/test_cli.py tests/unit/indexer/test_run_cli.py -q --tb=short` GREEN **36 passed**.
- 중간 lint에서 새 생성식의 줄 길이 1건이 발견돼 해당 파일만 formatter로 정리했다. 기본 검증의 최종 결과는 아래에 덧붙인다.

독립 리뷰 반영 후 최종 보고:

- status=PASS(4건 수정·로컬 검증 범위, 독립 재리뷰·병합 승인 아님), jira_issue=SCRUM-102, spec_id=QK-SYN-001.
- changed_files(이번 리뷰 반영 11개, 기존 작업 트리와 사람 문서 보완은 보존):
  `src/qello_knowledge/sync/plan.py`, `src/qello_knowledge/sync/run.py`, `src/qello_knowledge/sync/report.py`,
  `src/qello_knowledge/adapters/postgres/sync_store.py`, `src/qello_knowledge/indexer/sync_cli.py`,
  `tests/unit/sync/test_takedown_decide.py`, `tests/unit/sync/test_identity.py`, `tests/unit/indexer/test_cli.py`,
  `tests/localdb/sync/test_takedown.py`, `tests/localdb/sync/test_index_version.py`, `specs/QK-SYN-001-incremental-sync/tasks.md`.
- executed_checks/passed_checks — T050을 모두 다시 실행했다:
  - `python scripts/preflight.py` → PASS, 543개 텍스트 파일.
  - `git diff --check` → PASS.
  - `UV_CACHE_DIR=/private/tmp/qk-syn-uv UV_OFFLINE=1 uv run ruff check .` → PASS.
  - 같은 환경 `uv run ruff format --check .` → PASS, 372개 파일.
  - `COMPOSE_DISABLE_ENV_FILE=1 UV_CACHE_DIR=/private/tmp/qk-syn-uv UV_OFFLINE=1 uv run qk-dev db up --env-file /dev/null` → PASS.
  - 무작위 qk_test DB에만 DATABASE_URL을 프로세스 환경으로 전달하고 같은 환경에서 `uv run qk-migrate --env-file /dev/null` 두 번
    → PASS, 첫 applied=4 skipped=0, 두 번째 applied=0 skipped=4. 접속 값 미출력, 임시 DB 삭제 완료.
  - `COMPOSE_DISABLE_ENV_FILE=1 QK_REQUIRE_LOCALDB=1 UV_CACHE_DIR=/private/tmp/qk-syn-uv UV_OFFLINE=1 uv run pytest -q --tb=short`
    → **1263 passed, 2 deselected, 38.79초**. 기존 external 기본 제외 2개이며 새 skip/xfail/경고 suppress 없음.
- metrics_with_sample_size: 같은 환경에서 `uv run pytest tests/localdb/sync/test_perf.py -q -s --tb=short` → **1 passed, 23.88초**.
  시드 고정 합성 문서 n=79, 첫 동기화·무변경 각각 3회 중앙값 **7.427746초 / 0.225042초**.
  앞 T048의 같은 입력·장비·가짜 임베딩·로컬 DB 조건이며 무변경 임베딩 호출 0이다.
- index_version=iv-4c0bc4fcc642(현재 설정으로 다시 계산한 첫 값), embedding_model=@cf/baai/bge-m3,
  chunking_version=chk-md-20d966f730bb, eval_set_version=해당 없음, estimated_or_used_neurons=0.
- failed_checks=없음(수정 전 의도한 RED와 중간 lint는 위 기록대로 해소), blocked_checks=없음(요청한 리뷰 반영·T050 범위).
- assumptions=사용자가 보완한 R-09 및 기존 Scope·Decisions를 적용; location 추가는 인덱스 버전 변경 아님.
- risks=이번 수정의 독립 재리뷰 대기; 실제 자료원·모델·운영 저장소 검증은 제외 범위. 같은 세션의 자체 승인 없음.
- required_human_decisions=추가 정책 결정 없음. 독립 재리뷰·커밋은 Claude 세션이 담당한다.
  H01~H07·외부 GitHub 조회가 필요한 로드맵 동기화는 실행하지 않았다. 브랜치·HEAD는 시작값 그대로이며 스테이징·커밋·push 없음.

### H01 결과 (2026-10-21, Claude 세션, 사용자 지시)

- 사전 작업: 로컬 DB(`target=local`)에 미적용이던 마이그레이션 0003·0004를 `uv run qk-migrate`로 적용(`applied=2 skipped=2`, 재실행 `applied=0 skipped=4`). 더하기만 하는 마이그레이션이다.
- 명령: `uv run qk-index run --preview --json`(실제 `.env` 사용은 명령이 읽음, 값은 출력·기록하지 않음). 시작 2026-10-21T09:01:31Z, 종료 코드 0, 소요 약 218초.
- 측정 조건: 자료원 `dnd-backend-docs`, 원본 정체성 `origin_id=1310010471`·`dnd-side-project/dnd-15th-2-backend`, 확정 커밋 `6aeccd039b825dcd7a2b6c046a34ef72089a1f78`, 보안 규칙 `sec-7222e5dd1d6e`,
  청킹 규칙 `chk-md-20d966f730bb`, 인덱스 버전 `iv-4c0bc4fcc642`(활성 버전 없음, 준비 버전 없음), 로컬 개발 환경(macOS arm64).
- 결과: 원본 요청 84회(목록 완전, 실패 0, 중단 없음), 보안 필터 통과 79·비밀값 차단 1(`env-assigned-secret`, 측정 기록 2.1절의 알려진 문서), 처리 예정 79·건너뜀 1, 내림 0,
  청크 1,291개(예상 토큰 최소 16·중앙값 224·최대 2,776, 나뉜 블록 2), 임베딩 미리 보기 1,291개·캐시 적중 0·한도 초과 예상 0·**예상 368.93 Neurons**(입력 1,199,214바이트, 3.5바이트/토큰, 1,075 Neurons/백만 토큰),
  오늘 색인 예산 5,000 중 남은 5,000, 실행 가능.
- 쓰기 없음 확인: `qk-index runs list` 빈 목록, `index status` 활성·준비 버전 없음, `qk-index usage` 사용량 0.
- 관찰: 요청 수가 2026-10-20 측정(83회, 73초)보다 1회 많고 소요가 길다. 실행당 한도(2,000회, 1,800초) 안이다. 재시도 여부는 요약에 없어 확인하지 못했다.
- 외부 임베딩 호출 0, 0 Neurons.

### H02 결과 (2026-10-21, Claude 세션, 사용자 승인) — spec SC-012 측정

- 명령: `uv run qk-index run --json` 두 번(로컬 DB, `target=local`). 측정 조건은 H01과 같다(커밋 `6aeccd0`, `sec-7222e5dd1d6e`, `chk-md-20d966f730bb`, `iv-4c0bc4fcc642`, 로컬 개발 환경 macOS arm64, 2026-10-21).
- 1회차 `sync-20261021T091615-e8441b58`: `succeeded`, 종료 코드 0, 소요 222초(수집 73초). 원본 요청 83회, 처리 79(`PROCESS`)·건너뜀 1(비밀값 차단), 실패 0, 청크 1,291개,
  임베딩 요청 1,291·캐시 적중 0·제공자 호출 95회·**소비 894.50 Neurons(제공자 측정값, 추정 비율 0%)**. 준비 버전 `iv-4c0bc4fcc642` 생성, 활성 버전 없음.
- 2회차 `sync-20261021T091956-37508b00`: `succeeded`, 종료 코드 0, 소요 73초. 원본 요청 83회, 변경 없음 79·건너뜀 1, 청킹 0, **제공자 호출 0·0 Neurons**(로드맵 1.G 조건).
- SC-012 수치 목표: 첫 실행 소비 894.50 Neurons ≤ 색인 예산 5,000 — 충족. 오늘 색인 사용 894.50, 남은 4,105.50.
- 관찰(QK-EMB-001 범위): 미리 보기 예상 368.93 Neurons 대비 실제 894.50(약 2.42배, +142%)로 QK-EMB-001 SC-005 목표(±20%)를 벗어났다. 예상식(UTF-8 바이트 ÷ 3.5, 1,075 Neurons/백만 토큰)이
  영어·코드·표가 섞인 실제 문서의 토큰 수를 작게 잡는 것으로 보인다(QK-CHK-002 research R-03: 표에서 실제 토큰이 예상의 최대 2.30배) `(추론)`. 예산 판정은 정산된 실제 값으로 누적하므로
  초과를 막는 장치는 동작하지만, 실행 전 미리 보기와 예산 사전 판정은 실제보다 낙관적이다. 보정은 이 작업 범위 밖이며 사람 결정이 필요하다.
- H01의 요청 84회·218초와 달리 이번 두 회차는 83회·73초로 2026-10-20 측정과 같았다. H01의 차이는 일시적 재시도로 보인다 `(추론)`.

### H03 결과 (2026-10-21, Claude 세션, 사용자 지시)

- `uv run qk-index index activate iv-4c0bc4fcc642 --json` → 종료 코드 0, 활성화 전 요약: 검색될 문서 79, 청크 1,291, 벡터 없는 청크 0, 마지막 실행 `succeeded`, 실패 조건 없음.
  이후 `index status`: 활성 `iv-4c0bc4fcc642`, 준비 버전 없음, 현재 설정과 일치. 첫 버전 활성화는 AGENTS.md 3.3 평가 조건의 사용자 승인 예외다(spec FR-021).
- 검색 확인(검색 CLI는 QK-RET-001 범위라 `PostgresStore` 검색 질의를 직접 부른 읽기 전용 스크립트, 본문 미출력):
  키워드 `OpenAPI` → 5건(1위 `docs/api/OPENAPI_WRITING_GUIDE.md`), 키워드 `에러 코드` → 1건(`docs/product/AUTH_DESIGN.md`),
  벡터 "API 응답 형식 규칙은 어떻게 되나요?" → 5건(1~3위 `docs/api-response.md`의 절들, 점수 0.68·0.67·0.67). 모든 결과가 활성 버전 `iv-4c0bc4fcc642`에서 나왔다.
  질의 임베딩 1건, 제공자 호출 1회, 0.01 Neurons.
- 관찰(QK-RET-001 범위): 키워드 `에러 코드`가 `docs/error-codes.md`를 찾지 못했다. 한국어 키워드 분해·검색 텍스트 규칙(ADR-010)은 QK-RET-001에서 다룬다.
