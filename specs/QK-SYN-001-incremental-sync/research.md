# Research: QK-SYN-001 증분 동기화·문서 단위 원자적 교체·실행 기록·스케줄러·CLI

**작성일**: 2026-10-21 · **명세**: [spec.md](spec.md)(2026-10-21 승인)

spec이 `plan.md`로 넘긴 값과 구현 방식을 정한다. 각 항목은 결정, 근거, 고르지 않은 대안 순서다. 코드 근거는 브랜치 분기 시점(`96f54a8`) 기준이다.

## R-01 코드 배치: 새 `sync/` 패키지와 별도 저장 경계 `SyncStore`

**결정**: 동기화 흐름은 `src/qello_knowledge/sync/`에, 타입은 `domain/sync.py`에 둔다. 동기화가 저장소에 쓰는 일은 새 Protocol `ports/sync.py`의 `SyncStore`로만 하고,
Postgres 구현은 `adapters/postgres/sync_store.py`에 둔다. QK-STO-001 `Store` Protocol과 그 구현의 기존 메서드는 바꾸지 않는다(spec FR-013). 문서 단위 반영에서 청크를
지우고 넣는 SQL은 `adapters/postgres/store.py`의 `replace_chunks` 본문과 같은 일을 하므로, 그 부분을 같은 모듈 안의 내부 함수로 빼서 두 곳이 같이 쓴다(동작 변경 없음,
기존 `tests/localdb/store/test_replace.py`가 그대로 통과해야 한다).

**근거**: spec FR-013은 "상태·출처·청크·실행 기록 결과를 한 번에" 반영하라고 한다. 지금 `upsert_artifact`와 `replace_chunks`는 각자 커밋한다
(`adapters/postgres/store.py:124-157`의 `_db()` 블록, `:166`의 트랜잭션). 이 둘을 바깥에서 묶을 방법이 없으므로 한 트랜잭션 안에서 모두 하는 연산이 새로 필요하다.
`Store`에 메서드를 더하면 QK-RET-001·QK-EMB-001이 보는 경계가 커지고 가짜 구현(`tests/unit/fakes.py`)도 모두 바꿔야 한다. 동기화 전용 경계를 따로 두면 검색 쪽은 그대로다.
`embedding/`이 `domain`·`ports`만 가져오는 규칙(`tests/unit/test_boundaries.py`)과 같은 방식으로 `sync/`도 외부 SDK를 직접 가져오지 않게 한다(C-06).

**대안**: (a) `Store`에 `apply_document`를 더함 — 검색 경계까지 넓어진다. (b) 동기화가 psycopg 연결을 직접 받아 SQL을 씀 — C-06 위반이고 가짜로 시험할 수 없다.

## R-02 저장 스키마: 마이그레이션 `0004_sync.sql`

**결정**: 마이그레이션 하나로 아래를 더한다. 기존 열·제약·함수는 바꾸지 않고 더하기만 한다(QK-STO-001 FR-016~019, 지우는 마이그레이션 아님).

- `qk.artifact`에 열 추가(모두 NULL 허용, 기존 행 영향 없음):
  `source_name`(자료원 이름), `chunk_input_hash`(R-03), `processed_chunking_version`, `processed_index_version`, `processed_outcome`(`chunked`·`empty`),
  `last_seen_version`, `last_seen_at`, `takedown_reason`, `takedown_at`, `purge_pending text[] NOT NULL DEFAULT '{}'`(보안 대상 본문이 남은 인덱스 버전 목록, spec FR-015),
  `purge_reason`(삭제 대기를 만든 보안 사유. 다시 처리돼 `active`로 돌아와도 대기 목록이 남는 동안 유지).
- `qk.sync_source`: 자료원 정체성(spec FR-002). 기본 키 `source_name`, `source_kind`에 유일 제약(종류마다 자료원 하나, spec FR-002 제한을 DB가 한 번 더 강제).
  `scope_key`(설정의 수집 대상을 정규화한 문자열, R-10), `origin_id`, `origin_name`, `registered_at`, `updated_at`. 실행 기록 정리(R-11)와 무관하게 남는다.
- `qk.sync_run`: 실행 하나. `run_id` 기본 키, `trigger`(`manual`·`schedule`), `target`(`local`·`remote`), `started_at`, `finished_at`, `rules_version`, `chunking_version`,
  `index_version`, `status`(`running`·`succeeded`·`partial`·`stopped`·`unfinished`), `summary jsonb`.
- `qk.sync_run_source`: 실행 안의 자료원 하나. 기본 키 `(run_id, source_name)`. `status`, `origin_version`(확정 커밋), `listing_complete`, `stop_reason`, `retry_at`, `summary jsonb`.
  끝나지 않은 기록을 자료원 단위로 닫기 위해 나눈다(spec FR-027, R-06).
- `qk.sync_document_result`: 문서별 작업 결과. 기본 키 `(run_id, doc_key, action)`. 한 실행에서 한 문서에 작업이 둘 이상일 수 있다(예: 삭제 대기 정리 뒤 처리).
  `source_name`, `doc_display`(출력 규칙을 거친 표시값), `artifact_id`(있으면), `outcome`, `change_reason`, `stage`, `failure`, `takedown_reason`, `rule`(보안 규칙 이름),
  `lines int[]`(비밀값 줄 번호). 원문·비밀값 열은 없다(spec FR-028, QK-SEC-001 FR-020).

**근거**: spec FR-006이 요구하는 저장된 상태 중 원본 버전(`source_version`), 링크(`source_url`), 내용 해시(`content_hash`), 접근 범위(`access_scope`), 상태(`status`)는 이미 있다
(`0001_initial_schema.sql:22-37`). 없는 것만 더한다. 실행 기록은 2026-10-21 사용자 결정으로 DB에 둔다(spec FR-027).
메타데이터 스키마 버전(R-08)은 바꾸지 않는다. 청크 행의 열이 그대로이고 검색 함수가 보는 열도 그대로이기 때문이다. 따라서 인덱스 버전 변경이 아니다(AGENTS.md 3.3).

`source_name`을 `qk.artifact`에 더하지만 유일 키 `(source_kind, source_id)`는 그대로 둔다. 같은 종류 자료원 둘을 허용하는 일은 spec FR-002가 막고 있고, 그 검사를 풀 때
유일 키를 바꾼다(spec Assumptions). 지금 열을 더하는 이유는 spec FR-016 (5)의 "그 자료원의 문서"를 고르는 데 필요하기 때문이다.

**대안**: (a) 저장된 상태를 별도 테이블 `qk.sync_document`에 둠 — 원본 자료 항목과 1:1이라 조인만 늘고, 검색의 노출 조건(`status`, `access_scope`)은 어차피 `qk.artifact`에 있다.
(b) 실행 기록을 `sync_run.summary` 하나에 JSON으로 몰아 둠 — QK-SYN-002가 실패 문서를 질의로 고를 수 없다.

## R-03 변경 판단 값

**결정**:

- 청킹 입력 지문 `chunk_input_hash` = `sha256("qk-chunk-input-v1\0" + content_hash + "\0" + location + "\0" + (source_title or ""))`. `content_hash`는 QK-ING-001
  `content_hash(body)`(`domain/source.py`)이고, `source_title`은 청커가 실제로 받는 값(`content.title or item.title`, `chunking/service.py:85`)이다.
- "바뀐 문서" 판정(spec FR-008)은 저장된 행과 비교해 다음 순서로 첫 사유를 남긴다: `new`(행 없음) → `input_changed`(지문 다름) → `chunking_changed`(`processed_chunking_version`
  다름) → `reinstated`(`status <> 'active'` 또는 `access_scope <> 'team'`) → `index_changed`(`processed_index_version`이 이번 실행의 인덱스 버전과 다름).
  준비 상태 인덱스 버전은 판정에 쓰지 않는다(spec FR-008 끝 문장).
- "변경 없음"이면 `last_seen_version`(이번 실행의 원본 버전), `last_seen_at`만 갱신한다(spec FR-010). 여러 문서를 한 문장으로 갱신한다.

**근거**: 위치와 제목은 검색 헤더에 들어가 임베딩 입력을 바꾼다(QK-CHK-002 FR-011·FR-017). 내용 해시 하나만 보면 제목만 바뀐 ClickUp 페이지 같은 경우를 놓친다
(Codex 1차 검토 지적 6). 지문은 청커 입력 세 값만으로 정해지므로 원본 버전(커밋)만 바뀐 문서는 "변경 없음"이다(spec FR-008).

## R-04 문서 단위 반영과 내림의 트랜잭션

**결정**: `SyncStore`의 쓰기 연산은 모두 문서 하나 = 트랜잭션 하나다. 각 연산은 대상 원본 자료 행을 `FOR UPDATE`로 잠근 뒤 처리하고, 같은 트랜잭션에서 `qk.sync_document_result`
한 행을 넣는다.

| 연산 | 한 트랜잭션 안에서 하는 일 |
| --- | --- |
| `apply_document` | 원본 자료 행 넣기·갱신(출처, 지문, 처리 버전, 접근 범위 `team`, `status='active'`, 내림 해제), 이번 인덱스 버전 청크 지우고 넣기, `purge_pending`에서 이번 버전 빼기(비면 `purge_reason`도 비움), 결과 기록 |
| `take_down`(일반) | `status='deleted'`, `takedown_reason`, 결과 기록. 청크는 그대로 |
| `take_down`(보안, 삭제 허용) | `status='deleted'`, 접근 범위를 판정값으로(`restricted`·NULL), `takedown_reason`, 모든 인덱스 버전의 그 문서 청크 행 삭제, `purge_pending='{}'`, `purge_reason` NULL, 결과 기록 |
| `take_down`(보안, 삭제 보류) | 위와 같되 청크를 지우지 않고 `purge_pending`에 청크가 남은 인덱스 버전 목록, `purge_reason`에 사유를 넣는다. 남은 청크가 없으면(빈 문서, 이미 지운 문서) 목록과 사유 모두 비운다 |
| `purge_pending_bodies` | 확인 옵션이 있는 실행에서 `purge_pending`의 버전 청크만 지우고 목록과 `purge_reason`을 비운다. 문서 상태(`active`·`deleted`)는 그대로. 결과 기록 |
| `mark_seen` | 변경 없음 문서들의 `last_seen_*` 갱신(결과 기록은 같은 트랜잭션에서 한 번에) |

청크 행을 지우면 `body`와 `search_text`가 함께 사라진다(spec FR-015 "본문과 키워드 검색용 텍스트"). `qk.embedding` 행은 지우지 않는다.

**근거**: 문서 단위 원자성(spec FR-013)과 결과 기록의 정합성(spec FR-027 "문서별 결과는 그 문서의 반영과 함께")을 한 트랜잭션으로 얻는다. 끊기면 그 문서는 반영도 기록도 없다
(spec SC-014). `FOR UPDATE`는 기존 `replace_chunks`와 같은 직렬화 방식이다(`store.py:169`).
`replace_chunks`의 `chunk_set_hash` 멱등 판정은 동기화에서는 쓰지 않는다. 동기화가 "변경 없음"을 먼저 판정하므로 반영 연산은 항상 실제 교체다.

**대안**: 실행 전체를 한 트랜잭션 — 문서 하나 실패가 전체를 되돌려 C-08을 어긴다.

## R-05 내림 비율 안전장치 초기값

**결정**: 비율 20%. 자료원마다 (일반 내림 대상 수 > 기준 × 0.2) 또는 (본문 삭제 대상 수 > 기준 × 0.2)이면 그 자료원의 일반 내림과 본문 삭제를 모두 보류한다(spec FR-017).
기준 = 그 자료원의 저장된 문서 중 `takedown_reason`이 일반 사유가 아닌 문서 수. 기준이 0이고 대상이 1개 이상이면 넘은 것으로 본다. 확인 옵션은 `--confirm-takedown`.

**근거**: Phase 1 자료원은 79개 문서이고 커밋 하나에서 바뀌는 문서는 보통 몇 개다 `(추론)`. 20%(16개)를 넘는 내림은 포함 패턴 실수, 저장소 비공개 전환, 대규모 정리처럼
사람이 알아야 하는 일이다. 너무 낮으면(예: 5%, 4개) 문서 정리 커밋마다 확인이 필요해 주기 실행이 자주 멈춘다. 측정값이 아니라 초기값이다. 실행 기록에 비율을 남겨 조정한다.

**대안**: 절대 개수(예: 10개) — 자료원 크기에 따라 의미가 달라진다. 최소 개수 조건을 더함 — spec FR-017은 비율만 말하므로 더하지 않는다.

## R-06 동시 실행과 끝나지 않은 기록

**결정**: PostgreSQL 세션 advisory lock을 쓴다.

- 실행 대상: 현재 설정의 활성 자료원과, `qk.sync_source`에 있지만 설정에서 빠졌거나 꺼진 자료원(일반 내림 전용 대상, spec FR-016 (5)). `--source NAME`이면 그 하나만.
- 동기화: 실행 전 점검 뒤, 대상 자료원의 **종류**마다 `pg_try_advisory_lock(<종류 키>)`를 잡고, 전역 키 `qk-sync-index`는 `pg_try_advisory_lock_shared`로 잡는다.
  하나라도 못 잡으면 잡은 것을 놓고 아무것도 쓰지 않고 "이미 실행 중"(종료 코드 6)으로 끝난다(spec FR-029). 잠금 키를 이름이 아니라 종류로 두는 이유는, 원본 자료 행의
  유일 키가 `(source_kind, source_id)`라서 같은 종류의 다른 이름 자료원 두 실행이 같은 행을 덮을 수 있기 때문이다(Codex plan 1차 지적 4). 잠금을 잡은 뒤 자료원 식별 검사
  (R-10 (a)~(d))를 한 번 더 해서, 잠금 전 점검과 잠금 사이에 다른 실행이 정체성을 등록한 경우를 막는다.
- 첫 인덱스 버전 활성화: 전역 키를 `pg_try_advisory_lock`(배타)로 잡는다. 동기화가 하나라도 돌면 못 잡으므로 거부한다(spec FR-021 "조건 확인과 활성화 사이에 동기화가 끼어들지 않는다").
- 끝나지 않은 기록: 종류 잠금을 잡은 실행이 그 종류 자료원의 `qk.sync_run_source.status='running'` 행을 `unfinished`로 바꾸고, 그 실행의 자료원 행이 모두 끝났으면
  `qk.sync_run.status`도 `unfinished`로 닫는다. 잠금을 잡았다는 것은 그 자료원을 처리하는 다른 실행이 없다는 뜻이다(spec FR-027).
- 잠금은 동기화 내내 같은 연결이 들고 있다. 프로세스가 끊기면 연결이 끊겨 잠금이 풀린다(spec FR-029 "영원히 막히지 않는다").

**근거**: 별도 잠금 테이블은 끊긴 실행이 행을 남겨 시간 초과 규칙이 필요하다. advisory lock은 세션과 함께 사라진다. 사용량 예약에도 같은 종류의 잠금을 쓴다
(`0003_embedding_usage.sql`의 `pg_advisory_xact_lock`).

**남는 위험**: 운영 저장소 앞에 트랜잭션 단위 연결 풀러(PgBouncer transaction mode 등)가 있으면 세션 잠금이 유지되지 않는다 `(추론)`. 운영 저장소가 정해지면 직접 연결인지 확인한다
(quickstart 3절 사람 단계).

## R-07 미리 보기와 실제 실행의 공통 판단

**결정**: 수집·필터·청킹·변경 판단·내림 판단·비율 판정은 쓰기 없는 순수 단계 `plan_source()`가 만들고(결과 `SourcePlan`), 미리 보기는 이 결과와
`Embedder.preview()`만 출력한다. 실제 실행은 같은 `SourcePlan`을 받아 쓰기 단계 `execute_source()`로 반영한다. 미리 보기는 잠금을 잡지 않고, 실행 기록·정체성 기준값도 쓰지 않는다.
미리 보기도 실제 실행과 같은 판단 옵션(`--confirm-takedown`, `--allow-partial-budget`)을 받는다. 옵션은 판단만 바꾸고 미리 보기는 어떤 옵션에서도 쓰지 않는다
(Codex plan 1차 지적 10). 실제 실행은 모든 대상 자료원의 `SourcePlan`을 먼저 만든 뒤 쓰기를 시작한다(R-17).

**근거**: spec FR-023(같은 상태면 대상 집합이 같다)을 코드 경로 하나로 보장한다. 미리 보기와 실제 실행 사이에 원본이 바뀌면 다를 수 있지만, 그것은 spec이 보장하지 않는 경우다.

## R-08 인덱스 버전 식별값

**결정**: `iv-<sha256 앞 12자리>`. 해시 입력은 `embedding_model`, `dimension`, `chunking_version`, `metadata_schema_version`을 `\0`으로 이은 문자열이다.
메타데이터 스키마 버전은 상수 `meta-v1`이다(QK-STO-001 시험 데이터와 같은 값, `tests/localdb/store/builders.py:49`). Phase 1 현재 설정의 값은
`@cf/baai/bge-m3`, 1024, `chk-md-20d966f730bb`, `meta-v1`이다. 실제 첫 값은 구현에서 계산해 tasks 실행 기록에 남긴다.

**근거**: 같은 설정이면 같은 값이 나와 "현재 설정의 인덱스 버전"을 저장소 조회 없이 계산할 수 있다(spec FR-019·FR-020). 청킹 규칙 버전(`chk-md-<해시>`, QK-CHK-002 R-07)과 같은 방식이다.

## R-09 첫 인덱스 버전 활성화 조건 확인

**결정**: `qk-index index activate <version>`은 전역 배타 잠금(R-06)을 잡은 트랜잭션 안에서 다음을 확인하고, 모두 맞을 때만 `status='active'`, `activated_at=now()`로 바꾼다.
(1) 활성 버전 없음, (2) `<version>`이 현재 설정에서 계산한 값(R-08), (3) 그 버전으로 쓴 가장 최근 실행이 `succeeded`이고 `running`·`unfinished` 실행이 없음,
(4) `status='active' AND access_scope='team'`이고 그 버전 청크가 1개 이상인 문서 수 ≥ 1, (5) 그 버전 청크 중 `embedding_id IS NULL`인 행 0개.
못 채운 조건은 이름으로 모두 보여 주고 종료 코드 1로 끝난다. 활성화 전 요약(문서 수, 청크 수, 벡터 없는 청크 수, 마지막 실행 상태)을 항상 출력한다.

**근거**: spec FR-021 조건 네 가지를 그대로 옮겼다. (1)은 기존 부분 유일 인덱스(`index_version_one_active`)가 한 번 더 막는다.

## R-10 자료원 정체성

**결정**:

- 설정상 정체성 `scope_key`: `<source_kind>:<정규화한 수집 대상>`. GitHub 저장소 파일은 `github_repo_files:<owner>/<repo>@<ref>`(소문자). 포함·제외 패턴은 넣지 않는다.
  패턴 변경은 내림 경로(spec FR-016)로 처리하는 일이고 정체성 변경이 아니기 때문이다.
- 원본 정체성: 수집 공통 형식에 선택 값 `SourceOrigin(origin_id, origin_name, version)`을 더한다. `version`은 그 수집이 확정한 원본 버전(GitHub는 커밋)이라
  목록이 비거나 불완전해도 실행 기록에 남길 수 있다. `ListPage.origin`(기본 `None`)과 `Listing.origin`이다. `list_all`은 첫 페이지의 값을 쓴다.
  GitHub 어댑터는 이미 받는 저장소 응답(`adapters/github.py:84`)에서 `id`(바뀌지 않는 식별값)와 `full_name`(현재 이름)을, 커밋 응답에서 확정 커밋을 채운다. 추가 요청은 없다.
  GitHub는 이름을 바꾼 저장소 요청을 새 저장소로 보내므로(같은 허용 호스트 안 리다이렉트, QK-ING-002 Edge Cases) `full_name`이 설정과 달라진다.
  가짜 어댑터는 시험 응답에 두 값을 넣을 수 있게 한다. 공통 계약 시험에 "값이 있으면 둘 다 비어 있지 않은 문자열"을 더한다.
- 판정: 실행 전 점검에서 (a) 같은 `source_kind`의 활성 자료원이 둘 이상, (b) 활성 자료원과 같은 종류의 다른 이름 행이 `qk.sync_source`에 있음(그 행의 자료원이 설정에서
  빠졌거나 꺼졌어도 마찬가지. 같은 종류 자료원 교체는 지원하지 않는다), (c) 같은 이름 행의 `scope_key`가 다름이면 실패한다. (d) 활성 자료원이 없는 종류의 저장된 행은
  `TAKEDOWN_ONLY` 대상으로 넘긴다(같은 종류의 새 활성 자료원이 없을 때만, 곧 (b)에 걸리지 않을 때). (b)를 첫 쓰기 전에 거부하므로 `qk.sync_source(source_kind)` 유일 제약 오류는
  정상 경로에서 나지 않는다. 교체 절차(소유권 이전, 옛 자료원 행 정리)는 같은 종류 자료원을 더하는 명세가 정한다(spec Assumptions, Codex plan 2차 지적 N5). 수집 뒤에는 `Listing.origin`을 기준값과 비교한다. 기준값이 없으면 그 자료원의 첫 문서 쓰기 직전에
  등록한다. 값이 없거나 `origin_id`·`origin_name` 중 하나라도 다르면 그 자료원의 처리와 일반 내림을 멈추고 보안 내림만 한다(spec FR-002).

**근거**: spec FR-002가 요구한 두 정체성(원본이 바뀌었는지, 링크가 가리키는 곳이 바뀌었는지)을 추가 요청 없이 얻는다. 이 변경은 QK-ING-001 공통 형식과 QK-ING-002 어댑터 코드를 고친다.
그 명세의 요구사항은 바꾸지 않고 선택 값을 더하는 것이다. 구현 Scope 승인 대상이다(TASK.md).

## R-11 실행 기록 보관과 정리

**결정**: 실행 기록 보관 기간 90일. `qk-index runs prune --retention-days 90`은 `status <> 'running'`이고 `finished_at`(끝나지 않은 기록은 `started_at`)이 기간보다 오래된
`qk.sync_run`과 그 자식 행을 지운다. `running` 기록은 정리 대상이 아니다(끝나지 않은 기록 확정은 R-06의 잠금을 잡은 동기화만 한다). 보관 기간은 1일 이상만 받는다. 함수 하나가 트랜잭션 하나이고 두 번째 실행은 0건이다. 로컬이 아닌 저장소는 `--allow-remote`가 있어야 한다. `qk.sync_source`는 지우지 않는다.

**근거**: 사용량 기록 보관 90일(QK-EMB-001 FR-025)과 맞춘다. 하루 1회 실행에 문서 79개면 하루 약 80행, 90일 약 7,200행이라 저장 한도(ADR-008의 500 MB)에 영향이 없다 `(추론)`.
QK-SYN-002가 실패 문서를 고를 때 최근 실행만 보면 된다.

## R-12 실행 기록의 문서 식별

**결정**: `doc_key = sha256("qk-doc-v1\0" + source_name + "\0" + source_kind + "\0" + source_id)`의 16진 문자열 전체. `doc_display`는 QK-SEC-001 `SecurityVerdict.to_dict`가 쓰는
기록 출력 규칙(`policy.output_context`)을 원본 식별자에 적용한 값이다. 원본 식별자 원값은 기록하지 않는다.

**근거**: QK-SYN-002는 다음 목록의 항목에서 같은 식으로 `doc_key`를 계산해 맞춘다(spec FR-028). 해시는 되돌릴 수 없고, 원본 식별자가 출력 규칙에 걸려 가려진 문서도 찾을 수 있다.

## R-13 운영 저장소 정책 게이트

**결정**: 저장소 안 파일 `config/store_policy.toml`에 운영 저장소 제공자, 확인 날짜, 결정 기록 경로(ADR-008 또는 ADR-019 절)를 적는다. 로컬이 아닌 저장소를 대상으로 하는
`qk-index run`은 `--allow-remote`가 있고, 이 파일이 있으며 필수 항목이 채워져 있을 때만 진행한다. 이 파일은 이번 구현에서 만들지 않는다. 사람이 정책을 확인한 뒤 PR로 더한다(spec FR-033).

**근거**: 확인 결과를 PR 리뷰로 남기고, 코드가 그 존재를 강제한다. `config/source_reviews/`(QK-ING-002 FR-020)와 같은 방식이다.

## R-14 주기 실행: GitHub Actions 워크플로

**결정**: `.github/workflows/index-sync.yml`.

- 트리거: `schedule`(cron `30 0 * * *`, 매일 00:30 UTC = 09:30 KST)과 `workflow_dispatch`. 하루 예산 경계(00:00 UTC) 직후라 그날 예산을 온전히 쓴다.
- 켜기 게이트: 작업에 `if: vars.QK_SYNC_ENABLED == 'true'`. 저장소 변수가 없으면 예약 실행도 건너뛴다(spec FR-036). 사람이 FR-033 확인과 첫 실제 색인 뒤 변수를 만든다.
- 단계: `uv sync --locked --extra index --extra postgres` → `qk-index run --allow-remote --trigger schedule --json` → `qk-index usage prune --allow-remote` → `qk-index runs prune --allow-remote`.
  동기화가 0이 아닌 종료 코드면 작업이 실패로 표시되지만, 정리 단계는 `if: always()`로 돈다(spec FR-034·FR-037).
- 비밀값: GitHub는 `GITHUB_`로 시작하는 Secret 이름을 허용하지 않으므로 Secret `QK_GITHUB_API_TOKEN`을 환경 변수 `GITHUB_API_TOKEN`으로 넘긴다. 나머지는
  `DATABASE_URL`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`(QK-FND-001 설정 이름, `config/registry.py`). `permissions: contents: read`,
  `concurrency: index-sync`(취소 없음), `timeout-minutes: 30`(QK-ING-001 실행당 최대 1,800초).
- 출력: JSON 요약은 원문·주소 없이 나오므로(spec FR-028) 로그에 그대로 남긴다.

**근거**: ADR-008(색인은 GitHub Actions 또는 로컬 CLI, 2.G 증빙은 Actions 실행 기록). Workers Cron은 CPU 10 ms 한도로 맞지 않는다(ADR-008 Rationale).

**확인 필요(사람)**: 이 저장소는 비공개라 Actions 실행 시간이 조직 요금제의 무료 할당에서 빠진다. 하루 1회, 회당 약 2~3분(수집 73초 + 설치) `(추론)`이면 한 달 약 90분이다.
조직의 실제 할당과 사용량은 저장소 설정 화면에서 사람이 확인한다(quickstart 3절). 유료 과금이 시작되면 AGENTS.md 3.5에 따라 켜지 않는다.

## R-15 성능 측정 조건(SC-013)

**결정**: `tests/unit/sync/test_perf.py`(로컬 DB가 있을 때만, `QK_REQUIRE_LOCALDB=1`이면 필수). 입력은 QK-CHK-002 성능 시험과 같은 시드 고정 합성 Markdown 79개
(`random.Random(20261021)`, 약 1.4 MB)를 가짜 자료원으로 넘기고, 가짜 임베딩 제공자를 쓴다. 빈 로컬 DB에 첫 동기화 1회, 이어서 변경 없는 동기화 1회를 각각 3번 반복해
중앙값을 `time.perf_counter()`로 잰다. 원본 대기는 가짜라 0이다. 기준: 첫 동기화 60초, 재동기화 30초 이하. 측정 장비는 tasks 실행 기록에 남긴다.

**근거**: CHK-002 SC-011과 같은 입력을 써서 청킹 몫과 비교할 수 있다(그 실행 기록 0.41초).

## R-16 종료 코드와 출력

**결정**: `qk-index run`의 종료 코드는 0 성공, 1 실행 전 점검 실패(설정·자료원·정체성·보안 규칙·예산 설정·운영 저장소 정책), 2 저장소 사용 불가, 3 원격 확인 옵션 없음,
4 일부 실패(문서 실패가 1건 이상, 나머지는 반영), 5 멈춤(예산 초과·인덱스 버전 불일치·내림 비율 초과·수집 뒤 정체성 불일치, 또는 수집 중단·불완전 목록으로 보류한 일이 있음),
6 이미 실행 중이다. 수집 중단·불완전 목록은 문서 실패가 0이어도 성공이 아니다(Codex plan 1차 지적 3). 그래서 그런 실행은 첫 인덱스 버전 활성화 조건(R-09 (3))도 채우지 않는다.
4와 5가 함께면 5다. 0·1·2·3은 `qk-index usage`와 같은 뜻이다(`indexer/usage.py`).

**근거**: spec FR-031(성공·일부 실패·점검 실패·멈춤·저장소 사용 불가 구분). 주기 실행은 0이 아니면 실패로 표시된다(spec FR-037).

## R-17 예산 판정과 임베딩 단위

**결정**: 실제 실행은 모든 대상 자료원의 `SourcePlan`을 만든 뒤, 처리할 모든 문서의 임베딩 입력을 모아 `Embedder.preview()`를 한 번 부른다. 실행 가능하지 않고
`--allow-partial-budget`이 없으면 모든 자료원의 바뀐 문서 처리를 보류한다(`BUDGET_EXCEEDED`, spec FR-024). 그 밖의 작업은 data-model 2.4 허용표대로 한다.

실행 가능하면(또는 부분 실행이면) 바뀐 문서마다 다음 순서로 처리한다.

1. 캐시 확인: 문서의 모든 `embedding_text`에 대해 `embedding.hashing.input_hash`와 모델 버전으로 `Store.find_embeddings`를 부른다(QK-EMB-001과 같은 해시 규칙). 모두 있으면
   `Embedder.embed()`를 부르지 않고 그 벡터로 `apply_document`한다. 이 경로는 제공자와 사용량 장부를 쓰지 않으므로 둘의 오류와 무관하다(Codex plan 2차 지적 N4).
2. 실행 소진 상태가 켜져 있으면 캐시에 없는 청크가 있는 문서는 `HOLD(BUDGET_EXHAUSTED)`로 기록하고 넘어간다.
3. 아니면 문서 하나 = `EmbedRequest` 하나(`allow_partial`은 옵션 그대로)로 `embed()`를 부른다. 모든 항목에 벡터가 있으면 `apply_document`, 아니면 그 문서만
   `FAILED(embed, <종류>)`다. 다음 중 하나면 실행 소진 상태를 켠다: 항목 실패에 `PROVIDER_QUOTA`·`INDEX_BUDGET`·`USAGE_UNAVAILABLE`이 있음, 요약 경고에 `usage_unavailable`이 있음
   (정산 실패. 벡터는 모두 성공일 수 있다, `embedding/service.py:354-375`), `EmbedError`(`AUTH_CONFIG`·`USAGE_UNAVAILABLE`)가 남(Codex plan 3차 지적 M2). 이미 얻은 벡터로 끝나는
   문서는 반영한다.
   소진 상태는 실행 전체에 하나이고, 켜진 뒤에는 새 제공자 요청을 보내지 않는다(Codex plan 2차 지적 N2, spec FR-025).

QK-EMB-001 경계는 바꾸지 않는다. 캐시 확인은 `Store.find_embeddings`(QK-STO-001 경계)와 `embedding.hashing`(QK-EMB-001 공개 함수)을 쓰고, `sync/`가 `embedding`을 가져오는 것은
경계 규칙 안이다. 문서 하나의 요청 안에서는 QK-EMB-001이 이미 캐시를 먼저 보고 중복을 한 번만 보낸다. 캐시 직접 반영 문서의 임베딩 요약은 `RunSummary`와 같은 의미로 만든다
(`requested` = `cache_hits` = 항목 수, `provider_calls` 0, `neurons` 0). 외부 호출이 없으므로 사용량 장부 행은 만들지 않는다(기존 캐시 적중과 같다, 3차 지적 M4).

**근거**: 예산은 실행 전체로 한 번 판정해야 여러 자료원 합계가 넘을 때 앞 자료원만 반영되는 일이 없다(Codex plan 1차 지적 9). 기존 `embed()`는 묶음 전체 실패에서 중간 결과를
돌려주지 않으므로(`embedding/service.py`의 `_send`가 `EmbedError`를 올림), 문서 단위 요청이어야 실패 격리(spec FR-004·FR-014)가 성립한다(지적 5). `embed()`의 내부 중단 상태는
요청마다 새로 시작하므로(`embedding/service.py:217-222`) 요청 사이의 소진은 동기화가 들고 있어야 한다(2차 지적 N2, Codex 메모리 재현). 문서 사이 중복 텍스트는 캐시가
흡수하므로 요청을 나눠 생기는 추가 외부 호출은 같은 실행 안에서 처음 나온 중복뿐이다 `(추론)`. Phase 1 규모(문서 79개, 문서당 청크 평균 약 16개, CHK-002 H01 1,291개)에서
요청 수는 문서 수 이하다.

## R-18 `plan_source()`의 조립

**결정**: `plan_source()`는 기존 `screen_source()`를 그대로 부르고, `ScreenResult`에 선택 필드 `listing: Listing | None`(기본 `None`)을 더해 `screen_source()`가 채운다
(QK-SEC-001 코드에 필드 하나, 동작 변경 없음). 이어서 보안 필터를 통과한 문서마다 R-03의 변경 조건 전체(새 문서, 청킹 입력 지문, 청킹 규칙 버전, 내림·접근 범위 복구,
인덱스 버전)를 저장 상태와 비교하고, `PROCESS`로 판정된 문서만 `chunk_screened()`(QK-CHK-002)에 넘긴다. 다섯 조건 모두 청킹 없이 정할 수 있다. 변경 없음 문서의 청킹 호출은 0이다
(spec FR-009, Codex plan 2차 지적 N1, 3차 지적 M3).
그 밖에 저장된 문서마다 다음을 판정한다.

- 설정 제외 패턴: 저장된 위치에 보안 필터와 같은 제외 판정(`security/screen.py`의 자료원 제외 확인. 경로 정규화 뒤 대소문자 무시)을 적용한다. 지금은 비공개 함수
  `_source_excluded`라서 같은 동작의 공개 이름 `source_excluded`를 더한다(QK-SEC-001 코드, 동작 변경 없음). 걸리면 목록 완전 여부와 상관없이 보안 내림(`config_excluded`)이다.
- 포함 범위: 제외에 걸리지 않고 `in_scope(location, include, ())`(목록 조회와 같은 대소문자 구분)가 거짓이면 포함 패턴에서 빠진 것이다. 목록이 완전할 때 일반 내림(`source_missing`).
  `in_scope`는 두 사유를 구분하지 않고 거짓만 돌려주므로(`domain/scope.py:6-12`) 제외 판정을 먼저 따로 한다(2차 지적 N3). 두 조건이 겹치면 보안 내림이 이긴다.
- 목록에 없음: `listing.complete`이고 수집이 멈추지 않았을 때만 일반 내림.
- 보안 필터 판정: `ScreenResult.verdicts`에서 경로 제외·비밀값 차단·접근 범위 보류는 보안 내림(규칙 이름·줄 번호를 결과에 남김), 판정 실패·본문 조회 실패는 실패 기록만.
- 수집 요약은 `ScreenResult.fetch.to_dict()`에서 항목 목록을 뺀 값을 자료원 요약에 넣는다(spec FR-026).

**근거**: `screen_source()`의 조립(요청 자료와 받은 본문의 식별자 대조 등, `security/screen.py:206-250`)을 동기화가 다시 쓰면 두 곳이 어긋날 수 있다. 필드 하나를 더하는 편이
위험이 작다(Codex plan 1차 지적 7). 이 변경은 구현 Scope 승인 대상이다(plan.md).
