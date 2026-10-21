# Contract: 동기화 흐름과 `SyncStore` 경계

**명세**: [../spec.md](../spec.md) · **타입**: [../data-model.md](../data-model.md) · **결정**: [../research.md](../research.md)

## 1. 진입 함수 (`sync/`)

| 함수 | 입력 | 출력 | 쓰기 |
| --- | --- | --- | --- |
| `plan_source(target, deps, stored, index_version, options)` | 대상 자료원 하나(`FULL`이면 설정·어댑터·세션, `TAKEDOWN_ONLY`면 저장된 자료원 정보만), 보안 정책·청킹 설정, 저장 상태, 이번 실행의 인덱스 버전, 판단 옵션 | `SourcePlan` | 없음(원본 읽기만) |
| `preview(plans, embedder, model_version, index_state, options)` | 모든 대상의 `SourcePlan` | `SyncPreview` | 없음. `Embedder.preview()`를 한 번 부른다 |
| `run_sync(targets, deps, options)` | 대상 자료원, 의존성 묶음, 실행 옵션 | `SyncRunResult` | 아래 순서로만 쓴다 |
| `activate_first_index(store, version)` | 인덱스 버전 | `ActivationCheck` | 조건을 모두 채울 때만 상태 변경 |

대상 자료원은 현재 설정의 활성 자료원(`FULL`)과, `qk.sync_source`에 있지만 설정에서 빠졌거나 꺼진 자료원(`TAKEDOWN_ONLY`, 일반 내림만)이다. `--source NAME`이면 그 하나만이다
(research R-06). `plan_source(FULL)`은 `screen_source()`(결과의 `listing` 포함)를 부르고, research R-03의 변경 조건으로 `PROCESS` 판정된 문서만 `chunk_screened()`에 넘기며, research R-18대로 저장된 문서를 판정한다.

`run_sync`의 순서(spec FR-002·FR-024·FR-027·FR-029, research R-06·R-17):

1. 실행 전 점검(설정, 자료원·개인 정보 확인 기록, 보안 규칙, 예산 설정, 원격 확인 옵션, 운영 저장소 정책 파일, 저장소 연결, 자료원 식별 (a)~(c)). 실패하면 쓰기 없이 끝낸다.
2. 잠금(대상 자료원 종류별 배타 + 전역 공유). 못 잡으면 쓰기 없이 "이미 실행 중". 잡은 뒤 자료원 식별 (a)~(c)를 다시 검사하고, 실패하면 잠금을 놓고 쓰기 없이 끝낸다.
3. 같은 종류의 `running` 기록을 `unfinished`로 닫고, `qk.sync_run`·`qk.sync_run_source`를 `running`으로 만든다.
4. 인덱스 버전 결정: 활성 버전이 없으면 현재 설정 버전을 `ready`로 보장(`ensure_index_version`). 활성 버전이 있고 다르면 `INDEX_MISMATCH` 보류.
5. 모든 대상의 `plan_source()`를 먼저 만든다. 수집 뒤 정체성 확인(`MISMATCH`·`MISSING`이면 그 자료원 `ORIGIN_*` 보류).
6. 예산 판정: 처리할 모든 문서의 임베딩 입력으로 `Embedder.preview()`를 한 번 부른다. 실행 가능하지 않고 부분 실행 옵션이 없으면 모든 자료원에 `BUDGET_EXCEEDED` 보류.
7. 자료원마다 쓰기(각 작업은 data-model 2.4 허용표가 허용할 때만): 정체성 기준값 등록(`REGISTER`면 이 자료원의 첫 문서 쓰기 직전) → 보안 내림(검색 제외, 삭제 또는 대기) → 일반 내림
   → 삭제 대기 본문 지우기(확인 옵션이 있을 때) → 바뀐 문서마다 캐시 확인·임베딩·반영(research R-17) → 변경 없음 문서 `mark_seen` → 보류·건너뜀·실패 결과 기록. 보안 내림을 먼저 하는 이유는 뒤 단계가 예산·저장
   오류로 멈춰도 검색 제외는 이미 끝나 있게 하기 위해서다(spec FR-004).
8. 자료원 기록과 실행 기록을 최종 상태로 닫는다(data-model 3.2). 잠금을 놓는다.

바뀐 문서 하나는 먼저 캐시를 확인하고(모두 있으면 `embed()`를 부르지 않는다), 아니면 그 문서의 `ChunkDraft.embedding_text`를 담은 `EmbedRequest` 하나로 `embed()`를 부른다.
`origin`은 `(source_name, location)`이다. 모든 항목에 벡터가 있으면 `apply_document`, 하나라도 실패면 그 문서만 `FAILED(embed, <실패 종류>)`다(spec FR-014). 할당·예산 소진,
사용량 장부 오류(항목 실패·요약 경고), `EmbedError` 중 하나가 나면 실행 소진 상태를 켜고, 그 뒤 캐시에 없는 청크가 있는 문서는 `HOLD(BUDGET_EXHAUSTED)`로 기록한다(research R-17).

## 2. `SyncStore` (`ports/sync.py`)

모든 쓰기 연산은 문서 하나(또는 목록에 적힌 문서 묶음) = 트랜잭션 하나이고, 같은 트랜잭션에서 문서별 결과 행을 넣는다(research R-04). 오류는 QK-STO-001의 `StoreError` 계열을 쓴다.

| 메서드 | 설명 | 실패 시 |
| --- | --- | --- |
| `index_state() -> IndexState` | 활성 버전, 준비 버전 목록 | `StoreUnavailable` |
| `ensure_index_version(spec) -> str` | 없으면 `ready`로 만든다. 있으면 그대로. 재실행 안전 | |
| `load_documents(source_kind) -> Mapping[str, StoredDocument]` | 원본 식별자 → 저장 상태(1.1 열). 본문 없음 | |
| `load_sources() -> Mapping[str, StoredSource]` | `qk.sync_source` 전체 | |
| `try_lock(source_kinds) -> SyncLock \| None` | research R-06(종류별 배타 + 전역 공유). 반환된 잠금은 `close()`로 놓는다 | |
| `begin_run(run, source_names) -> None` | 잠근 종류의 `running` 기록 닫기 + 새 기록 | |
| `register_origin(source_name, kind, scope_key, origin)` | 기준값 등록(없을 때만). 종류 유일 제약 위반이면 `StoreError`로 그 자료원 처리 중단 | |
| `apply_document(run_id, doc, artifact, index_version, chunks) -> int` | 원본 자료 행 + 이번 버전 청크 교체 + 결과 행 | 트랜잭션 전체 취소, 이전 상태 유지 |
| `take_down(run_id, doc, reason, access_scope, delete_bodies)` | 일반·보안 내림(1.1, research R-04 표) | 같음 |
| `purge_pending_bodies(run_id, doc)` | `purge_pending`의 버전 청크 삭제 | 같음 |
| `mark_seen(run_id, docs, version, at)` | 변경 없음 문서들 | 같음 |
| `record_outcome(run_id, doc, action, outcome)` | 저장 변화 없는 결과(`FAIL`·`HOLD`·`SKIP`). 작업마다 행 하나(기본 키 `(run_id, doc_key, action)`) | |
| `finish_source(run_id, source_name, status, summary)`, `finish_run(run_id, status, summary)` | 최종 상태 | |
| `activation_check(version) -> ActivationCheck`, `activate(version) -> ActivationCheck` | research R-09. `activate`는 전역 배타 잠금 안에서 확인과 변경을 한 트랜잭션으로 | 조건 실패면 변경 없음 |
| `list_runs(limit)`, `run_detail(run_id)`, `run_failures(run_id)`, `prune_runs(retention_days)` | 조회·정리(research R-11). 정리는 `running` 제외, 기간 1일 이상 | |

가짜 구현 `tests/unit/sync/fake_store.py`는 같은 Protocol을 메모리로 구현하고, 장애 주입(지정한 문서의 `apply_document`에서 오류)을 지원한다.

## 3. 다른 경계에 더하는 것

| 경계 | 더하는 것 | 기존 동작 |
| --- | --- | --- |
| QK-ING-001 `domain/source.py` | `SourceOrigin(origin_id, origin_name, version)`, `ListPage.origin`, `Listing.origin`(기본 `None`) | 그대로. 값이 없는 어댑터도 계약 통과 |
| QK-ING-001 `sources/collect.py` `list_all` | 첫 페이지 `origin`을 `Listing.origin`에 담는다 | 그대로 |
| QK-ING-002 `adapters/github.py` | 저장소 응답의 `id`·`full_name`과 확정 커밋을 첫 페이지 `origin`에 채운다 | 요청 수 그대로(83회) |
| QK-SEC-001 `domain/security.py`·`security/screen.py` | `ScreenResult.listing: Listing \| None`(기본 `None`)을 더하고 `screen_source()`가 채운다. 자료원 제외 판정의 공개 이름 `source_excluded`(기존 `_source_excluded`와 같은 동작)를 더한다(research R-18) | 판정·요약·기록 그대로 |
| QK-ING-001 `adapters/fake.py` | 시험 응답의 `origin` 필드 | 그대로 |
| 공통 계약 시험 | `origin`이 있으면 두 값 모두 비어 있지 않은 문자열 | 기존 항목 그대로 |
| QK-STO-001 `adapters/postgres/store.py` | `replace_chunks`의 청크 지우기·넣기를 내부 함수로 분리해 `sync_store.py`와 같이 쓴다 | 동작·시험 그대로 |
| `tests/unit/test_boundaries.py` | `sync`는 `domain`·`ports`·`embedding`·`chunking`·`security`·`sources`와 표준 라이브러리만 가져온다. `adapters`는 금지 | 기존 규칙 그대로 |

## 4. 보장과 시험 대응

| spec | 보장 | 시험(quickstart 1절) |
| --- | --- | --- |
| FR-008·009, SC-001·002 | 변경 없음이면 임베딩 요청 0, 청크 교체 0 | `test_incremental.py` |
| FR-013·014, SC-004·006 | 문서 단위 원자 반영, 실패 시 이전 상태 | `test_atomic.py`(로컬 DB) |
| FR-015~018, SC-003·005·015 | 보안 우선 검색 제외, 삭제 대기, 비율 | `test_takedown.py`(로컬 DB) |
| FR-019~021, SC-014 | 준비 버전, 활성화 조건, 배타 | `test_index_version.py`(로컬 DB) |
| FR-022~025, SC-007·008 | 미리 보기 무쓰기, 대상 집합 일치, 예산 | `test_preview_budget.py` |
| FR-026~028, SC-009 | 실행 기록, 내부 식별값, 원문 없음 | `test_run_record.py` |
| FR-029, SC-010·011 | 잠금, 끝나지 않은 기록, 무쓰기 거부 | `test_concurrency.py`(로컬 DB) |
| FR-002, SC-011 | 자료원 정체성 | `test_identity.py` |
