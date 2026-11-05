---
description: "QK-STO-002 구현 작업 목록"
---

# Tasks: QK-STO-002 인덱스 버전 생성·평가 게이트·활성화

**Input**: `specs/QK-STO-002-index-version-gate/`의 plan.md, spec.md, research.md(R-01~R-18), data-model.md, contracts/cli.md, contracts/gate-policy.md, contracts/gate-record.md, quickstart.md

**Tests**: 포함한다. spec SC-001~SC-008, FR-035·FR-036, C-12가 자동 시험을 요구한다. 시험을 먼저 쓰고 실패를 확인한 뒤 구현한다. 모든 자동 시험은 외부 호출 0건이다
(가짜 자료원·가짜 임베딩 제공자 `embedding/fake.py`, 손으로 만든 실행 기록·정책, 가짜 `RepoHistory`, 로컬 DB). SC-008(외부 호출·운영 DB 접근 0)은 기존 `tests/conftest.py`의 네트워크 차단과
운영 접속 정보를 쓰지 않는 시험 구성으로 닫는다. 운영 실행(US6)은 이 브랜치 밖이다(맨 끝 "이 브랜치 밖의 사람 단계").

**Organization**: 사용자 스토리별 단계. Foundational(저장 변경) → US1 재색인(P1) → US2 게이트(P1, US1과 독립) → US3 활성화(P1, US1·US2 필요) → US4 되돌리기(P2) → US5 상태 보기·정리(P2).

**선행 조건**: spec.md(2026-11-02)·plan.md(2026-11-05) 사람 승인, 이 목록의 사람 승인, `TASK.md` Scope를 아래 "TASK.md Scope 갱신안"대로 고치기(AGENTS.md 1절).

**공통 규칙**:
- 질문 문장, 핵심 사실, 라벨 근거 낱말, 검색어, 청크 본문, 비밀값, 접속 정보를 로그·예외 문구·`repr`·출력·게이트 기록·전환 기록에 넣지 않는다(SC-007).
  SC-007 문자열 검사는 T018·T030·T032·T040·T041·T047이 맡는다(합성 본문·합성 질문 문장·합성 접속 문자열이 출력·기록·`details`·`reason`에 0번).
- 바꾸지 않는 것: `retrieval/`, `embedding/`, `evaluation/`(가져다 쓰기만), 기존 마이그레이션 파일 `0001`~`0008`, `domain/retrieval.py`의 `RetrievalSettings` 기본값, `domain/keyword_rules.py`,
  `devtools/eval_index.py`, QK-EVL-001 계약 문서, spec.md. 기존 시험 파일과 기대값은 고치지 않는다(FR-036). 예외는 T002의 `tests/unit/test_boundaries.py`에 검사를 더하는 것뿐이다.
  기존 가짜 저장소(`tests/unit/sync/fake_store.py`)와 시험 도우미(`tests/localdb/store/builders.py`)도 고치지 않고, 새 동작이 필요한 시험은 새 도우미 파일에서 상속해 쓴다.
- 새 시험 파일 이름은 `tests/` 전체에서 겹치지 않게 한다(`__init__.py`가 없는 디렉터리가 있어 같은 이름이면 수집이 실패한다). quickstart.md 1절 표는 T056에서 이 목록의 시험 파일과 같게 고친다.
- 경계: `gate/**`는 표준 라이브러리와 `qello_knowledge.domain`·`ports`·`evaluation`·`gate`만 가져온다(T002). `sync/versions.py`는 기존 `sync/**` 경계 검사(`tests/unit/test_boundaries.py`의 `sync_violations`)를 그대로 따르고
  `gate`·`evaluation`을 가져오지 않는다. 게이트 확인 결과는 `indexer/index_cli.py`가 조건 이름과 값(문자열·정수)으로 바꿔 넘긴다.
- 로컬 DB 시험은 `tests/localdb/sync/` 아래에 두고 그 디렉터리의 `clean_sync_tables`(인덱스 버전 `TRUNCATE … CASCADE`로 전환 기록도 비워진다)를 쓴다.
  활성화 시험은 시험 인덱스 버전 ID가 `INDEX_KEYWORD_RULES`에 없으므로 `monkeypatch`로 대응표를 시험 값으로 바꾼다(`domain/keyword_rules.py` 파일은 고치지 않는다).
- 0008까지만 적용한 DB에 행을 넣는 시험(T004·T006)은 SQL로 직접 넣는다. `builders.py`의 `replace_chunks` 경로는 T010 뒤 새 출처 열을 쓰므로 쓰지 않는다.

**TDD 순서**: 각 단계에서 시험 작업(단위·로컬 DB 통합 모두)을 먼저 쓰고 실패(아직 없는 모듈이면 수집 오류 포함)를 확인한 뒤 구현 작업을 한다. 목록 순서가 곧 작업 순서다.
[P]는 다른 파일을 다루고 앞선 미완료 작업에 기대지 않는다는 뜻이다.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 다른 파일을 다루고 미완료 작업에 기대지 않아 병렬로 할 수 있다
- **[Story]**: 해당 사용자 스토리(US1~US5)

---

## Phase 1: Setup

- [X] T001 자리 만들기: `src/qello_knowledge/gate/__init__.py`(모듈 설명 한 줄), `tests/unit/gate/`, `tests/fixtures/gate/`. 시험 디렉터리에는 `__init__.py`를 만들지 않는다.
- [X] T002 [P] `tests/unit/test_boundaries.py`: 기존 검사는 그대로 두고 `GATE_ALLOWED = (*ALLOWED_INTERNAL, "qello_knowledge.evaluation", "qello_knowledge.gate")`와 `gate_violations(root)`(대상: `gate/**/*.py`)를 더한다.
  금지: `psycopg`, `qello_knowledge.adapters`, `qello_knowledge.devtools`, `qello_knowledge.indexer`, `qello_knowledge.sync`.
- [ ] T003 [P] 공통 파일 변경 알림(보낼 문구를 사람에게 먼저 보여 확인받은 뒤 보냄): 같은 시점에 QK-ING-003을 진행하는 세션에 이 브랜치가 고칠 공통 파일(`sync/plan.py`·`decide.py`·`execute.py`·`preview.py`·`run.py`, `domain/sync.py`, `ports/sync.py`,
  `adapters/postgres/sync_store.py`·`store.py`, `indexer/sync_cli.py`·`cli.py`, 마이그레이션 번호 `0009`)을 메시지로 알리고(TASK.md 제외 범위), 마이그레이션 번호가 겹치는지 답을 받아 "실행 기록"에 남긴다. 그쪽 파일은 고치지 않는다.

---

## Phase 2: Foundational (저장 변경, 모든 스토리의 선행)

**Purpose**: 마이그레이션 0009, 버전별 출처 정보(FR-005), 전환 기록, 배포 순서 보호, 저장 경계. 이 단계가 끝나야 US1·US3~US5를 시작한다(US2는 저장소를 쓰지 않아 이 단계와 병렬 가능).

- [X] T004 [P] `tests/localdb/sync/test_migration_0009.py`(research R-18, data-model 1절): 0008까지 적용한 격리 DB에 자료·청크·활성 버전 하나를 SQL로 넣고 0009를 적용한 뒤
  (1) `qk.chunk.source_url`·`source_modified_at`·`collected_at`이 자료 행 값으로 채워짐, (2) 제약 "`pruned_at IS NULL OR status = 'archived'`" 위반 거부,
  (3) `qk.sync_run.kind` 기본 `'sync'`, `CHECK (kind IN ('sync', 'reindex'))` 위반 거부, (4) `processed_outcome = 'not_target'` 허용·그 밖 새 값 거부,
  (5) `qk.index_transition`에 `first_activation` 한 행(`details.backfilled = true`, `target = 'unknown'`, 시각 = `activated_at`), (6) 제약 위반 거부: `activation`인데 게이트 두 열 중 하나라도 NULL,
  게이트 두 열 가운데 하나만 있음(종류 무관), `rollback`인데 `reason` NULL, `reason` 길이 0·201, `prune`인데 `deleted_chunks` NULL, `target`이 `local`·`remote`·`unknown` 밖, (7) 재적용 시 `applied=0`.
  기존 `tests/localdb/sync/test_migration.py`의 부분 적용 방식을 가져와 쓴다(그 파일은 고치지 않음).
- [X] T005 [P] `tests/localdb/sync/test_chunk_provenance.py`(research R-01, SC-001의 출처 부분): 같은 자료를 버전 V1로 쓴 뒤 자료 행의 `source_url`·`collected_at`·`source_modified_at`이 바뀌게 V2로 다시 쓰면,
  V1 활성 상태에서 `qk.search_keyword`·`qk.search_keyword_terms`·`qk.search_vector`·`qk.chunk_context`·`qk.chunk_neighbors`가 V1 청크를 쓴 때의 값을 내고 `PostgresStore.trace_chunk`도 같은 값을 낸다.
  출처 열이 NULL인 행(옛 코드가 쓴 행 흉내, SQL로 넣음)은 자료 행 값으로 돌아간다(`coalesce`).
- [X] T006 [P] `tests/localdb/sync/test_schema_guard.py`(research R-18): 0008까지만 적용한 DB에서 `PostgresSyncStore.begin_run`·`activate`와 `PostgresIndexVersionStore` 연결이 쓰기 없이 `SchemaOutdated`를 낸다.
  `qk.schema_migration`에 `version >= 9` 성공 행이 있으면 통과한다(버전 10 행만 있는 경우 포함, 행은 SQL로 넣음).
- [X] T007 [P] `tests/localdb/sync/test_first_activation_transition.py`(FR-002, US3-5): `PostgresSyncStore(url, current_version=V1, target="remote").activate(V1)` 성공 뒤 `qk.index_transition`에 `first_activation` 한 행
  (`before_active` NULL, `after_active` V1, 문서·청크 수, `target = 'remote'`), 조건 실패(`active_exists` 등)면 행 0. 기존 `test_index_version.py`는 고치지 않는다.
- [X] T008 [P] `tests/localdb/sync/test_index_version_store.py`(research R-04·R-12·R-17, data-model 2.3): `PostgresIndexVersionStore`의 읽기 결과가 손으로 넣은 행과 같은지.
  덮음 사례(덮음, 남음, 빈 본문, `not_target`, 덮였지만 마지막 재색인 실패, 새 문서는 분모 밖), 불일치 시작 시각, 활성 이력, `activation_state`의 운영 키워드 색인 토크나이저(`TokenBigramSplitSymbol`),
  대상 버전이 든 `purge_pending` 자료 수(0과 2), `qk.sync_source`의 `{ name, kind }` 목록, 실행 중 동기화 여부.
- [X] T009 `src/qello_knowledge/adapters/postgres/migrations/0009_index_versions.sql`(research R-18, data-model 1.1~1.5): 청크 출처 열 3개(NULL 허용)와 채우기, `qk.hit_json` 교체(같은 시그니처,
  `coalesce(c.<열>, a.<열>)`, `IMMUTABLE` 유지), `qk.index_version.pruned_at`과 검사 제약, `qk.sync_run.kind`, `qk.artifact.processed_outcome` 검사 제약을 지우고 `('chunked', 'empty', 'not_target')`로 다시 만듦,
  `qk.index_transition` 표(data-model 1.3 열·제약 그대로, `target CHECK (target IN ('local', 'remote', 'unknown'))`, `reason` 길이 1~200, 게이트 두 열은 둘 다 있거나 둘 다 없음)와 지금 활성 버전의 채움 행.
  질의 역할 권한은 더하지 않는다. T004 통과.
- [X] T010 `src/qello_knowledge/adapters/postgres/store.py`: `_replace_chunk_rows`가 같은 트랜잭션에서 `qk.artifact`의 `source_url`·`source_modified_at`·`collected_at`을 읽어 청크 행에 쓴다.
  `trace_chunk`는 `coalesce(c.source_url, a.source_url)` 등 청크 값을 먼저 쓴다. 다른 함수는 바꾸지 않는다. T005 통과.
- [X] T011 `src/qello_knowledge/domain/store.py`에 `SchemaOutdated(StoreError)`를 더하고, `adapters/postgres/sync_store.py`에 0009 확인(`SELECT 1 FROM qk.schema_migration WHERE version >= 9 AND result = 'success'`)을
  `begin_run`·`activate` 첫 쓰기 전에 한 번(연결당 기억) 부른다. `PostgresSyncStore(url, *, current_version=None, target="local")` 생성 인자 `target`을 더하고, `activate`가 같은 트랜잭션에서
  `first_activation` 전환 행을 쓴다. `activate(version)` 시그니처와 반환값은 그대로다. T006(동기화 저장소 부분)·T007 통과.
- [X] T012 [P] `src/qello_knowledge/ports/index_versions.py`(data-model 2.3): `RunRef`, `VersionRow`, `FailedDoc`, `Coverage`, `ActivationState`(활성 버전, 대상 `VersionRow`, 실행 중 동기화, 덮음,
  대상이 든 `purge_pending` 자료 수, 운영 키워드 색인 토크나이저, 운영 자료원 `{ name, kind }` 목록), `RollbackState`, `PruneState`, `TransitionRow` 불변 dataclass와 `IndexVersionStore` Protocol:
  `versions()`, `coverage(version)`, `mismatch_since(active, current)`, `activation_state(version)`, `rollback_state(version)`, `prune_state(version)`,
  `switch_active(version, *, check, kind, gate_record_id=None, gate_record_sha256=None, reason=None, provenance_mismatch=None, details=None)`(`check`는 잠금·트랜잭션 안에서 다시 읽은 상태를 받아 실패 조건 이름 튜플을 돌려주는 함수),
  `prune_batch(version, limit)`, `finish_prune(version, deleted)`, `transitions(version=None)`, `close()`. 인자 이름 `version`은 인덱스 버전 ID, 실행 위치는 생성 인자 `target`이다. 반환값에 본문·접속 정보 없음.
- [X] T013 [P] `src/qello_knowledge/ports/history.py`(research R-09): `RepoHistory` Protocol(`first_added_commit(ref, path)`, `file_at(ref, path) -> bytes | None`, `list_paths(ref, directory)`, `is_ancestor(ancestor, commit)`, `head() -> (sha, dirty)`).
- [X] T014 `src/qello_knowledge/adapters/postgres/index_versions.py`(새 파일, research R-04·R-08·R-12·R-16·R-17): `PostgresIndexVersionStore(url, *, current_version, target)`. 연결 직후 0009 확인(T011과 같은 질의, 없으면 `SchemaOutdated`).
  읽기는 읽기 전용 트랜잭션. 덮음(R-04 정의 그대로: 노출 문서 = 활성 버전 청크가 있고 `status = 'active'`, `access_scope = 'team'`; 덮음 = 그 가운데 `processed_index_version = 후보`;
  처리 실패 = 노출 문서 가운데 후보 버전 최근 `kind = 'reindex'` 실행의 결과가 `FAILED`), 불일치 시작 시각(R-17), 버전 목록(활성 이력 = 그 버전이 `after_active`인 `first_activation`·`activation`·`rollback` 전환 행 존재).
  `activation_state(version)`는 T012의 항목을 모두 읽는다: 운영 키워드 색인 토크나이저는 `chunk_search_text_pgroonga`의 `reloptions`에서(`adapters/postgres/eval_target.py`의 `_tokenizer`와 같은 해석),
  `purge_pending`에 대상이 든 자료 수, `qk.sync_source`의 `source_name`·`source_kind`, 대상 버전 청크 가운데 `embedding_id IS NULL` 수, 대상 버전 마지막 `kind = 'reindex'` 실행, `status = 'running'` 실행 유무.
  `switch_active`는 `pg_try_advisory_lock(hashtext('qk-sync-index'))`를 잡고(못 잡으면 `("sync_running",)`) 한 트랜잭션에서 상태를 다시 읽어 `check`로 확인한 뒤 이전 활성 `archived` → 대상 `active`(`activated_at = now()`) →
  전환 행 순으로 쓰고 잠금을 푼다(R-08). 정리는 R-16(1,000행 묶음, 마지막 트랜잭션에서 모든 자료 행 `purge_pending`에서 버전 제거와 비면 `purge_reason = NULL`, `archived` + `pruned_at = now()`, 전환 행 `prune`).
  `PostgresSyncStore.index_versions()`가 같은 접속 정보·`current_version`·`target`으로 이 저장소를 연다(research R-15). T006 나머지·T008 통과.

**Checkpoint**: 0009가 로컬 DB에 적용되고 기존 시험이 모두 통과한다(`QK_REQUIRE_LOCALDB=1 uv run pytest`).

---

## Phase 3: User Story 1 - 활성 버전을 그대로 둔 채 새 인덱스 버전을 만든다 (P1) 🎯 MVP

**Goal**: 불일치 상태에서 `qk-index run --reindex`가 후보 버전을 채우고 활성 버전 검색은 바뀌지 않는다.

**Independent Test**: 로컬 DB에 V1을 만들고 청킹 설정을 바꿔 재색인한다. 재색인 전후 V1 검색 결과·출처 정보가 같고, V2에 대상 문서가 모두 처리되고, 가짜 임베딩 호출 수가 미리 보기와 맞는다.

- [X] T015 [US1] `tests/unit/sync/reindex_fakes.py`(시험 도우미, 수집 대상 아님): `MemorySyncStore`를 상속한 `ReindexMemoryStore`(`prepare_candidate(spec, *, target)`, 실행 `kind` 기록, 재사용 전환 기록, `index_versions()`가 돌려줄 가짜 덮음). 기존 `fake_store.py`는 고치지 않는다.
- [X] T016 [P] [US1] `tests/unit/sync/test_reindex_plan.py`(T015 뒤, research R-02·R-03, FR-004·FR-010·FR-029, US1-5·US1-6):
  (1) `SyncOptions(reindex=True, trigger="schedule")`·`(reindex=True, source=…)`는 `ValueError`, (2) 활성 없음 → `no_active_version`, 활성 = 현재 → `not_mismatched`, 둘 다 쓰기 0,
  (3) 재색인 계획에 `INDEX_MISMATCH` 보류 없음, 바뀐 문서 `PROCESS`, 원본에서 사라진 문서 `TAKE_DOWN source_missing`, 끈 자료원(`TAKEDOWN_ONLY`) 문서 `TAKE_DOWN source_disabled`, 비율 안전장치 적용,
  (4) 지금 노출되지 않는 저장 문서(`status ≠ 'active'` 또는 `access_scope ≠ 'team'`: 일반 내림, 보안 내림 + 본문 삭제 대기, 대상 아님으로 내림)가 다시 처리 대상이 되면 `HOLD`이고 `failure = "reindex_hidden"`,
  (5) 노출 문서의 `NOT_MARKDOWN`은 `TAKE_DOWN`이 아니라 `not_target = True`, `actions = (PROCESS,)`, 청크 0개이고 `chunked`(청킹 버전·`screened`)가 채워짐, (6) 재색인이 아닌 실행에서 `processed_outcome = 'not_target'`이고
  `processed_index_version = 현재`면 `ChangeReason.NOT_TARGET_PENDING`으로 다시 청킹해 지금처럼 `TAKE_DOWN not_target`, 불일치 예약 실행이면 보류, (7) 예약 실행은 재색인을 하지 않고 지금처럼 `INDEX_MISMATCH` 보류이며
  요약에 `index_mismatch: { active, current, coverage, resolutions }`가 더해짐(덮음 값은 가짜 저장소 값, `index_versions()`가 없는 저장소면 `coverage: null`).
- [X] T017 [P] [US1] `tests/unit/sync/test_reindex_preview.py`(T015 뒤, research R-05, FR-006, US1-1·US1-3·US1-9): 미리 보기 출력 키(contracts/cli.md 1절 `reindex` 객체 전부), 임베딩 호출·저장소 쓰기 0,
  예상 일수 공식(예상 ≤ 오늘 잔여 → 1, 아니면 `1 + ceil((예상 − 오늘 잔여) / index_budget)`, 예상 0 → 1)의 경계값, 모델만 바뀐 설정에서 캐시 적중 0, 예산 초과면 실행이 `begin_run` 전에 종료 5 `budget_exceeded`(실행 기록 0)이고
  `security_takedowns` 수를 보임, `--allow-partial-budget`이면 부분 실행.
- [X] T018 [P] [US1] `tests/unit/indexer/test_reindex_cli.py`(contracts/cli.md 1절): `--reindex`와 `--trigger schedule`·`--source` 조합 오류(종료 2), `no_active_version`·`not_mismatched`·`schema_outdated` 종료 1,
  `budget_exceeded` 종료 5, 원격 확인 옵션, 출력 키, SC-007(합성 본문·합성 접속 문자열 0번). `main(sync_factory=…)`로 가짜를 주입한다. 기존 `test_run_cli.py`는 고치지 않는다.
- [X] T019 [US1] `tests/localdb/sync/test_reindex.py`(SC-001·SC-006, US1-2~US1-5): 가짜 자료원과 가짜 임베딩으로 V1 첫 색인·첫 활성화 → 청킹 설정 변경 → 재색인.
  (1) 재색인 전후 활성 버전 검색(키워드·벡터·하이브리드, 상위 20건의 순위·자료원·위치·원본 링크·원본 버전·제목 경로·원본 수정 시각·수집 시각)이 내린 문서를 뺀 모든 시험 질의에서 같다
  (원본에서 바뀐 문서 포함, 벡터 근사 결과가 정확 검색과 같아지는 크기: 청크 40개 이하. spec SC-001의 "제목"은 결과에 값이 없어 비교 대상이 없다, research R-01),
  (2) V1 청크 생성·수정·삭제 0, (3) 가짜 임베딩 호출 수 = 미리 보기 `to_embed`, (4) 변경 없는 재색인 두 번째 실행의 임베딩 호출 0, (5) 부분 실행 뒤 재실행에서 처리 끝난 문서 임베딩 0,
  (6) 비밀값 문서는 실행 뒤 V1 포함 모든 검색에서 빠짐, (7) 원본 삭제 문서는 V1 검색에서 빠짐, (8) 내렸던 문서(일반 내림, 보안 내림 뒤 본문 삭제 대기)가 원본에 다시 나타나도 재색인 뒤 V1 검색에 나오지 않음(research R-02),
  (9) 대상 아님 문서는 V1에서 계속 검색되고 덮음에 셈.
- [X] T020 [P] [US1] `tests/localdb/sync/test_reindex_versions.py`(US1-7·US1-8, FR-009, FR-002): 재색인 중 설정이 V3로 바뀌면 다음 재색인이 V3에 처리하고 V2는 `ready`로 남음, 보관(정리 포함) 버전 ID로 돌아가면 `ready`로 재사용되고
  `reuse` 전환 행이 남고(`target`이 실행 위치 값) 활성 이력은 유지.
- [X] T021 [US1] `src/qello_knowledge/domain/sync.py`: `ChangeReason.NOT_TARGET_PENDING`, `DocumentDecision.not_target: bool = False`(참이면 `actions == (PROCESS,)`이고 `chunked`의 청크 0개여야 한다는 검사).
  `HoldReason`·`ALLOWED`는 바꾸지 않는다.
- [X] T022 [US1] `src/qello_knowledge/sync/decide.py`·`sync/plan.py`(research R-02·R-03): `change_reason(…, *, reindex=False)`에서 `not_target` 대기 판정(재색인에서는 처리 완료로 봄),
  `plan_source(…, options)`가 `options.reindex`일 때 숨은 저장 문서의 `PROCESS`를 `HOLD`(`failure="reindex_hidden"`)로, 노출 문서의 `NOT_MARKDOWN`을 `chunked`를 넣은 `not_target` 결정으로 바꾼다
  (`sync/execute.py`가 `chunked.screened`·`document_title`·`chunking_version`을 읽는다). 재색인이 아닌 경로의 결정은 그대로다.
- [X] T023 [US1] `src/qello_knowledge/sync/execute.py`·`sync/preview.py`: `not_target` 결정은 처리 결과 `processed_outcome = 'not_target'`, 결과 `PROCESSED_EMPTY`로 쓰고, 임베딩 요청(`embedding_request`)에서 뺀다.
- [X] T024 [US1] `src/qello_knowledge/ports/sync.py`·`adapters/postgres/sync_store.py`(research R-06·R-07): `RunInfo.kind: str = "sync"`, `SyncStore.prepare_candidate(spec, *, target) -> str`(없으면 `ready` 생성, `ready`면 그대로,
  `archived`면 `ready`·`pruned_at = NULL`과 전환 행 `reuse`(`target` 인자 값)), `begin_run`이 `kind`를 쓴다.
- [X] T025 [US1] `src/qello_knowledge/sync/run.py`(research R-02·R-05): `SyncOptions.reindex`와 검증, 재색인 경로(불일치 확인 → 잠금 → 계획 → 예산 선판정 → `begin_run(kind='reindex')` → `prepare_candidate(spec, target=options.target)` → 실행),
  재색인 요약(`reindex: { candidate, coverage }`), 재색인이 아닌 실행의 불일치 요약 `index_mismatch`(저장소에 `index_versions()`가 없으면 `coverage: null`). 미리 보기 계산 함수 `reindex_preview(…)`를 `sync/preview.py`에 둔다.
  T016·T017 통과.
- [X] T026 [US1] `src/qello_knowledge/indexer/cli.py`·`indexer/sync_cli.py`(contracts/cli.md 1절): `run`에 `--reindex`, `cli.py`의 기존 `parser.error` 자리에서 `--reindex`와 `--trigger schedule`·`--source` 조합 거부,
  재색인 미리 보기·실행 출력, `no_active_version`·`not_mismatched`·`budget_exceeded` 종료 코드, `SchemaOutdated`는 `StoreError`보다 먼저 잡아 종료 1 `schema_outdated`.
  `build_runtime`과 `postgres_sync_store`는 이미 받는 `source`로 `target_label(source)`를 계산해 `PostgresSyncStore(target=…)`로 넘긴다(새 인자 없음. devtools 사용처는 로컬 URL이라 `local`).
  재색인의 `reuse` 행은 T025의 `options.target`을 쓰고, 두 값은 같은 `target_label(source)`에서 온다.
  기존 `run` 출력 키·종료 코드는 그대로다. T018·T019·T020 통과.

**Checkpoint**: US1 단독으로 재색인과 미리 보기가 동작하고 활성 버전 검색이 그대로다.

---

## Phase 4: User Story 2 - 후보 버전을 평가 게이트로 판정한다 (P1)

**Goal**: `qk-dev eval gate`가 정책과 실행 기록만으로 통과·실패·판정 불가를 내고 게이트 기록을 쓴다(DB·외부 호출 0).

**Independent Test**: 손으로 만든 실행 기록·정책 예시와 가짜 `RepoHistory`로 판정해 손으로 계산한 판정·지표·사유와 같다.

- [X] T027 [US2] `tests/fixtures/gate/`: 합성 질문 세트 지문을 가진 손 작성 실행 기록 JSON(`qk-evl-001-run/v1` 계약 그대로, 질문 문장 없음)과 정책 TOML. 사례: 통과, 주 지표 하락,
  후보에서만 근거 미색인·검색 실패·하이브리드 생략, G1·G2·G3 위반 각 하나, 판정 불가 사유마다 하나(contracts/gate-record.md 4절 표 전부), 모델이 다른 두 실행 기록, 같은 세트 기록 둘, 가드레일 판정 질문 0개. `README.md`에 사례별 손 계산 값을 적는다.
- [X] T028 [P] [US2] `tests/unit/gate/test_gate_policy.py`(T027 뒤, contracts/gate-policy.md): 형식 예시 통과, 3절 오류 이름마다 하나, 수치 문자열 → `Fraction`, 음수·지수 표기·빈 문자열 거부, 모르는 키 거부, 파일 이름 버전 ≠ `version` 거부, 지문.
- [X] T029 [P] [US2] `tests/unit/gate/test_judge.py`(T027 뒤, SC-003, research R-10, FR-015~FR-017): T027 사례마다 판정·세트별 지표(기준·후보·차이·판정 질문 수)·뺀 질문과 사유·가드레일(판정 질문 수 포함)·회귀·개선·위반·판정 불가 사유가 손 계산과 같다.
  가드레일 판정 질문 0개 → `too_few_judged`, 후보 비정상 질문은 Precision@5 0·상한 도달로 셈, `code_commit.sha = null` → `code_commit_unknown`, 임베딩 모델이 다른 두 기록 → `query_vectors_differ = true`이고 그 밖 조건이 다르면 `condition_mismatch`.
- [X] T030 [P] [US2] `tests/unit/gate/test_gate_record.py`(T027 뒤, contracts/gate-record.md 1~3절, SC-007, FR-018): 최상위·중첩 객체 키 목록 일치(목록 밖 키 실패), 키 정렬·들여쓰기 2칸, 기록 경로가 있으면 쓰지 않음, 임시 이름 뒤 이름 바꾸기,
  합성 세트의 질문 문장·청크 본문 문자열 0번, 판정 불가에도 기록과 `judged_counts`.
- [X] T031 [P] [US2] `tests/unit/gate/test_repo_history.py`: `adapters/git_history.py`를 `tmp_path`의 임시 git 저장소(첫 부모 병합 커밋 하나 포함)로 시험한다. `first_added_commit`이 그 파일을 들여온 병합 커밋을 해시 한 줄로 내고,
  `is_ancestor`, `file_at`, `list_paths`, `head`의 `dirty`. 네트워크 0.
- [X] T032 [P] [US2] `tests/unit/devtools/test_gate_cli.py`(T027 뒤, contracts/cli.md 6절): 통과 0, 실패 1, 판정 불가 3(셋 모두 기록 씀), 인자·정책 오류·출력 경로 있음 2(기록 없음), `{gate_id}` 자리표시자, `--main-ref` 기록,
  DB·네트워크 접근 0(가짜 `RepoHistory` 주입), SC-007(합성 질문 문장 0번).
- [X] T033 [US2] `src/qello_knowledge/gate/policy.py`(contracts/gate-policy.md): `GatePolicy`, `SetRule`, `Guardrail`, `load_policy(path) -> (GatePolicy | None, issues)`. `search`가 빠지면 `RetrievalSettings()` 기본값으로 채운다. T028 통과.
- [X] T034 [US2] `src/qello_knowledge/gate/judge.py`(research R-10, data-model 3.2): `judge(request: GateRequest) -> GateOutcome`. `evaluation.metrics`의 `OK_STATUSES`·`MRR_CUTOFF`를 가져와 쓰고 `Fraction`으로만 계산한다.
  비교 조건 항목(세트 ID·버전·지문, 자료원별 고정 커밋, 임베딩 모델, 질의 쪽 규칙, 후보 수, RRF 상수, 검색 필터)은 이 모듈 안에서 계산한다(`evaluation/compare.py`의 비공개 함수에 기대지 않음). T029 통과.
- [X] T035 [US2] `src/qello_knowledge/gate/record.py`(contracts/gate-record.md): `GateRecord` JSON 쓰기·읽기·스키마 검사, `new_gate_id(clock, random)`, 파일 SHA-256. T030 통과.
- [X] T036 [US2] `src/qello_knowledge/adapters/git_history.py`(research R-09): `GitHistory(repo_root)`가 `git log --first-parent --diff-merges=first-parent --diff-filter=A --no-patch --format=%H <ref> -- <path>`(가장 오래된 줄),
  `git show <ref>:<path>`, `git ls-tree --name-only <ref> <dir>/`, `git merge-base --is-ancestor`, `git rev-parse HEAD`·`git status --porcelain`을 부른다. 실패는 `None`/`False`와 사유로 돌려준다. T031 통과.
- [X] T037 [US2] `src/qello_knowledge/devtools/gate_cli.py`(새 파일)와 `devtools/db.py`의 `eval` 묶음에 `gate`(contracts/cli.md 6절 옵션 전부) 등록. `history_factory` 주입점을 둔다. T032 통과.

**Checkpoint**: US2 단독으로 게이트 판정과 기록이 동작한다(저장소 없음).

---

## Phase 5: User Story 3 - 게이트를 통과한 버전만 활성화하고 이전 버전은 보관한다 (P1)

**Goal**: `qk-index index activate <버전> --gate <기록>`이 조건을 모두 채울 때만 V2 활성·V1 보관으로 한 번에 바꾼다.

**Independent Test**: V1 활성·V2 준비 상태에서 FR-021 조건마다 그 조건 하나만 어긴 사례가 거부되고 상태·전환 기록이 그대로다. 모두 채우면 한 번에 바뀌고 동시 검색이 섞인 결과를 받지 않는다.

- [X] T038 [P] [US3] `tests/unit/sync/test_version_conditions.py`(data-model 2.4): `sync/versions.py`의 활성화 조건 함수가 스냅샷 값과 게이트 확인 결과(조건 이름·값)에서 조건 이름 (1)~(11)을 모두 내고, 여러 개 어기면 이름을 모두 낸다. 활성 없음 → `no_active_version`.
- [X] T039 [P] [US3] `tests/unit/gate/test_gate_verify.py`(contracts/gate-record.md 5절, research R-11): 통과 기록 확인 성공, 그리고 사례마다 기대 조건 이름이 결과에 포함되는지 단언한다(다시 판정이 함께 실패해 `gate_integrity`가 더 나올 수 있다):
  판정이 통과가 아님(`gate_verdict`), 후보 ≠ 대상(`gate_candidate`), 기준 ≠ 지금 활성(`gate_baseline`), 정책이 `origin/main`과 다름·병합 커밋 없음·더 높은 버전 있음(`gate_policy`),
  실행 기록 파일 지문 다름·정책 파일 지문 다름·판정 필드를 손으로 고침(`gate_integrity`, 이 사례는 결과가 정확히 `{gate_integrity}`). 다시 판정의 기대 인덱스 버전은 활성화가 넘긴 값이다.
- [X] T040 [P] [US3] `tests/unit/indexer/test_index_cli.py`(contracts/cli.md 2·3절): 가짜 버전 저장소·가짜 `RepoHistory`로 `status`·`activate` 옵션·종료 코드(0·1·4·6, `gate_record_required`, `schema_outdated` 종료 1)·원격 확인·출력 키,
  버전 저장소가 없는 대역에서 `status`는 지금 키만, `activate`(활성 없음)는 지금 첫 활성화, 활성 있음 + `--gate` 없음은 종료 1 `gate_record_required`, 활성 있음 + `--gate`는 종료 2 `store_unavailable`. SC-007(합성 본문·합성 접속 문자열 0번).
  기존 `test_run_cli.py`·`test_code_sync_cli.py`는 고치지 않고 그대로 통과해야 한다.
- [X] T041 [US3] `tests/localdb/sync/test_index_activation.py`(SC-002 활성화, US3-1~US3-4): V1 활성·V2 준비·재색인 성공 상태를 만든다. 실행 경로는 `indexer.index_cli`의 활성화 함수에 `PostgresSyncStore`(로컬 DB)와
  `gate_verifier` 대역을 직접 넘기는 방식이다(CLI `main`의 설정·자료원 검토 검사는 T040이 맡는다). 대역으로 게이트 확인 통과·실패를 고른다(공통 준비: 대응표 `monkeypatch`, 현재 설정 버전 = V2).
  조건 (1)~(11)을 하나씩만 어긴 사례마다 거부되고 `qk.index_version`·`qk.index_transition`이 그대로다. (7)은 대응표에서 V2를 뺌, (8)은 게이트 후보 토크나이저를 다른 값으로, (9)는 정책 `search`를 기본값이 아닌 값으로,
  (11)은 다른 연결이 공유 잠금을 쥔 상태. 미리 보기 값(덮음, `failed_documents`, `purge_pending_documents`, `chunks_without_vector`, `retrieval_settings`, `uncovered_sources`)이 DB 값과 같다.
  모두 채우면 V2 `active`·V1 `archived`, 전환 행에 게이트 기록 ID·지문·전후 버전·문서·청크 수·`details`(정책 ID·버전, 세트별 지표·판정 질문 수, 임베딩 모델, 세트 버전), `details`에 합성 본문·접속 문자열 0번(SC-007).
  활성화 직후 예약 동기화가 바뀐 문서를 V2에 처리하고 보류했던 일반 내림을 한다(US3-4).
- [X] T042 [US3] `tests/localdb/sync/test_index_switch_concurrency.py`(SC-004, research R-08): T041과 같은 준비로 V1·V2 모두에 결과가 나오는 질의를 고른다. V2 활성화 1회 뒤, 검색 스레드가 `retrieve`(하이브리드, 가짜 임베딩, 문맥 확장 포함)를
  반복하는 동안 V1·V2 되돌리기를 번갈아 10회 이상 돌린다. 원본이 바뀐 문서가 없는 데이터를 써서 출처 어긋남 0으로 되돌리기가 `provenance_unconfirmed`에 걸리지 않게 한다. 결과마다 검색 결과와 문맥 블록의 모든 `chunk_id`를 DB에서 찾아 `qk.chunk.index_version`이 하나인지 보고(섞임 0건), 상태 `NO_ACTIVE_INDEX` 0건,
  `index_version_changed` 수를 시험 출력(`record_property`)에 남긴다.
- [X] T043 [US3] `src/qello_knowledge/gate/verify.py`(research R-11): `verify_for_activation(record_path, *, active, target, history, repo_root) -> (VerifiedGate | None, failed_conditions)`. 활성화는 언제나 `origin/main`을 쓴다. T039 통과.
- [X] T044 [US3] `src/qello_knowledge/sync/versions.py`(새 파일, data-model 2.2~2.4): 활성화·되돌리기·정리 조건 함수(게이트 확인 결과는 조건 이름·값으로 받음, `gate`·`evaluation`을 가져오지 않음), 미리 보기 값 조립(contracts/cli.md 3~5절 출력 키),
  해소 방법 목록, 불일치 상태 보기 조립. 순수 함수. T038 통과.
- [X] T045 [US3] `src/qello_knowledge/indexer/index_cli.py`(새 파일, contracts/cli.md 2·3절, research R-15): `index` 명령을 `sync_cli.query_command`에서 옮긴다. 버전 저장소는 `getattr(store, "index_versions", None)`으로 찾고,
  없으면 `status`는 지금 키(`active`, `ready`, `current`, `matches`), `activate`는 활성 없음일 때 지금 첫 활성화, 활성 있음이면 종료 2 `store_unavailable`. `activate`: 활성 있음 → `--gate` 필수(`gate_record_required`),
  미리 보기(종료 4) / `--confirm` 전환(종료 0) / 조건 미충족(1) / 잠금(6). 미리 보기의 `uncovered_sources`(`[{ name, kind }]`), `retrieval_settings`(정책 값과 `RetrievalSettings()` 값), `notes`(벡터 근사 색인 안내 고정 문구).
  `SchemaOutdated`는 `StoreError`보다 먼저 잡아 종료 1 `schema_outdated`. `main(…, history_factory=GitHistory, gate_verifier=verify.verify_for_activation)` 주입점을 둔다(게이트 확인은 이 주입점으로만 부른다).
  지금 `query_command`의 사전 처리를 공용 도우미로 빼서 `runs`와 `index`가 함께 쓴다: `QK_CODE_CHUNKING`이 `INVALID`면 저장소를 만들기 전에 종료 1과 보고서, 현재 설정 버전을 코드 청킹·Confluence 등록 이력까지 보고 다시 계산해 `store.current_version`에 넣기,
  `sync_store_factory(source, version)` 시그니처 유지(`tests/unit/indexer/test_code_sync_cli.py`가 기대는 동작). 활성 버전이 있을 때 `activate`의 확인 순서: `--gate` 없음 → 종료 1 `gate_record_required`, 그다음 버전 저장소 없음 → 종료 2 `store_unavailable`. 쓰기 명령 목록에 `activate`·`rollback`·`prune`을 두어 원격 확인(`--allow-remote`)·저장소 정책·자료원 검토 검사를 건다.
  `indexer/cli.py`가 `index`를 이 파일로 넘기고 `query_command`는 `runs`만 맡는다. T040·T041·T042 통과.

**Checkpoint**: US1 + US2 + US3으로 재색인 → 게이트 → 활성화가 로컬에서 끝까지 돈다.

---

## Phase 6: User Story 4 - 문제가 생기면 보관 버전으로 되돌린다 (P2)

**Goal**: `qk-index index rollback <버전> --reason … --confirm`이 보관 버전을 다시 활성으로 바꾼다.

**Independent Test**: V1 보관·V2 활성에서 되돌리면 V1 활성·V2 보관이 되고, 내린 문서와 본문 삭제 대기 본문이 V1 검색에 나오지 않으며, 정리된 버전은 거부된다.

- [X] T046 [P] [US4] `tests/unit/sync/test_rollback_conditions.py`(data-model 2.4 되돌리기): `reason_required`(없음·201자), `reason_secret`(`tests/unit/synthetic_secrets.py`의 합성 비밀값), `not_archived`, `pruned`, `never_active`,
  `purge_pending`, `sync_running`, `provenance_unconfirmed`(출처 어긋남 ≥ 1이고 `--confirm-stale` 없음), `no_active_version`.
- [X] T047 [P] [US4] `tests/unit/indexer/test_index_rollback_cli.py`(contracts/cli.md 4절): 옵션·종료 코드·원격 확인·출력 키(`mismatch_after`, `resolutions`), 버전 저장소가 없는 대역은 종료 2 `store_unavailable`, 사유 문자열이 출력에 다시 나오지 않음.
- [X] T048 [US4] `tests/localdb/sync/test_index_rollback.py`(SC-002 되돌리기, US4-1~US4-6): 조건마다 하나씩만 어긴 사례에서 거부·상태 불변. 성공 시 V1 활성·V2 보관, 전환 행에 사유와 출처 어긋남 수, 게이트를 거치지 않음.
  미리 보기 값(V1 청크 없는 노출 문서 수, 출처 어긋남 = V1 청크 `source_version` ≠ 자료 행 `source_version`인 노출 문서 수, 대기 목록에 V1이 든 문서 수), V2 활성 기간에 내린 문서가 되돌린 뒤 V1에도 안 나옴,
  되돌린 뒤 현재 설정 버전 ≠ 활성이면 출력 `mismatch_after: true`와 해소 방법(US4-2).
- [X] T049 [US4] `src/qello_knowledge/indexer/index_cli.py`에 `rollback`(contracts/cli.md 4절), `sync/versions.py`의 되돌리기 조건 연결, `adapters/postgres/index_versions.py`의 `rollback_state` 질의.
  사유는 `domain/secret_rules.find_secrets`로 검사하고 출력에 다시 내지 않는다(전환 기록에만 저장). 원격 확인은 T045의 쓰기 명령 규칙. T046·T047·T048 통과.

---

## Phase 7: User Story 5 - 버전 상태를 보고, 쓰지 않는 버전을 정리하고, 불일치를 해소한다 (P2)

**Goal**: `qk-index index status`가 버전별 상태와 해소 방법을, `qk-index index prune`이 확인 뒤 청크 정리를 한다.

**Independent Test**: 준비 둘·보관 둘·활성 하나에서 상태 값이 DB와 같고, 정리 거부 조건마다 거부되며, 정리한 버전 청크 0·다른 버전 청크와 임베딩 그대로·대기 목록에서 빠짐.

- [X] T050 [P] [US5] `tests/unit/sync/test_prune_conditions.py`(data-model 2.4 정리): `active_version`, `current_version`, `rollback_target_unconfirmed`, `sync_running`, 이미 정리됐고 남은 청크 0이면 바뀌는 것 없이 성공.
- [X] T051 [P] [US5] `tests/unit/indexer/test_index_prune_cli.py`(contracts/cli.md 2·5절): `status` 새 키와 `prune` 옵션·종료 코드(0·1·4)·원격 확인·출력 키, 버전 저장소가 없는 대역에서 `prune`은 종료 2 `store_unavailable`.
- [X] T052 [US5] `tests/localdb/sync/test_index_status.py`(US5-1, FR-026, research R-17): 버전 다섯 개의 `status`·재료·문서·청크 수·`pruned_at`·마지막 재색인·활성 이력·`prune_candidate`·`rollback_target`이 DB와 같고,
  덮음은 현재 설정 버전만 값(그 밖은 `null`과 `coverage_note: "not_current_version"`), 불일치면 `mismatch_since`와 `resolutions` 두 가지, 처리 실패 문서 목록(위치·단계), 읽기 전용(전후 표 행 수 같음).
- [X] T053 [US5] `tests/localdb/sync/test_index_prune.py`(SC-005, US5-2~US5-5): 확인 옵션 없으면 지울 청크 수만, 활성·현재 설정 버전 거부, 가장 최근 보관 버전은 `--confirm-rollback-target` 필요, 다른 연결이 공유 잠금을 쥐면 `sync_running`,
  성공 시 대상 청크 0·다른 버전 청크와 `qk.embedding` 행 수 그대로·모든 자료 행 `purge_pending`에서 대상 제거·비면 `purge_reason` NULL·`archived` + `pruned_at`·전환 행 `prune`.
  묶음 크기 2로 첫 묶음 뒤 예외를 넣어 중단하고 다시 실행하면 남은 청크만 지운다.
- [X] T054 [US5] `src/qello_knowledge/indexer/index_cli.py`에 `status` 새 키(contracts/cli.md 2절)와 `prune`(5절), `adapters/postgres/index_versions.py`의 `prune_state`·`prune_batch`·`finish_prune` 연결. 원격 확인은 T045의 쓰기 명령 규칙.
  T050~T053 통과.

---

## Phase 8: Polish & Cross-Cutting

- [X] T055 `docs/ops/oci-production-store.md`에 "인덱스 버전 교체" 절을 더한다: 0009 먼저 적용 뒤 코드 배포(research R-18), 재색인 → 평가 대상 준비(기준은 활성 버전 커밋의 `git worktree`) → 게이트 → 실행 기록·게이트 기록 커밋 →
  `git fetch origin` → 활성화 미리 보기 → `--confirm`, 되돌리기, 정리, 예상 Neurons 합계 보고(quickstart 3절 표), 벡터 근사 색인 한계, 되돌리기 사유에 사람 이름을 쓰지 않음, `replace_chunks`는 0009 없는 DB에서 SQL 오류.
  접속 정보·서버 주소는 쓰지 않는다.
- [X] T056 quickstart.md 1절 표의 시험 위치를 이 목록의 시험 파일과 같게 고치고, 2절을 "선택 단계, 완료 판정에 넣지 않음"으로 고친다. `qk-index run`은 Workers AI 제공자와 실제 자료원 설정으로 조립돼 CLI에서 가짜로 바꿀 수 없고, 같은 흐름은 T019·T041이 주입 시험으로 덮는다고 적는다.
- [X] T057 기본 검증 전체(quickstart 1절, AGENTS.md 7절): `python scripts/preflight.py`, `git diff --check`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run qk-dev db up`, `QK_REQUIRE_LOCALDB=1 uv run pytest`.
  결과(통과 수, 실패, 건너뛴 시험과 이유)를 "실행 기록"에 남긴다. `git diff --stat main -- tests/`로 바뀐 기존 시험 파일이 T002의 `tests/unit/test_boundaries.py` 하나뿐인지 확인한다.
- [X] T058 구현 검토: 작성에 관여하지 않은 별도 에이전트가 실제 diff·명령 결과를 spec·plan·contracts와 대조한다(AGENTS.md 2절). 지적과 반영을 `checklists/implementation-review.md`에 남긴다.
- [X] T059 `/pr-draft-summary`로 PR 제목·본문 초안을 만든다(초안만, push·PR 생성은 사람 승인 뒤 `/harness-pr`).

---

## 이 브랜치 밖의 사람 단계 (US6, SC-009)

TASK.md 제외 범위다. 이 목록의 완료 판정에 넣지 않는다. 순서는 quickstart.md 3절 H1~H9: 운영 0009 적용 → 새 코드 배포 → 첫 게이트 정책 값 결정과 정책 PR 병합 → 설정 변경 배포 → 예상 Neurons 합계 보고·승인 →
운영 재색인 → 평가 대상 준비와 `eval run` → 게이트 → 기록 커밋 → 활성화 → Jira 증빙. ADR-010 Status 결정(H08, QK-EVL-001) 뒤 별도 작업으로 한다.

---

## Dependencies & Execution Order

- Phase 1(T001~T003) → Phase 2(T004~T014) → US1(T015~T026). US2(T027~T037)는 Phase 1 뒤 바로 시작할 수 있다(저장소를 쓰지 않음).
- US3(T038~T045)은 Phase 2, US1의 T024~T026(실행 `kind`, 후보 준비, CLI 조립), US2의 T033~T036 뒤.
- US4(T046~T049)는 US3 뒤. US5(T050~T054)는 US4 뒤. 셋 다 `indexer/index_cli.py`와 `sync/versions.py`를 고치므로 US3 → US4 → US5 순서로 한다.
- Phase 8은 모든 스토리 뒤.
- 시험 작업은 같은 단계의 구현 작업보다 앞이다. 도우미·픽스처(T015, T027)는 그것을 쓰는 시험보다 앞이다.

## 커밋 단위 (plan 승인 2026-11-05: PR 하나, 커밋은 검토 목적별)

1. 계약: `TASK.md`, plan·research·data-model·contracts·quickstart·검토 기록, tasks.md(이 목록 승인 뒤)
2. 저장 변경: T001·T002·T004~T014(자리, 경계 시험, 마이그레이션, 청크 출처, 전환 기록, 0009 확인, 버전 저장소)
3. 재색인: T015~T026
4. 게이트: T027~T037
5. 활성화·되돌리기·상태·정리: T038~T054
6. 운영 문서·quickstart·실행 기록·검토 기록: T055~T058

T003은 메시지 작업이라 커밋이 없다(결과는 6번 커밋의 실행 기록). 정책 커밋 규칙(FR-012)은 운영 정책을 더하는 US6 작업에 적용된다. 이 브랜치의 정책 파일은 시험 픽스처뿐이다.

## Parallel Example

```text
Phase 2: T004, T005, T006, T007, T008 (시험) 병렬 → T009 → T010 → T011 → T012, T013 병렬 → T014
US1: T015 → T016, T017, T018 병렬 → T019, T020 → T021 → T022 → T023 → T024 → T025 → T026
US2 (Phase 2와 병렬 가능): T027 → T028, T029, T030, T031, T032 병렬 → T033 → T034 → T035 → T036 → T037
```

## Implementation Strategy

- MVP: Phase 1·2 + US1(재색인)까지. 이것만으로 불일치 상태에서 후보 버전을 채울 수 있다(활성화는 아직 불가).
- 그다음 US2(게이트) → US3(활성화)으로 재색인 → 게이트 → 활성화를 완성한다. US4·US5는 운영 안전장치다.
- 각 Checkpoint에서 `QK_REQUIRE_LOCALDB=1 uv run pytest`를 돌려 기존 시험이 깨지지 않았는지 본다.

## TASK.md Scope 갱신안 (이 목록 승인과 함께 반영)

`TASK.md` Scope "코드"에 다음을 더하고 빼는 것을 반영한다(plan "구현 Scope 승인이 필요한 것").

- 더함: `src/qello_knowledge/gate/**`, `src/qello_knowledge/ports/history.py`, `src/qello_knowledge/ports/index_versions.py`, `src/qello_knowledge/adapters/git_history.py`,
  `src/qello_knowledge/adapters/postgres/store.py`(`_replace_chunk_rows`·`trace_chunk`만), `src/qello_knowledge/domain/store.py`(`SchemaOutdated`만), `src/qello_knowledge/devtools/gate_cli.py`, `src/qello_knowledge/devtools/db.py`(`eval gate` 등록만),
  `src/qello_knowledge/indexer/index_cli.py`, `src/qello_knowledge/indexer/cli.py`, `tests/unit/test_boundaries.py`(검사 추가만)
- 다른 명세 코드를 고치는 것: QK-STO-001(`_replace_chunk_rows`, `trace_chunk`, `qk.hit_json` 교체), QK-SYN-001(`sync/plan.py`·`decide.py`·`execute.py`·`preview.py`·`run.py`, `sync_store.py`, `indexer/sync_cli.py`의 `index` 명령 이동과 `build_runtime` 실행 위치 전달)
- 뺌: `src/qello_knowledge/devtools/eval_index.py`(research R-13, 바꾸지 않음)

## 실행 기록

- 2026-11-05 T003 사전 확인(읽기 전용): QK-ING-003 워크트리(`docs/SCRUM-119-gh-72-confluence-pages-closeout`)는 설정·문서 파일만 바뀌었고 마이그레이션은 `0008`까지라 `0009`와 겹치지 않는다.
  겹치는 파일은 `TASK.md`뿐이다. 알림 메시지 전송은 사람 확인 대기.
- 2026-11-05 구현 중 바꾼 점(승인한 설계와 다른 것):
  - 원본 수정 시각은 NULL일 수 있어, `qk.hit_json`·`trace_chunk`가 청크 `source_url`이 NULL인 옛 행에서만 자료 행 값을 쓴다(단순 `coalesce`면 다른 버전의 값이 끼어든다). data-model 1.1에 반영. 시험 `test_chunk_provenance.py`.
  - T027: 사례마다 실행 기록 JSON을 손으로 두지 않고 `tests/unit/gate/gate_builders.py`가 QK-EVL-001 계약 그대로 만들어 `write_record`로 쓴다(계약 필드가 많아 손 작성 파일이 어긋나기 쉽다). 손 계산 값은 `tests/fixtures/gate/README.md`와 시험 단언.
  - T012·T014: `prune_batch`·`finish_prune` 둘 대신 잠금을 쥔 채 묶음마다 커밋하는 `prune(version, *, check, batch_size, after_batch)` 하나로 합쳤다(중간에 동기화가 끼지 않게). `rollback_target()`을 더했다.
  - US1-9(임베딩 모델 교체 미리 보기): 등록된 임베딩 모델이 하나뿐이라 모델을 바꾸는 시험은 못 했다. 캐시가 빈 경우로 전체 재임베딩 비용이 보이는지 확인했다(캐시 키가 (입력, 모델)이라 같은 경로다).
  - T019: 보안 내림·원본 삭제를 함께 넣은 시험은 내림 비율 안전장치(20%)를 넘어 `confirm_takedown=True`로 돌렸다. 대기 본문 문서 G는 확인 옵션으로 본문 삭제(PURGE)가 되고 처리(되살리기)는 하지 않는다.
  - T042: 검색 76회, 섞인 결과 0, 활성 없음 0, `index_version_changed` 6.
  - 사전 검사가 시험 변수 이름 `TOKENIZER`·`SECRET_LIKE`를 비밀값 이름 패턴으로 잡아 이름을 바꿨다(검사를 끄지 않음).
- 2026-11-05 운영 문서 확인: 서버 예약 동기화는 매번 최신 `main`을 받아 실행하고, 운영 문서 6절은 새 마이그레이션이 든 PR을 병합 전에 운영 DB에 적용하게 한다. 이 PR 병합 전 운영 `0009` 적용이 필요하다(사람 단계, 이 브랜치 밖).
- 2026-11-05 전체 시험(첫 실행): 3,975 passed, 2 failed(`tests/localdb/query/test_obs_consent_db.py` 두 사례), 3 deselected(`external`). 같은 시간에 사전 검사를 함께 돌렸다. 그 파일만 다시 돌리면 8 passed. T057에서 부하 없이 다시 확인한다.
- 2026-11-05 T058 구현 검토(별도 서브에이전트): 1차 변경 요청 7건(높음 1: 정리한 버전 재사용 시 청크 없는 문서가 덮음으로 세어져 활성화 뒤 사라짐, 재현됨)을 반영했고 2차 "승인 가능". 2차 새 지적 2건도 반영(정리 시작 표시, 0009 확인 예외 매핑, 재검토 없음). 기록은 `checklists/implementation-review.md`.
- 2026-11-05 T057 기본 검증(최종 코드, 다른 부하 없이): `python3 scripts/preflight.py` 1,070개 통과, `git diff --check` 통과, `uv run ruff check .` 통과, `uv run ruff format --check .` 791개, `uv run qk-dev db up` 준비,
  `QK_REQUIRE_LOCALDB=1 uv run pytest` 3,984 passed, 3 deselected(`external`). 첫 실행에서 실패한 `test_obs_consent_db.py` 두 사례는 부하 없는 두 번의 전체 실행에서 모두 통과했다.
  `git diff --stat main -- tests/`로 바뀐 기존 시험 파일은 `tests/unit/test_boundaries.py`(검사 추가) 하나다. 외부 호출 0, Neurons 0.
