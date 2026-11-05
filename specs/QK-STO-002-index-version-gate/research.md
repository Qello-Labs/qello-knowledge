# Research: QK-STO-002 인덱스 버전 생성·평가 게이트·활성화

**Date**: 2026-11-05 | **Spec**: [spec.md](spec.md)(2026-11-02 승인)

코드 근거는 2026-11-05 브랜치 `feat/SCRUM-125-gh-100-index-version-gate-impl`(`origin/main` `6685b88`)에서 읽었다. `NEEDS CLARIFICATION`은 없다.
spec이 plan으로 넘긴 것(명령 이름, 파일 경로, 저장 스키마 변경, 운영 절차 문서, FR-005의 방법, D4의 경로와 운영 쪽 확인 방법)은 아래 결정에 있다.

## R-01 버전별 출처 정보: 청크 행에 출처 열을 둔다 (FR-005, D7, SC-001)

- **Decision**: `qk.chunk`에 `source_url`, `source_modified_at`, `collected_at` 열을 더한다(`source_version`은 이미 청크에 있다). 청크를 쓰는 유일한 함수
  `adapters/postgres/store.py`의 `_replace_chunk_rows`가 같은 트랜잭션에서 그 자료 행의 값을 읽어 청크 행에 함께 쓴다. 검색 결과를 만드는 `qk.hit_json`과
  출처 추적 `PostgresStore.trace_chunk`는 `coalesce(c.<열>, a.<열>)`로 청크 값을 먼저 쓴다. 새 마이그레이션이 기존 청크를 지금 자료 행 값으로 채운다.
  그러면 재색인이 자료 행(`qk.artifact`)의 문서 단위 값을 덮어써도 활성 버전 청크의 출처 정보는 그 청크를 쓴 때의 값 그대로다.
  제목(`title`)은 검색 결과·출처 정보 어디에도 나오지 않아(`0002`의 `qk.hit_json`, `domain/store.py`의 `Provenance`) 청크 열로 두지 않는다. spec FR-005의 "제목"은 결과에 나오는 값이 없으므로 확인 대상이 없다.
  QK-STO-001 `replace_chunks`가 묶음 해시가 같아 `unchanged`를 돌려주는 경로는 청크를 다시 쓰지 않으므로 출처 열도 그대로다(그 경로를 부르는 곳은 `devtools/bench.py`뿐).
- **Rationale**: 지금 출처 정보 가운데 원본 링크·원본 수정 시각·수집 시각은 자료 행에서 온다(`0002_search_functions.sql`의 `qk.hit_json`). `apply_document`는 처리할 때마다 자료 행을 덮어쓴다
  (`sync_store.py`). 바뀌지 않은 문서만 덮어쓰지 않게 하는 안은 원본에서 바뀐 문서를 재색인할 때 활성 버전 청크(옛 본문)와 자료 행(새 링크·시각)이 어긋나 FR-005를 못 채운다.
  청크 행에 두면 청크 교체와 출처 정보가 한 문장으로 같이 바뀌고, 정리(청크 삭제)가 출처 정보도 함께 지운다. 검색 함수의 출력 키는 그대로다(QK-STO-001 `contracts/store.md`).
- **D7 되돌리기 출처 어긋남의 뜻**: 버전별 출처 정보가 생기면 되돌린 버전의 검색 결과는 그 청크를 쓴 때의 본문·링크·원본 버전을 함께 보여 서로 어긋나지 않는다.
  남는 차이는 "되돌린 버전의 청크가 문서의 마지막 처리 원본 버전보다 옛 것"이다. 그래서 출처 어긋남 문서 수는 대상 버전 청크의 `source_version`이 자료 행의 `source_version`과 다른
  노출 문서 수로 센다(spec 문구 "대상 버전 청크와 지금 문서 단위 출처 정보가 어긋나는 문서"). 1개 이상이면 FR-024대로 별도 확인 옵션이 있어야 되돌린다.
- **배포 호환**: 열은 NULL 허용이다. 새 마이그레이션을 먼저 적용하고 옛 코드가 잠시 돌아도 옛 `INSERT`가 실패하지 않고 `hit_json`은 자료 행 값으로 돌아간다(지금 동작).
  반대 순서(새 코드가 0009 없이 돎)는 막는다. 순서와 확인 방법은 R-18.
- **벡터 근사 색인의 한계**: HNSW 색인은 `qk.embedding` 하나에 걸려 모든 버전이 함께 쓴다(`0001_initial_schema.sql`). 재색인이 새 임베딩 행을 더하면 근사 탐색 경로가 바뀌어
  활성 버전의 벡터 검색 결과가 근사 오차 범위에서 달라질 수 있다. 키워드 검색과 출처 정보는 정확히 그대로다. 임베딩 입력이 같은 변경(예: ADR-010 B)은 캐시 적중이라 새 임베딩 행이 없어 영향이 없다.
  SC-001은 spec대로 근사 결과가 정확 검색과 같아지는 크기로 시험하고, 이 한계는 운영 문서와 활성화 미리 보기 안내에 적는다. 재색인 중 활성 버전 벡터 검색을 정확 검색으로 바꾸는 안은
  검색 함수 성능을 바꾸므로 고르지 않았다.
- **Alternatives considered**: 버전별 자료 표 `qk.artifact_version(artifact_id, index_version, …)`(검색 함수 다섯 개가 조인을 하나 더 하고 정리·재사용 때 함께 관리해야 한다),
  재색인 동안 자료 행을 갱신하지 않기(위 이유로 FR-005 실패), 열을 NOT NULL로 두기(배포 순서가 어긋나면 동기화가 멈춘다).

## R-02 재색인 실행 경로: `qk-index run --reindex` (FR-004~FR-009, FR-029)

- **Decision**: 재색인은 지금 동기화(`sync/run.py`의 `run_sync`)를 그대로 쓰고 `SyncOptions.reindex = True`만 다르다. 차이는 넷이다.
  (1) 불일치 상태일 때만 실행한다. 활성 버전이 없으면 `no_active_version`(첫 색인은 지금 `run` 그대로), 현재 설정 버전과 같으면 `not_mismatched`로 쓰기 전에 멈춘다.
  (2) `INDEX_MISMATCH` 보류를 붙이지 않는다. 그래서 바뀐 문서 처리와 설정과 무관한 일반 내림(원본에서 사라짐, 자료원 끔, 자료원 설정 제외)을 지금 규칙과 비율 안전장치대로 한다(FR-010).
  (3) 실행 기록에 `qk.sync_run.kind = 'reindex'`를 남긴다. (4) `--trigger schedule`, `--source`와 함께 쓸 수 없다(FR-029, 일부 자료원만 처리한 실행이 FR-021 (2)를 채우지 않게).
  예약 실행은 지금처럼 불일치로 보류한다(D2). 후보 버전 준비(R-06)는 `begin_run` 직후 잠금 안에서 한다.
- **지금 노출되지 않는 문서는 처리하지 않는다**: 저장 상태가 `status ≠ 'active'` 또는 `access_scope ≠ 'team'`인 문서(내린 문서, 보안 보류 문서)는 재색인에서 다시 처리할 이유가 생겨도
  (`REINSTATED` 등) `PROCESS`를 하지 않고 결과를 `HELD`(`failure = reindex_hidden`)로 남긴다. `apply_document`는 자료 행을 `status='active'`, `access_scope='team'`으로 되살리는데(`sync_store.py`의 자료 행 갱신),
  내림은 다른 버전의 청크를 남기므로(일반 내림은 모든 버전, 보안 내림은 본문 삭제가 보류되면 대기 목록의 버전) 재색인이 되살리면 활성 버전의 옛 청크가 다시 검색된다.
  이는 FR-005("내린 문서가 빠지는 것만 다르다")를 어긴다. 이 문서들은 덮음의 분모(지금 노출 문서, R-04)에 들지 않아 활성화를 막지 않고, 활성화 뒤 첫 동기화가 지금 규칙대로 다시 처리한다.
  처음 보는 문서(자료 행 없음)는 활성 버전 청크가 없어 그대로 처리한다.
- **예산 초과**: 재색인은 계획을 세운 뒤 `begin_run` 전에 `Embedder.preview()`로 판정한다. 넘으면 기본은 실행 기록도 쓰지 않고 `budget_exceeded`(종료 5)로 멈춘다(FR-006 "기본은 실행하지 않는다").
  그 계획에서 찾은 보안 내림도 이 실행에서는 반영되지 않는다. 다음 예약 실행이 불일치 보류 아래에서도 보안 내림(`SECURITY_HIDE`·`SECURITY_PURGE`)을 하므로(`domain/sync.py`의 `ALLOWED`) 늦어도 하루 안에 반영된다.
  재색인 미리 보기와 거부 출력은 보안 내림 건수를 함께 보인다. `--allow-partial-budget`이면 지금 부분 실행 경로(QK-EMB-001 FR-024)대로 예산 안에서 처리하고 멈춘다.
- **이어 하기**: 처리를 마친 문서는 `processed_index_version = 후보`라 `change_reason`이 바뀜 없음으로 본다(`sync/decide.py`). 다시 실행하면 남은 문서와 그 뒤 바뀐 문서만 처리한다(FR-007, SC-006).
- **Rationale**: 수집·보안 필터·청킹·임베딩·문서 단위 교체를 두 벌로 만들지 않는다(FR-005 "QK-SYN-001과 같은"). 재색인 표시는 활성화 조건(FR-021 (2))이 보류된 예약 실행과 재색인을 가르는 데 쓴다.
- **Alternatives considered**: 별도 명령 `qk-index index reindex`(같은 설정 점검·자료원 조립을 다시 써야 한다), 실행 기록 요약 JSON에만 표시(활성화 조건 질의가 JSON을 뒤져야 하고 제약을 걸 수 없다).

## R-03 새 설정에서만 "대상 아님"인 문서 (FR-010)

- **Decision**: 재색인에서 청킹 결과가 `NOT_MARKDOWN`인 저장 문서 가운데 지금 노출 중인 문서(R-02)는 내리지 않고, 후보 버전에 청크 0개로 처리한다.
  결정에 `not_target = True` 표시를 두고 `sync/execute.py`가 처리 결과를 `not_target`으로 쓴다(지금은 `"chunked" if chunks else "empty"`). 미리 보기(`sync/preview.py`)는 이 결정을 임베딩 요청에서 뺀다. 자료 행은 `processed_outcome = 'not_target'`(새 값)이고
  자료 상태는 `active` 그대로라 활성 버전 청크는 계속 검색된다. 후보 버전 처리 완료로 센다(덮음, R-04).
  재색인이 아닌 동기화에서 `processed_outcome = 'not_target'`이고 `processed_index_version`이 현재 설정 버전과 같으면 변경 사유 `NOT_TARGET_PENDING`(새 값)으로 다시 청킹해
  지금 규칙대로 `NOT_TARGET` 내림을 한다. 활성화 뒤 첫 예약 동기화가 이 내림을 한다(spec FR-010 마지막 문장). 불일치 중 예약 실행에서는 `PROCESS`가 보류돼 그대로다.
- **Rationale**: 지금 `NOT_MARKDOWN`은 바로 `TAKE_DOWN NOT_TARGET`이다(`sync/plan.py`). 재색인에서 그대로 두면 새 설정 때문에 활성 버전 검색에서 문서가 빠진다.
  상태 값 하나로 "처리는 끝났고 활성화 뒤 내릴 문서"를 표시하면 이어 하기와 덮음 계산이 다른 처리 결과와 같은 방식이 된다.
- **Alternatives considered**: 재색인에서 문서를 건너뛰고 미처리로 두기(덮음이 차지 않아 활성화할 수 없다), 활성화 트랜잭션에서 대상 아님 문서를 내리기(활성화가 수집 판단을 알아야 한다).

## R-04 덮음, 남은 문서, 처리 실패 (FR-008, FR-011, FR-021 (3))

- **Decision**: 모두 저장소 질의 하나로 센다.
  - 노출 문서: 활성 버전 청크가 하나 이상 있고 `status = 'active'`, `access_scope = 'team'`인 자료.
  - 덮음: 노출 문서 가운데 `processed_index_version = 후보`인 자료(`processed_outcome`이 `chunked`·`empty`·`not_target` 어느 것이든).
  - 남은 문서: 노출 문서 − 덮음.
  - 처리 실패 문서: 노출 문서 가운데, 후보 버전에 쓴 가장 최근 재색인 실행의 문서 결과가 `FAILED`인 자료(덮음 여부와 관계없다. 예전에 처리를 마쳤지만 원본이 바뀐 뒤 실패한 문서도 든다).
    위치(`doc_display`)와 실패 단계(`stage`)를 함께 낸다. 그래서 `failed_documents`는 `coverage`와 따로 실패할 수 있다.
  - 상태 보기의 덮음은 현재 설정 버전에만 값이 있다. 문서 처리 상태가 버전 하나만 저장해서(spec FR-025) 현재 설정 버전이 아닌 준비 버전(정리 대상)의 덮음은 설정이 바뀐 뒤 계속 줄어 뜻이 없다.
    FR-026 "버전마다 … 덮음"은 버전 목록의 각 항목에 `coverage` 키를 두고 현재 설정 버전이 아니면 `null`과 사유 `not_current_version`을 보이는 것으로 채운다. 활성·보관 버전도 `null`이다.
- **Rationale**: 문서 처리 상태는 버전 하나만 저장하지만(spec FR-025), 재색인 동안에는 활성 버전으로 처리된 문서가 새로 생기지 않는다(불일치 보류). 그래서 `processed_index_version = 후보`가 곧
  "후보 버전 처리를 마침"이다. 새로 생긴 문서(활성 버전 청크 없음)는 분모에 넣지 않는다.
- **Alternatives considered**: 후보 버전 청크 수로 세기(본문 없음·대상 아님 문서를 셀 수 없다), 실행 기록 결과를 모두 합치기(실행 기록 정리 뒤 값이 바뀐다).

## R-05 재색인 미리 보기와 예상 일수 (FR-006, US1-1·US1-9)

- **Decision**: `qk-index run --reindex --preview`는 R-02의 계획을 세우고 `Embedder.preview()`만 붙인다(지금 `--preview`와 같다. 원본 읽기는 하고 임베딩 호출·저장소 쓰기는 0).
  출력: 대상 문서 수, 처리할 문서 수, 임베딩 요청 청크 수, 캐시 적중 수, 새로 임베딩할 청크 수, 예상 Neurons와 계산 근거(`EstimateBasis`), 오늘 색인 예산·사용량·잔여량, 예상 실행 일수, 지금 덮음(R-04).
  예상 일수 = 예상 Neurons가 오늘 잔여량 이하면 1, 아니면 1 + ⌈(예상 − 오늘 잔여) ÷ 일일 색인 예산⌉(`BudgetSettings.index_budget`, 기본 5,000). 예상 0이면 1이다.
  임베딩 모델만 바뀐 경우(US1-9)는 캐시 키가 `(입력 해시, 모델 버전)`이라 캐시 적중이 0으로 나와 전체 재임베딩 비용이 그대로 보인다(QK-EMB-001 캐시 규칙).
- **Rationale**: 같은 계산을 쓰면 미리 보기와 실제 실행의 예산 판정이 어긋나지 않는다(QK-EMB-001 FR-024).
- **Alternatives considered**: 청크 수 × 평균 토큰 추정(실제 청킹 결과와 다르다).

## R-06 후보 버전 준비와 재사용 전환 (FR-001, FR-004, US1-7·US1-8, FR-009)

- **Decision**: 재색인은 현재 설정 버전을 다음처럼 준비한다(새 저장 연산 `prepare_candidate`). 없으면 `ready`로 만든다. `ready`면 그대로 쓴다.
  `archived`면 `ready`로 되돌리고 `pruned_at`을 비우며 전환 기록 `reuse`를 남긴다(활성 이력은 전환 기록에 남아 있다). `active`면 불일치가 아니므로 R-02 (1)에서 이미 멈췄다.
  설정이 다시 바뀌어 후보가 V3가 되면 V2는 `ready`로 남고 상태 보기가 "정리 대상"(준비 상태이고 현재 설정 버전이 아님)으로 보인다. V2의 게이트 기록은 활성화가 "대상이 현재 설정 버전"
  조건(FR-021 (1))과 "게이트 기록 후보 = 대상"(FR-021 (6))으로 거부한다.
- **Rationale**: 정리된 버전을 재사용하면 청크가 0개라 재색인이 전부 다시 처리한다(대부분 캐시 적중). 정리 표시를 비워야 상태 보기와 정리 명령이 그 버전을 다시 다룬다.
- **Alternatives considered**: 정리된 버전 ID 재사용 거부(설정을 옛 값으로 되돌리는 정상 경로가 막힌다, spec Edge Cases "같은 재료로 돌아감").

## R-07 전환 기록 표 (FR-002, FR-032)

- **Decision**: 새 표 `qk.index_transition`에 전환마다 한 행을 남긴다. 종류는 `first_activation`·`activation`·`rollback`·`prune`·`reuse`다. 열은 [data-model.md](data-model.md) 1.3.
  QK-SYN-001 첫 활성화(`PostgresSyncStore.activate`)도 같은 트랜잭션에서 `first_activation` 행을 남긴다. 실행 위치는 `PostgresSyncStore`를 만들 때 받는 `target` 값(CLI의 `target_label`)이다
  (생성 인자를 더하고 기본값 `local`, `activate(version)` 시그니처는 그대로). 마이그레이션은 지금 활성 버전이 있으면 `first_activation` 행 하나를
  `details.backfilled = true`, `target = 'unknown'`으로 채운다(시각은 `activated_at`. `unknown`은 채움 행에만 쓰는 값이다). "활성 이력"은 그 버전이 `after_active`인 `first_activation`·`activation`·`rollback` 행이 있는지다.
  되돌리기 사유는 200자 이하 문자열이고 비밀값 규칙(`domain/secret_rules.find_secrets`)에 걸리면 거부한다. 사람 이름을 담지 말라는 안내는 명령 도움말과 운영 문서에 둔다(검사할 수 없다).
- **Rationale**: 되돌리기 대상 판정(FR-023 "전환 기록에 활성 이력")과 Jira 증빙(US6)이 같은 기록을 본다. 첫 활성화 이력이 없으면 지금 활성 버전을 나중에 되돌리기 대상으로 쓸 수 없다.
- **Alternatives considered**: `qk.index_version`에 마지막 전환 열만 두기(이력과 게이트 지문을 남길 수 없다), 파일 기록(운영 DB 상태와 원자적으로 남길 수 없다).

## R-08 활성화·되돌리기·정리의 잠금과 트랜잭션 (FR-003, SC-004)

- **Decision**: 세 명령은 동기화가 공유로 잡는 세션 advisory lock `qk-sync-index`를 배타로 잡는다(지금 첫 활성화와 같은 키, `sync_store.py`). 잡지 못하면 `sync_running`이다.
  잠금을 든 채 한 트랜잭션에서 조건을 다시 계산하고, 모두 채우면 이전 활성 버전을 `archived`로 바꾼 뒤 대상을 `active`로 바꾸고 전환 기록을 쓴다.
  `index_version_one_active` 유일 색인 때문에 순서는 보관 먼저다. 읽는 쪽은 MVCC로 커밋 전 상태(이전 활성) 아니면 커밋 뒤 상태(새 활성)만 본다.
- **검색 쪽**: 검색 함수는 호출마다 `qk.active_index_version()`을 한 번 읽고, 검색 하나가 여러 함수를 부르는 사이에 버전이 바뀌면 `retrieval/service.py`가 `index_version_changed`로 실패한다
  (spec Edge Cases). 코드는 바꾸지 않는다. SC-004 시험은 로컬 DB에서 검색 스레드가 `retrieve`를 반복하는 동안 활성화·되돌리기를 번갈아 돌리고, 결과마다 청크의 인덱스 버전이 하나인지,
  "활성 버전 없음"이 0건인지 세며 `index_version_changed` 수를 결과에 남긴다.
- **Rationale**: 조건 확인과 전환 사이에 동기화·재색인이 끼면 덮음이나 벡터 조건이 깨질 수 있다. 동기화가 이미 공유 잠금을 쓰므로 새 잠금 체계가 필요 없다.
- **Alternatives considered**: 행 잠금만(`SELECT … FOR UPDATE`, 문서 처리 트랜잭션은 버전 행을 잠그지 않아 막지 못한다), 직렬화 격리(재시도 처리가 늘고 잠금 키 체계와 겹친다).

## R-09 게이트 정책 파일과 "병합된 최신 정책" 확인 (FR-012, FR-015 (8), FR-021 (6), D4)

- **Decision**: 정책은 TOML 파일 `eval/gate_policies/<정책 ID>/v<버전>.toml`이다(질문 세트와 같은 배치, QK-EVL-001 R-02). 형식은 [contracts/gate-policy.md](contracts/gate-policy.md).
  정책 지문은 파일 바이트의 SHA-256이다. "정책 병합 커밋"은 `origin/main`의 첫 부모 이력에서 그 파일을 처음 더한 커밋이다
  (`git log --first-parent --diff-merges=first-parent --diff-filter=A --no-patch --format=%H origin/main -- <경로>`의 가장 오래된 것).
  - 판정(FR-015 (8)): 병합 커밋이 없으면 `policy_unmerged`, 실행 기록 `code_commit.sha`가 `null`이면 `code_commit_unknown`, 병합 커밋을 조상으로 갖지 않으면(`git merge-base --is-ancestor`)
    `code_before_policy`, `dirty = true`면 `dirty_code`다. 정책 파일 내용이 `origin/main`의 그 경로 내용과 다르면 `policy_changed`다.
    게이트 명령은 `--main-ref`(기본 `origin/main`)를 받고 그 값을 게이트 기록 `policy.main_ref`에 남긴다. 판정한 코드의 `judge_commit`(커밋·`dirty`)은 기록만 하고 판정에 쓰지 않는다.
    판정 코드가 무엇이든 활성화가 자기 코드로 다시 판정하기 때문이다(R-11).
  - 활성화(FR-021 (6)): 참조를 받지 않고 언제나 `origin/main`으로 같은 확인을 다시 하고, `origin/main`에 같은 정책 ID의 더 높은 버전 파일이 있으면 `gate_policy`로 거부한다.
  git 읽기는 새 경계 `ports/history.py`(`RepoHistory`)로 받고 구현은 `adapters/git_history.py`가 `git` 명령을 부른다. `origin/main`을 최신으로 받는 것(`git fetch`)은 운영 절차가 한다.
- **Rationale**: 작성자가 자기 브랜치에 느슨한 정책을 더해 바로 판정·활성화하는 일을 막는다(D4). 이 저장소의 `main`은 PR마다 병합 커밋(부모 둘)을 남긴다.
  첫 부모 이력에서 병합 커밋의 변경을 첫 부모와 비교하면 그 파일을 처음 들여온 병합 커밋이 나온다(2026-11-05 확인: `eval/question_sets/qk-evl-001-golden/v2.toml` → `6685b88`).
  고정 뒤 내용 변경은 금지라(FR-012) 내용 비교로 막는다.
- **Alternatives considered**: 정책에 병합 커밋을 손으로 적기(병합 뒤에야 알 수 있어 다시 고쳐야 한다), GitHub API로 PR 병합 확인(외부 호출, 기본 검증에서 시험할 수 없다).

## R-10 게이트 판정 규칙 (FR-015~FR-017, SC-003)

- **Decision**: 판정은 `gate/judge.py`의 순수 함수다. 입력은 정책, 실행 기록(`evaluation/records.read_record`로 읽은 `RunRecord`), 기준·후보 대상 이름과 기대 인덱스 버전 ID, 저장소 이력 확인 결과다.
  1. 판정 불가 검사(FR-015)를 모두 돌려 사유를 모은다. 하나라도 있으면 지표를 계산하지 않고 `undecidable`이다. 사유 이름은 [contracts/gate-record.md](contracts/gate-record.md) 4절.
  2. 세트마다 판정 질문을 고른다(FR-016). 지표 대상(`metric_target`) 질문 가운데 기준 대상·판정 방식 결과가 `ok`·`no_results`이고 `omitted`가 비어 있는 질문이다.
     나머지는 판정에서 빼고 질문 ID와 사유(`baseline_skipped`·`baseline_failed:<상태>`·`baseline_omitted`)를 남긴다.
  3. 후보의 같은 질문 결과가 정상(`ok`·`no_results`이고 생략 없음)이 아니면 첫 근거 순위를 없음으로 본다(Recall@5 0, 역순위 0).
  4. Recall@5·MRR은 `evaluation/metrics.py`와 같은 정의(`Fraction`, 순위 ≤ 5, 역순위는 순위 ≤ `MRR_CUTOFF`)로 판정 질문 집합에서 계산한다. 차이 = 후보 − 기준.
  5. 통과는 세트마다 주 지표 차이 ≥ −(허용 하락)이고 정책이 고른 가드레일을 모두 채울 때다(FR-017).
     G1 = 기준 정상·후보 비정상인 판정 질문 수 ≤ 허용 수, G2 = 식별자 세트 Precision@5(정책이 정한 방식) 하락 ≤ 허용 값, G3 = 키워드 전용 상한 도달 비율 증가 ≤ 허용 값.
     G2·G3도 판정 질문 집합으로 계산한다. 가드레일 방식이 판정 방식과 다르면 그 방식에서 2단계 규칙으로 판정 질문을 다시 고른다(가드레일 판정 질문).
     정의는 QK-EVL-001과 같다. Precision@5 = 상위 5건 근거 항목 수 ÷ 5의 평균, 상한 도달 = `result_count ≥ conditions.candidates`인 질문 비율.
     후보 결과가 비정상이면 그 질문을 후보에게 가장 나쁜 값으로 센다. Precision@5는 0, 상한 도달은 도달로 센다(주 지표가 실패를 놓침으로 세는 것과 같은 방향, FR-016). 분모는 기준·후보 모두 가드레일 판정 질문 수다.
     가드레일 판정 질문이 0개면 그 가드레일은 계산할 수 없어 판정 불가 `too_few_judged`다(정책 `min_judged`는 판정 방식에만 걸린다).
     그래서 후보가 근거를 잃은 질문이 후보 쪽 분모에서만 빠지는 일이 없다(D3). 정책이 고른 방식이 기록에 없으면 판정 불가 `mode_missing`이다.
     한 세트에 맞는 실행 기록이 둘 이상이면(같은 세트 ID·버전, 기준·후보 대상이 모두 있음) 판정 불가 `set_duplicate`다.
  6. 회귀 질문 = 기준 첫 근거 순위 ≤ 5이고 후보는 아님, 개선 질문 = 그 반대(판정 방식, 판정 질문 집합).
  비교는 모두 `Fraction`이고 정책의 허용 값은 소수 문자열을 `Fraction`으로 읽는다(부동소수 반올림 차이 없음).
- **Rationale**: QK-EVL-001 `metric_set`은 `skipped`를 분모에서 빼는데(QK-EVL-001 R-09) 게이트는 후보 쪽 근거 미색인을 놓침으로 세야 해(FR-016) 같은 함수를 그대로 쓸 수 없다.
  정의 상수(`OK_STATUSES`, `MRR_CUTOFF`)를 가져와 쓰면 정의가 갈라지지 않는다.
- **Alternatives considered**: QK-EVL-001 공통 질문 집합 재사용(후보가 근거를 잃은 질문이 빠져 통과한다, D3).

## R-11 게이트 기록 파일 (FR-018, FR-019, SC-007)

- **Decision**: 게이트 기록은 JSON 파일 하나다(스키마 `qk-sto-002-gate/v1`, UTF-8, 키 정렬, 들여쓰기 2칸). 기록 ID는 `gate-<YYYYMMDDTHHMMSSZ>-<16진수 8자>`다.
  경로는 `--out`으로 받고 권장 위치는 `eval/gate_records/<기록 ID>.json`이다. 이미 있으면 쓰지 않는다. 임시 이름에 쓴 뒤 이름을 바꾼다(QK-EVL-001 실행 기록과 같은 규칙).
  입력 실행 기록은 저장소 상대 경로와 파일 SHA-256으로 남기고, 게이트 기록 자체의 지문은 파일 바이트의 SHA-256이다. 판정 불가도 기록을 쓴다(목표 미달·판정 불가도 남긴다, C-13).
  형식은 [contracts/gate-record.md](contracts/gate-record.md).
- **활성화의 확인**: 활성화는 게이트 기록을 읽어 (a) 입력 실행 기록 파일 지문, (b) 정책 파일 지문과 R-09 확인, (c) 같은 입력으로 다시 판정한 결과(판정·세트별 지표·가드레일·위반)가 기록과 같은지 본다.
  다시 판정의 입력: 정책 파일과 실행 기록 파일은 기록의 경로에서 읽고 지문이 맞는 것만 쓴다. 기준·후보 대상 이름은 기록의 `baseline.target`·`candidate.target`,
  기대 인덱스 버전은 기록 값이 아니라 활성화가 정한 값(기준 = 지금 운영 활성 버전, 후보 = 활성화 대상)이다. 그래서 기준이 바뀐 뒤의 기록은 (c)에서도 판정 불가가 되어 거부된다.
  다시 판정은 순수 계산이라 DB와 외부 호출이 없다. 손으로 고친 기록은 (c)에서 거부된다.
- **판정 불가의 기록 내용**: 판정 불가여도 계산할 수 있는 세트의 판정 질문 수는 `judged_counts`에 남긴다(`too_few_judged`의 원인을 보이기 위해).
- **Alternatives considered**: 게이트 기록을 운영 DB에 저장(D4 "저장소 파일로 두고 PR로 리뷰"와 맞지 않는다), 기록 지문만 확인(판정 필드를 고친 뒤 지문을 다시 계산하면 통과한다).

## R-12 토크나이저 (FR-021 (8), FR-033, D6)

- **Decision**: 이 브랜치는 토크나이저를 바꾸는 경로를 만들지 않는다. ADR-010은 Proposed이고 후보 A 유지를 권고한다(2026-11-04). A·B로 정해지면 토크나이저는 지금 값
  (`TokenBigramSplitSymbol`, `0001_initial_schema.sql`)으로 고정이다. 활성화는 운영 키워드 색인(`chunk_search_text_pgroonga`)의 `reloptions`에서 토크나이저를 읽어
  게이트 기록의 후보 토크나이저와 다르면 `tokenizer_mismatch`로 거부한다(읽는 방법은 `adapters/postgres/eval_target.py`의 `_tokenizer`와 같다).
  ADR-010이 C를 고르면 후보 토크나이저가 운영 값과 달라 이 조건이 활성화를 막는다. 그때 D6 선택지를 사람이 정하고 별도 작업으로 구현한다.
- **Rationale**: 토크나이저 변경 경로 없이도 "게이트가 판정한 키워드 동작과 활성화 뒤 동작이 같다"를 확인할 수 있다. 잘못된 쪽(다른 토크나이저로 판정한 게이트로 활성화)은 거부된다.
- **Alternatives considered**: D6 (a)를 지금 구현(ADR-010이 C를 고르지 않으면 필요 없는 저장 구조 변경이 가장 크다, spec D6).

## R-13 기준·후보 평가 대상 준비 (FR-013, FR-014, D1)

- **Decision**: 평가 대상은 지금 명령 `qk-dev eval-index prepare`로 만들고 코드를 바꾸지 않는다. 지금 계약으로 만들 수 있는 조합은 후보 A·B·C이고 이름이 (규칙, 커밋)으로 정해져
  기준과 후보의 규칙이 다르면 함께 만들 수 있다(예: ADR-010 B 반영은 기준 `iv-4c0bc4fcc642` = A, 후보 `iv-8b7e93b22051` = B).
  "기준 평가 대상을 활성 버전을 만든 코드 커밋으로 만든다"(FR-014)는 운영 절차다. 활성 버전을 만든 커밋을 `git worktree`로 꺼내 그 안에서 `eval-index prepare`를 돌린다(quickstart 3절).
  만든 대상의 인덱스 버전 ID는 실행 기록 `targets[].index_version`에 남고 게이트가 기대값과 비교한다(FR-015 (3)).
  규칙이 같은 기준·후보(청킹 변경, 코드 청킹·Confluence 켜짐, 모델 교체)는 이름이 겹치거나 실행기가 거부한다. 그 확장은 QK-EVL-001·QK-RET-001 쪽 변경이다(spec "의존과 넘김").
- **Rationale**: 평가 계약을 바꾸지 않는다(FR-013). 게이트는 실행 기록만 읽으므로 대상이 어떤 코드로 만들어졌는지는 인덱스 버전 ID 비교로 충분하다.
- **Alternatives considered**: 평가 대상 이름 규칙 확장(QK-EVL-001 계약 변경, 사람 승인 필요. 첫 사용 사례 B에는 필요 없다).

## R-14 비용 추정 (FR-034, AGENTS.md 3.5)

- **Decision**: 이 브랜치의 기본 검증은 0 Neurons다(가짜 임베딩 제공자, FR-035). US6에서 쓸 추정은 다음과 같고 실행 전에 미리 보기로 실제 값을 다시 본다.
  - ADR-010 B 반영(청킹 규칙 버전만 바뀌고 임베딩 입력은 같음): 재색인 약 0 Neurons(H02에서 B 평가 대상을 A의 캐시로 0 Neurons에 준비했다, QK-EVL-001 TASK 2026-11-04 사실),
    평가 대상 준비 0(캐시 복사), 질의 임베딩은 골든 v2·식별자 v1 미리 보기 기준 약 2.3 + 2.4 Neurons(실제 1.04). 합계 5 Neurons 아래.
  - 임베딩 입력이 바뀌는 청킹 변경: 운영 청크 약 1,300개 전체 재임베딩, 약 900 Neurons(QK-EVL-001 TASK "후보당 약 900 Neurons"). 평가 대상 준비가 같은 규모로 한 번 더 든다.
  - 임베딩 모델 교체: 캐시를 못 써 위와 같은 규모가 재색인·기준·후보 대상에 각각 든다(평가 대상 계약 확장 뒤).
  같은 날 합치면 운영 장부 잔여량(일 10,000 Neurons)과 대조하고, 넘을 것 같으면 날을 나눈다(FR-034). 합계 보고는 quickstart 3절 표를 쓴다.
- **Rationale**: 평가 대상 사용량은 평가 대상 DB 장부에만 남아 운영 장부에 보이지 않는다(spec Edge Cases).

## R-15 코드 위치와 경계 (C-06)

- **Decision**:
  - 버전 수명 판단(활성화·되돌리기·정리 조건, 덮음 요약, 상태 보기 조립): 새 모듈 `sync/versions.py`. 입력은 저장소가 돌려준 스냅샷 값이고 순수 함수다.
  - 저장 경계: 새 Protocol `ports/index_versions.py`(`IndexVersionStore`)와 구현 `adapters/postgres/index_versions.py`(`PostgresIndexVersionStore`). `SyncStore`에는 `prepare_candidate`와
    재색인 표시만 더한다. 첫 활성화의 전환 기록은 `PostgresSyncStore.activate` 안에서 쓴다.
  - 게이트: 새 패키지 `gate/`(`policy.py`, `judge.py`, `record.py`, `verify.py`). 표준 라이브러리와 `evaluation`·`domain`·`ports`만 가져온다.
  - 저장소 이력: `ports/history.py`(`RepoHistory`), `adapters/git_history.py`.
  - 명령: `qk-index run --reindex`(`indexer/sync_cli.py`), `qk-index index status|activate|rollback|prune`(새 파일 `indexer/index_cli.py`로 옮기고 `query_command`는 `runs`만 맡는다),
    기존 주입점 `sync_store_factory`는 그대로 둔다. 버전 저장소는 동기화 저장소 객체가 내준다(`PostgresSyncStore.index_versions()`가 같은 접속 정보로 `PostgresIndexVersionStore`를 연다).
    명령은 `getattr(store, "index_versions", None)`으로 찾고(지금 `load_sources`를 찾는 방식과 같다), 없으면 지금 키와 지금 첫 활성화만 낸다.
    `index status`의 새 키(`versions`, `coverage`, `mismatch_since`, `resolutions`)와 `rollback`·`prune`·활성 버전이 있을 때의 `activate`는 버전 저장소에서 온다.
    버전 저장소가 없는 대역으로 `rollback`·`prune`이나 활성 버전이 있을 때의 `activate --gate`를 부르면 종료 2 `store_unavailable`이다.
    기존 시험 파일(`tests/unit/indexer/test_run_cli.py`, `test_code_sync_cli.py` 등)과 그 가짜 저장소는 고치지 않는다,
    `qk-dev eval gate`(새 파일 `devtools/gate_cli.py`, `devtools/db.py`의 `eval` 묶음에 등록).
  - `tests/unit/test_boundaries.py`에 `gate/`와 `sync/versions.py`가 `adapters`를 가져오지 않는 규칙을 더한다.
- **Rationale**: 게이트 판정은 DB 없이(FR-019) 평가 기록만 읽으므로 평가 도구(`qk-dev`)에 둔다. 활성화는 운영 저장소를 바꾸므로 운영 명령(`qk-index`)에 두고 원격 확인 옵션 규칙을 따른다.
  `sync_store.py`(405줄)에 활성화·되돌리기·정리까지 넣으면 동기화 경계가 너무 넓어진다.
- **Alternatives considered**: 게이트 판정을 `qk-index`에 두기(평가 실행 기록과 질문 세트 도구가 `qk-dev`에 있어 흩어진다), `evaluation/`에 게이트 넣기(QK-EVL-001 패키지 범위가 넓어지고 계약 변경처럼 보인다).

## R-16 정리의 삭제 방식 (FR-027, FR-028, SC-005)

- **Decision**: 정리는 R-08 잠금을 든 채 대상 버전 청크를 1,000행씩 별도 트랜잭션으로 지운다. 남은 청크가 0이 되면 마지막 트랜잭션에서
  (1) 모든 자료 행의 `purge_pending`에서 그 버전을 빼고, 비게 된 행은 `purge_reason`도 NULL로 바꾼다(제약 `artifact_purge_reason_matches_pending`, `sync_store.py`의 기존 패턴과 같다).
  (2) 버전을 `archived` + `pruned_at = now()`로 바꾸고 (3) 전환 기록 `prune`(이번 실행에서 지운 청크 수)을 남긴다. 중단되면 다시 실행해 남은 청크만 지운다.
  지운 청크 수는 실행마다 세고, 이어서 끝낸 실행의 전환 기록에는 그 실행이 지운 수만 남는다(앞 실행 수는 출력으로만 남는다).
  임베딩 행은 지우지 않는다(QK-SYN-003). 확인 옵션 없이는 지울 청크 수만 보인다.
- **Rationale**: 버전 하나가 청크 수천 개라 한 트랜잭션으로 지우면 키워드 색인 갱신이 길어진다. 묶음마다 커밋하면 중단해도 부분 반영이 일관된다(지운 만큼만 지워짐). 잠금이 있어 재색인이 같은 버전에 쓰지 못한다.
- **Alternatives considered**: 한 번에 `DELETE`(중단 시 전부 되돌아가고 긴 잠금), `ON DELETE CASCADE`로 버전 행 삭제(전환 기록·활성 이력이 사라진다, FR-027 "버전 행과 전환 기록은 남기고").

## R-17 상태 보기 값 (FR-026)

- **Decision**: `qk-index index status`는 읽기 전용 트랜잭션에서 다음을 낸다. 활성 버전, 현재 설정 버전, 일치 여부, 불일치 시작 시각(지금 활성 버전의 마지막 활성 전환 시각 뒤에
  현재 설정 버전으로 기록된 실행 가운데 가장 이른 시작 시각, 없으면 `null`), 버전마다 상태·재료·문서 수·청크 수·정리 여부·마지막 재색인 결과(실행 ID·상태·종료 시각)·활성 이력·정리 대상 여부,
  현재 설정 버전의 덮음(R-04)과 처리 실패 문서 목록(위치·단계), 불일치면 해소 방법 두 가지. 지금 출력 키(`active`, `ready`, `current`, `matches`)는 그대로 두고 키를 더한다(FR-036).
- **Rationale**: 불일치 시작을 따로 저장하지 않아도 실행 기록과 전환 기록으로 계산된다. 지금 키를 유지하면 기존 시험 기대값이 바뀌지 않는다.

## R-18 마이그레이션 `0009_index_versions.sql`

- **Decision**: 더하기 위주의 마이그레이션 하나다. (1) R-01의 청크 출처 열과 기존 행 채우기, `qk.hit_json` 교체(같은 시그니처, `coalesce`). (2) `qk.index_version.pruned_at`과 검사 제약
  (`pruned_at IS NULL OR status = 'archived'`). (3) `qk.sync_run.kind`(`sync`·`reindex`, 기본 `sync`). (4) `qk.artifact.processed_outcome` 검사 제약에 `not_target` 추가(제약을 지우고 다시 만든다).
  (5) `qk.index_transition` 표와 첫 활성화 채우기(R-07). 질의 역할(`qk_query`)은 표 단위 `SELECT` 권한이라 새 열도 읽을 수 있고 새 표 권한은 주지 않는다(질의 경로가 읽지 않는다).
  운영 적용은 US6 단계에서 `qk-migrate --dry-run` → 적용 → 다시 실행해 `applied=0`(운영 문서 2절 절차)로 하고, 이 브랜치는 로컬 DB에만 적용한다.
- **배포 순서**: 0009를 먼저 적용하고 그 뒤 코드를 갱신한다(QK-OBS-001 운영 문서 7.7의 0008과 같은 순서). 반대로 가면 새 코드의 청크 쓰기와 실행 기록 `kind` 쓰기가 실패해
  서버 예약 동기화가 멈춘다. 이를 막으려고 새 코드의 Postgres 어댑터가 확인한다. 확인은 `qk.schema_migration`에 `version >= 9`인 성공 행이 있는지다(뒤 마이그레이션이 생겨도 그대로 쓴다).
  - `PostgresSyncStore`: 첫 쓰기(`begin_run`, `activate`) 전에 확인하고 없으면 `SchemaOutdated`(`StoreError` 하위)를 낸다. CLI는 이를 `schema_outdated`(종료 1)로 보인다.
  - `PostgresIndexVersionStore`: 연결 직후 확인한다. 읽기 명령 `index status`도 새 표·열을 읽으므로 0009가 없으면 `store_unavailable`이 아니라 `schema_outdated`(종료 1)다.
  - QK-STO-001 `PostgresStore.replace_chunks`: 확인을 더하지 않는다. 부르는 곳이 `devtools/bench.py`와 시험뿐이고 로컬 DB는 언제나 전체 마이그레이션을 적용한다. 0009 없는 DB에서는 SQL 오류(`InvalidRecord`/`StoreError`)로 실패한다고 운영 문서에 적는다.
  확인은 어댑터 안에서만 하고 CLI·흐름 코드는 메서드를 새로 부르지 않는다. 그래서 기존 CLI 단위 시험의 가짜 저장소는 바뀌지 않는다(R-15, FR-036). 운영 문서에 순서를 적는다.
- **Rationale**: 기존 마이그레이션 파일은 고치지 않는다. 검사 제약 교체와 함수 교체 말고는 지우는 변경이 없다.
