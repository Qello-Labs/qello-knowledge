# Data Model: QK-SYN-001 증분 동기화

**명세**: [spec.md](spec.md) · **결정 근거**: [research.md](research.md)

1절은 저장 스키마 추가분(마이그레이션 `0004_sync.sql`), 2절은 `domain/sync.py`의 도메인 타입, 3절은 상태 전이다. 도메인 타입은 표준 라이브러리와
`qello_knowledge.domain`만 가져온다(`tests/unit/test_boundaries.py` 규칙).

## 1. 저장 스키마 추가분

### 1.1 `qk.artifact` 추가 열 (research R-02)

| 열 | 타입 | 제약 | 뜻 |
| --- | --- | --- | --- |
| `source_name` | text | NULL 허용 | 문서를 저장한 자료원 이름(spec FR-016 (5)) |
| `chunk_input_hash` | text | NULL 허용 | 청킹 입력 지문(research R-03) |
| `processed_chunking_version` | text | NULL 허용 | 마지막 성공 처리의 청킹 규칙 버전 |
| `processed_index_version` | text | NULL 허용, `qk.index_version(id)` 참조 | 마지막 성공 처리의 인덱스 버전 |
| `processed_outcome` | text | `chunked`·`empty`·NULL | 마지막 성공 처리 결과 |
| `last_seen_version` | text | NULL 허용 | 마지막으로 확인한 원본 버전(spec FR-010) |
| `last_seen_at` | timestamptz | NULL 허용 | 마지막으로 확인한 시각 |
| `takedown_reason` | text | 아래 값·NULL | 내림 사유. NULL이면 내려지지 않음 |
| `takedown_at` | timestamptz | NULL 허용 | 내린 시각 |
| `purge_pending` | text[] | NOT NULL DEFAULT `'{}'` | 보안 대상 본문이 남은 인덱스 버전 목록(spec FR-015·FR-017) |
| `purge_reason` | text | 보안 사유 값·NULL | 삭제 대기를 만든 보안 사유. 대기 목록이 빌 때 비운다 |

- `takedown_reason` 값: 보안 내림 `security_path`(보안 필터 경로 제외), `security_secret`, `security_access`, `config_excluded`(설정 제외 패턴),
  일반 내림 `source_missing`(완전한 목록에 없음), `not_target`(대상 아님), `source_disabled`. 검사 제약으로 고정한다.
- 불변식(검색 제외): `takedown_reason IS NOT NULL` ⇔ `status = 'deleted'`(동기화가 쓴 행).
- 불변식(삭제 대기, 검색 제외와 따로): `purge_pending <> '{}'` ⇔ `purge_reason IS NOT NULL`이고, `purge_reason`은 보안 사유다. 상태는 `deleted`일 수도 `active`일 수도 있다.
  `active`이면 다시 처리돼 현재 버전에서 검색되고, 대기 목록에는 현재 버전이 없다(`processed_index_version`이 목록에 없음).
  삭제를 보류한 보안 내림이라도 남은 청크가 없으면(빈 문서, 이미 지운 문서) 목록과 사유를 모두 비운다(Codex plan 2차 지적 N7).
- 기존 열의 쓰임: `source_url`·`source_version`은 처리한 원본의 링크·버전, `content_hash`는 처리한 본문 해시, `collected_at`은 처리한 시각,
  `access_scope`는 `team`·`restricted`·NULL(미확인). 도메인 값 `AccessScope.TEAM`·`RESTRICTED`·`UNKNOWN`과의 대응은 어댑터가 한다(`qk.visible_access_scope()`가 `'team'`).

### 1.2 `qk.sync_source` (spec FR-002, research R-10)

| 열 | 타입 | 제약 |
| --- | --- | --- |
| `source_name` | text | 기본 키 |
| `source_kind` | text | NOT NULL, 유일(종류마다 자료원 하나, spec FR-002) |
| `scope_key` | text | NOT NULL |
| `origin_id` | text | NULL 허용(첫 성공 수집 전) |
| `origin_name` | text | NULL 허용 |
| `registered_at` | timestamptz | NOT NULL DEFAULT now() |
| `updated_at` | timestamptz | NOT NULL DEFAULT now() |

실행 기록 정리(`runs prune`)가 지우지 않는다. 행은 그 자료원의 첫 문서 쓰기 직전에 만든다.

### 1.3 `qk.sync_run`, `qk.sync_run_source` (spec FR-026·FR-027)

`qk.sync_run`

| 열 | 타입 | 제약 |
| --- | --- | --- |
| `run_id` | text | 기본 키(`sync-<UTC 시각>-<무작위 8자>`) |
| `trigger` | text | `manual`·`schedule` |
| `target` | text | `local`·`remote` |
| `started_at`, `finished_at` | timestamptz | `finished_at` NULL 허용 |
| `rules_version`, `chunking_version`, `index_version` | text | NOT NULL |
| `status` | text | `running`·`succeeded`·`partial`·`stopped`·`unfinished` |
| `summary` | jsonb | NOT NULL DEFAULT `'{}'` |

`qk.sync_run_source`

| 열 | 타입 | 제약 |
| --- | --- | --- |
| `run_id` | text | `qk.sync_run` 참조, ON DELETE CASCADE |
| `source_name` | text | 기본 키 `(run_id, source_name)` |
| `status` | text | `qk.sync_run.status`와 같은 값 |
| `origin_version` | text | 확정한 원본 버전(커밋). NULL 허용 |
| `listing_complete` | boolean | NULL 허용 |
| `stop_reason` | text | QK-ING-001 `StopReason`. NULL 허용 |
| `holds` | text[] | 2.4 `HoldReason` 목록. NOT NULL DEFAULT `'{}'` |
| `retry_at` | timestamptz | NULL 허용 |
| `summary` | jsonb | 단계별 요약(수집·필터·청킹·임베딩·내림 비율, 2.6) |

### 1.4 `qk.sync_document_result` (spec FR-026·FR-028)

| 열 | 타입 | 제약 |
| --- | --- | --- |
| `run_id` | text | `qk.sync_run` 참조, ON DELETE CASCADE |
| `doc_key` | text | research R-12 |
| `action` | text | 2.5 `action` 값. 기본 키 `(run_id, doc_key, action)` |
| `source_name` | text | NOT NULL |
| `doc_display` | text | NOT NULL. 기록 출력 규칙을 거친 표시값 |
| `artifact_id` | bigint | NULL 허용 |
| `outcome` | text | 2.3 `DocumentOutcome` 값 |
| `change_reason` | text | 2.2 `ChangeReason` 값·NULL |
| `stage` | text | `fetch`·`screen`·`chunk`·`embed`·`store`·NULL |
| `failure` | text | 정해진 실패 유형·NULL |
| `takedown_reason` | text | 1.1 값·NULL |
| `rule` | text | 보안 규칙 이름(보안 내림일 때)·NULL |
| `lines` | int[] | 비밀값 줄 번호·NULL |

`(source_name, doc_key, outcome)`로 실패 목록을 조회하는 인덱스를 둔다(QK-SYN-002). 원문, 원본 식별자 원값, 원본 링크 열은 없다. 한 실행에서 한 문서의 작업은
`PURGE` 뒤 `PROCESS`·`UNCHANGED`·`TAKE_DOWN` 중 하나처럼 둘까지 생길 수 있어 작업마다 행 하나다.

## 2. 도메인 타입 (`domain/sync.py`)

### 2.1 `SourceOrigin` (QK-ING-001 공통 형식 추가, `domain/source.py`)

`origin_id: str`, `origin_name: str`, `version: str | None`(확정한 원본 버전). 앞의 둘은 비어 있지 않아야 한다. `ListPage.origin`, `Listing.origin`에 `SourceOrigin | None = None`으로 더한다(research R-10).

### 2.2 `ChangeReason` (spec FR-008, research R-03)

`NEW`, `INPUT_CHANGED`, `CHUNKING_CHANGED`, `REINSTATED`, `INDEX_CHANGED`. 판정 순서는 이 순서이고 첫 값만 남긴다.

### 2.3 `DocumentOutcome`

| 값 | 뜻 | 저장 상태 변화 |
| --- | --- | --- |
| `PROCESSED` | 바뀐 문서를 처리해 반영(청크 있음) | 갱신 |
| `PROCESSED_EMPTY` | 바뀐 문서가 빈 문서라 청크 0개로 반영 | 갱신 |
| `UNCHANGED` | 변경 없음 | `last_seen_*`만 |
| `TAKEN_DOWN` | 내림(사유는 `takedown_reason`) | `status`, 사유, (보안) 청크 삭제 또는 대기 |
| `PURGED` | 삭제 대기 본문을 지움 | `purge_pending` 비움 |
| `FAILED` | 처리 실패(단계·유형) | 없음 |
| `HELD` | 보류(예산 초과, 인덱스 버전 불일치, 비율 초과, 정체성 불일치) | 없음 |
| `SKIPPED` | 수집 중단으로 본문을 받지 못함 | 없음 |

### 2.4 `HoldReason`

`BUDGET_EXCEEDED`(실행 전 판정), `BUDGET_EXHAUSTED`(실행 중 소진, research R-17), `INDEX_MISMATCH`, `TAKEDOWN_RATIO`, `ORIGIN_MISMATCH`, `ORIGIN_MISSING`,
`COLLECTION_INCOMPLETE`(목록 불완전 또는 수집 중단). 보류별로 막는 작업은 아래 허용표 하나로 정하고, 미리 보기와 실제 실행이 같은 표를 쓴다(Codex plan 2차 지적 N6).

| 보류 \ 작업 | 처리(`PROCESS`) | 보안 내림 검색 제외 | 보안 내림 본문 삭제 | 일반 내림 `source_missing` | 일반 내림 `not_target`·`source_disabled` | 대기 본문 지우기 | `mark_seen` |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `BUDGET_EXCEEDED` | 막음 | 함 | 함(비율 안) | 함 | 함 | 함(확인 옵션) | 함 |
| `BUDGET_EXHAUSTED` | 캐시 완비 문서만 | 함 | 함(비율 안) | 함 | 함 | 함(확인 옵션) | 함 |
| `INDEX_MISMATCH` | 막음 | 함 | 함(비율 안) | 막음 | 막음 | 함(확인 옵션) | 함 |
| `TAKEDOWN_RATIO` | 함 | 함 | 대기로 남김 | 막음 | 막음 | 확인 옵션이 있을 때만(그때는 보류 아님) | 함 |
| `ORIGIN_MISMATCH`·`ORIGIN_MISSING` | 막음 | 함 | 함(비율 안) | 막음 | 막음 | 막음 | 막음 |
| `COLLECTION_INCOMPLETE` | 받은 문서만 | 함 | 함(비율 안) | 막음 | 함 | 함(확인 옵션) | 받은 문서만 |

보안 내림의 검색 제외는 어떤 보류에도 막히지 않는다(spec FR-004). 여러 보류가 함께 있으면 어느 하나라도 막는 작업은 막는다. `TAKEDOWN_ONLY` 대상은 `source_disabled` 일반 내림과
대기 본문 지우기만 한다. 정체성 불일치(`ORIGIN_*`)에서 `mark_seen`을 막는 이유는 다른 원본의 버전을 확인 버전으로 남기지 않기 위해서다. `INDEX_MISMATCH`에서 일반 내림을
막는 것은 spec SC-011(버전 불일치 실행의 일반 내림 0건)을 따른 것이다(Codex plan 3차 지적 M1).

### 2.5 `DocumentDecision`

문서 하나에 대한 판단. `plan_source()`가 만들고 쓰기 단계가 그대로 반영한다(research R-07).

| 필드 | 타입 | 비고 |
| --- | --- | --- |
| `doc_key` | str | research R-12 |
| `display` | str | 출력 규칙 적용 값 |
| `artifact_id` | int \| None | 저장된 행이 있으면 |
| `actions` | `PURGE`와, `PROCESS`·`UNCHANGED`·`TAKE_DOWN`·`FAIL`·`HOLD`·`SKIP` 중 하나 | 쓰기 순서대로. `PURGE`는 확인 옵션이 있을 때만 |
| `change_reason` | ChangeReason \| None | `PROCESS`일 때 |
| `takedown_reason` | str \| None | `TAKE_DOWN`일 때 |
| `delete_bodies` | bool | 보안 내림에서 삭제 허용이면 참, 보류면 거짓 |
| `chunked` | ChunkedContent \| None | `PROCESS`일 때 QK-CHK-002 결과(`repr=False`) |
| `stage`, `failure` | str \| None | `FAIL`일 때 |

### 2.6 `SourcePlan`

자료원 하나의 판단 묶음. `source_name`, `mode`(`FULL`·`TAKEDOWN_ONLY`: 설정에서 빠지거나 꺼진 자료원), `origin_version`, `listing_complete`, `stop`(QK-ING-001 `StopInfo`),
`fetch_summary`(QK-ING-001 `FetchResult.to_dict()`에서 항목 목록을 뺀 값), `origin`(SourceOrigin \| None), `origin_check`(`OK`·`REGISTER`·`MISMATCH`·`MISSING`),
`decisions: tuple[DocumentDecision, ...]`, `takedown_ratio`(일반·본문 삭제 각각의 대상 수와 기준 수), `holds: frozenset[HoldReason]`, `filter_summary`(QK-SEC-001),
`chunking_summary`(QK-CHK-002). 불변식: `holds`에 `ORIGIN_*`나 `INDEX_MISMATCH`가 있거나 `mode=TAKEDOWN_ONLY`면 `PROCESS` 결정이 없다.
보류가 막는 작업(2.4 허용표)의 결정은 없다. `BUDGET_EXCEEDED`·`BUDGET_EXHAUSTED`는 실행 전체 판정(research R-17)이라 실행 단계에서 붙는다. `TAKEDOWN_RATIO`가 있으면 일반 사유 `TAKE_DOWN`이 없고
보안 `TAKE_DOWN`은 모두 `delete_bodies=False`다.

### 2.7 `SyncPreview` (spec FR-022)

자료원별 `SourcePlan` 요약(행동별 문서 수, 내림 사유별 수, 보류 사유)과 `EmbedPreview`(QK-EMB-001, 모든 자료원의 처리 대상 문서를 합친 한 번의 계산), 인덱스 버전 상태(활성·현재 설정·일치 여부),
실행 가능 여부, 미리 본 판단 옵션(`confirm_takedown`, `allow_partial_budget`).
저장소 쓰기·외부 임베딩 호출이 없다.

### 2.8 `SyncRunResult`

`run_id`, `status`(`succeeded`·`partial`·`stopped`), 자료원별 결과(작업별 문서 수, 보류 사유, 문서별 임베딩 요약 합계), 종료 코드(research R-16). 임베딩 요약은 `embed()`를 부른 문서는
`EmbedResult.summary`, 캐시 직접 반영 문서는 같은 의미로 만든 값(`requested` = `cache_hits` = 항목 수, 제공자 호출·소비량 0, research R-17)이다.
요약 수치는 `qk.sync_document_result` 행을 센 값과 같다(spec SC-009).

### 2.9 `ActivationCheck` (spec FR-021, research R-09)

`version`, `documents`, `chunks`, `chunks_without_vector`, `last_run_status`, `failed_conditions: tuple[str, ...]`. `failed_conditions`가 비어야 활성화한다.

## 3. 상태 전이

### 3.1 저장된 문서 (`qk.artifact`)

```text
(없음) --PROCESS--> active
active --PROCESS(바뀐 문서)--> active          # 청크 교체, purge_pending에서 이번 버전 제거(비면 purge_reason 비움)
active --UNCHANGED--> active                    # last_seen_*만
active --TAKE_DOWN(일반)--> deleted             # 청크 유지
active --TAKE_DOWN(보안, 삭제 허용)--> deleted   # 모든 버전 청크 삭제
active --TAKE_DOWN(보안, 삭제 보류)--> deleted   # purge_pending = 청크가 남은 버전 목록
deleted --PROCESS(다시 통과, REINSTATED)--> active   # purge_pending에 다른 버전이 남으면 active + 대기
deleted(purge_pending ≠ {}) --PURGE(확인 옵션)--> deleted(purge_pending = {})
active(purge_pending ≠ {}) --PURGE(확인 옵션)--> active(purge_pending = {})
* --FAIL/HOLD/SKIP--> (변화 없음)
```

### 3.2 실행 (`qk.sync_run`, `qk.sync_run_source`)

```text
(점검·잠금 통과) --> running
running --문서 실패 0, 보류 0--> succeeded
running --문서 실패 ≥ 1, 보류 0--> partial
running --보류 ≥ 1(COLLECTION_INCOMPLETE 포함)--> stopped
running --(끊김) 다음 실행이 같은 자료원 잠금을 잡음--> unfinished
```

실행 전 점검 실패, 원격 확인 옵션 없음, 동시 실행은 `qk.sync_run` 행을 만들지 않는다(spec FR-027).

### 3.3 인덱스 버전 (`qk.index_version`)

```text
(없음) --동기화(활성 버전 없음)--> ready
ready --qk-index index activate(활성 버전 없음, 조건 4개)--> active
active와 다른 현재 설정 --> 동기화는 INDEX_MISMATCH로 처리 보류(새 버전 생성·교체는 QK-STO-002)
```
