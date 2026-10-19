---
description: "QK-ING-001 구현 작업 목록"
---

# Tasks: QK-ING-001 자료원 어댑터 계약·자료원 설정·호출 한도·재시도

**Input**: `specs/QK-ING-001-source-adapter-contract/`의 plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: 포함한다. 명세의 수용 시나리오와 C-12(수용 기준은 검증으로 닫는다)가 자동 테스트를 요구한다. 스토리마다 테스트를 먼저 쓰고 실패를 확인한 뒤 구현한다.

**Organization**: 사용자 스토리별 단계로 나눈다. 우선순위는 US1·US2(P1) → US3·US4(P2)다. 모든 시험은 재생 전송과 가짜 시계로 돌아 외부 요청 0건, 실제 대기 0초다.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 다른 파일을 다루고 미완료 작업에 기대지 않아 병렬로 할 수 있다
- **[Story]**: 해당 사용자 스토리(US1~US4)

---

## Phase 1: Setup

**Purpose**: 새 패키지·디렉터리 자리 만들기. 의존성 추가 없음(plan.md Technical Context)

- [x] T001 `src/qello_knowledge/sources/__init__.py`를 만들고 의존 규칙을 문서 문자열로 적는다: "`domain`·`ports`·`config`만 가져오고 `adapters`를 가져오지 않는다. 종류 이름과 어댑터를 잇는 일은 QK-SYN-001이 진입점에서 한다"
- [x] T002 [P] 테스트 디렉터리 만들기: `tests/contract/__init__.py`, `tests/unit/domain/__init__.py`, `tests/unit/sources/__init__.py`, `tests/fixtures/responses/fake/`, `tests/fixtures/sources/`. 기존 `tests/unit/` 하위 디렉터리가 `__init__.py`를 쓰는지 확인하고 같은 방식을 따른다
- [x] T003 [P] `config/sources.toml`: 자료원 없이 형식 안내 주석만 둔다(contracts/sources-config.md 예를 주석으로, "첫 실제 자료원은 QK-ING-002가 추가한다"). 비밀값 없음

---

## Phase 2: Foundational

**Purpose**: 모든 스토리가 쓰는 공통 형식·경계·시계·재생 전송. 끝나야 스토리 작업을 시작한다

- [x] T004 [P] `tests/unit/domain/test_source_types.py`: `SourceItem`의 `source_id`·`change_key`가 빈 문자열이면 생성 시 `ValueError`, `url`은 `https`만, `modified_at`·`fetched_at`은 시간대 없는 datetime이면 `ValueError`, `AccessInfo(UNKNOWN)`이면 `raw`는 빈 튜플이어야 함, `SourceRequest.method`는 문자열 그대로 보관(검사는 세션이 함), 모든 타입이 불변(`frozen=True`)
- [x] T005 [P] `tests/unit/domain/test_scope.py`: research.md R-05 표 여섯 사례를 그대로 시험(`docs/a.md`·`**/*.md` 맞음, `a.md`·`**/*.md` 맞음, `docs/x/y.md`·`docs/**` 맞음, `docs/x/y.md`·`docs/*` 안 맞음, `.github/a.md`·`**/*.md` 맞음, `Docs/A.MD`·`**/*.md` 안 맞음). 포함·제외가 겹치면 제외가 이긴다(FR-012). 포함 목록이 비면 `ValueError`
- [x] T006 `src/qello_knowledge/domain/source.py`: data-model.md의 타입을 정의한다. `SourceItem`, `AccessInfo`(`PROVIDED`, `UNKNOWN`), `OriginState`(`ACTIVE`, `ARCHIVED`, `DELETED`), `ChangeKeyKind`(`VERSION`, `MODIFIED_AT`, `CONTENT_HASH`), `SourceContent`, `ContentFormat`(`MARKDOWN`, `CODE`, `JSON`, `TEXT`), `ListPage`, `Listing`, `SourceRequest`, `SourceResponse`("`headers`(소문자 키)", `truncated`), `TransportError(kind)`, `ResponseClass`(`OK`, `TRANSIENT`, `PERMANENT`, `AUTH`), `RateLimitHint`, `FailureType`(일시적 `RATE_LIMITED`, `SERVER_ERROR`, `TIMEOUT`, `CONNECTION` / 영구 `NOT_FOUND`, `ACCESS_DENIED`, `INVALID_RESPONSE`, `SIZE_EXCEEDED`, `REDIRECT_BLOCKED` / 인증 `AUTH_FAILED`), `ItemStatus`(`SUCCEEDED`, `TRANSIENT_EXHAUSTED`, `PERMANENT_FAILED`, `SKIPPED`), `StopReason`(`AUTH_FAILED`, `WAIT_TOO_LONG`, `REQUEST_BUDGET`, `RUN_TIME`), `StopInfo`, `ItemOutcome`, `FetchResult`. 예외 `InvalidResponse`, `SourceFailure(failure, http_status)`, `RunStopped(stop)`, `ReadOnlyViolation`. 표준 라이브러리만 import. T004 통과
- [x] T007 `src/qello_knowledge/domain/scope.py`: `in_scope(location, include, exclude) -> bool`. `PurePosixPath(location).full_match(pattern)`, 대소문자 구분, "겹치면 제외가 이긴다". T005 통과
- [x] T008 `src/qello_knowledge/domain/source_config.py`: 설정 값 객체만 둔다(읽기·검증은 T028). `SourceConfig`(`name`, `kind`, `enabled`, `auth`, `scope`, `limits`, `retry`, `max_content_bytes`, `allowed_hosts`), `SourceScope`(`include`, `exclude`, 종류별 키 `extra: tuple[tuple[str, str], ...]`), `RateLimits`(기본값 `max_requests_per_minute=60`, `max_requests_per_second=None`, `max_requests_per_run=2000`, `max_wait_seconds=300`, `max_run_seconds=1800`), `RetryPolicy`(기본값 `max_retries=3`, `initial_backoff_seconds=1`, `max_backoff_seconds=60`). 불변, 표준 라이브러리만. `ports`가 설정 타입을 참조해도 경계 규칙을 지키게 하려는 배치다
- [x] T009 `src/qello_knowledge/ports/source.py`: contracts/source-adapter.md의 `SourceAdapter`(`kind`, `list_page`, `fetch_content`, `classify`, `rate_limit_hint`), `SourceTransport`(`send`), `SourceSession`(`send`) Protocol. 타입은 `qello_knowledge.domain.source`와 `qello_knowledge.domain.source_config`에서만 가져온다. `uv run pytest tests/unit/test_boundaries.py` 통과
- [x] T010 [P] `src/qello_knowledge/sources/clock.py`: `Clock` Protocol(`now() -> datetime`(UTC), `monotonic() -> float`, `sleep(seconds)`)과 `SystemClock`
- [x] T011 [P] `tests/unit/sources/conftest.py`: `FakeClock` fixture(`sleep`은 실제로 기다리지 않고 시각만 앞으로, 누적 대기 시간 기록), 고정 지연 함수 fixture(`lambda cap: cap / 2` 같은 결정적 `Jitter`). `random.Random` 시드를 쓰지 않는다(research R-07, ruff `S311`)
- [x] T012 [P] `tests/unit/sources/test_replay.py`: `ReplayTransport`가 (메서드, URL)마다 준비된 응답을 순서대로 돌려주고, 받은 요청을 모두 기록하며, 준비되지 않은 요청이면 `AssertionError`(시험 실패), 시나리오 파일의 `_meta`(`source_api`, `saved_at`, `redactions`)가 없으면 읽기 실패, `TransportError` 항목(`timeout`, `connection`)을 응답 대신 낼 수 있다
- [x] T013 `src/qello_knowledge/adapters/replay.py`: `ReplayTransport.from_file(path)`와 `requests` 기록. 시나리오 형식: `{"_meta": {...}, "body": {"exchanges": [{"method", "url", "responses": [{"status", "headers", "body"} | {"error": "timeout"|"connection"}]}]}}`. `max_bytes`를 넘는 본문은 잘라 `truncated=True`. T012 통과

**Checkpoint**: 공통 형식, 경계, 재생 전송 준비 완료

---

## Phase 3: User Story 1 - 새 자료원은 정해진 계약만 구현하면 파이프라인에 붙는다 (P1) 🎯 MVP

**Goal**: 어댑터 계약, 기본 세션(읽기 전용·해시·시각), 목록 순회, 가짜 어댑터, 재사용 가능한 공통 계약 시험

**Independent Test**: 가짜 어댑터로 공통 계약 시험을 돌려 모두 통과하고, 기록된 요청이 모두 `GET`·`HEAD`인지 본다

### Tests (US1)

- [x] T014 [P] [US1] `tests/contract/source_adapter_contract.py`: 기반 클래스 `SourceAdapterContract`(이름이 `Test`로 시작하지 않아 직접 수집되지 않음). 하위 클래스가 fixture `adapter`, `transport`, `config`를 구현한다. 검사: 목록 항목 필수 필드와 권한 없으면 `UNKNOWN`(US1-1, FR-002), 본문의 본문·내용 형식·원본 버전·위치(US1-2, FR-003), 수정 시각 없으면 `change_key_kind == CONTENT_HASH`(US1-3), 여러 페이지 목록에서 `source_id` 중복 없음(US1-4, FR-005), 기록된 요청 메서드가 모두 `GET`·`HEAD`(US1-5, SC-002), 결과 타입이 `qello_knowledge.domain` 모듈 소속(FR-004), 형식이 다른 응답은 `InvalidResponse`(Edge Cases)
- [x] T015 [P] [US1] `tests/fixtures/responses/fake/`: 시나리오 파일 `basic.json`(2페이지, 5개, 권한 있음), `no_modified_at.json`(수정 시각·버전 없음), `no_access.json`(권한 정보 없음), `page_overlap.json`(페이지 경계 중복 1개), `invalid_shape.json`(필드 누락 1개). 호스트는 `https://fake.invalid`. QK-FND-001 응답 샘플 형식(`_meta` + `body`)을 따른다
- [x] T016 [P] [US1] `tests/unit/sources/test_session_basic.py`: `GET`·`HEAD` 밖의 메서드는 보내기 전에 `ReadOnlyViolation`이고 전송에 기록된 요청 0건, 본문을 받은 `SourceContent`에 `content_hash`가 `sha256:` + 본문 UTF-8 바이트의 16진 해시로 채워지고 `fetched_at`이 가짜 시계 시각(UTC), 같은 본문이면 같은 해시(C-07)
- [x] T017 [P] [US1] `tests/unit/sources/test_list_all.py`: 커서가 `None`일 때까지 순회, `source_id` 중복은 처음 것을 남기고 `duplicates_dropped` 증가, 포함·제외 패턴(`location` 기준)으로 뺀 수가 `excluded`, 마지막 페이지까지 받으면 `complete=True`
- [x] T018 [P] [US1] `tests/contract/test_fake_adapter_contract.py`: `SourceAdapterContract`를 상속해 `FakeSourceAdapter`와 T015 시나리오로 계약 시험을 돈다

### Implementation (US1)

- [x] T019 [US1] `src/qello_knowledge/sources/session.py`: `DefaultSourceSession(transport, adapter, config, clock)`의 기본 동작만 만든다: 읽기 전용 강제(`GET`·`HEAD` 밖이면 `ReadOnlyViolation`), `requests_made` 계수, 본문 해시·수집 시각 채우기(`finalize_content`). 한도·재시도·리다이렉트는 US3·US4에서 더한다. T016 통과
- [x] T020 [US1] `src/qello_knowledge/sources/collect.py`: `list_all(adapter, config, session) -> Listing`(contracts/source-adapter.md). T017 통과
- [x] T021 [US1] `src/qello_knowledge/adapters/fake.py`: `FakeSourceAdapter(kind="fake")`. 목록 `GET https://fake.invalid/items?cursor=<커서>`, 본문 `GET https://fake.invalid/items/<id>`. 수정 시각·버전이 없으면 본문을 받아 내용 해시로 `change_key`를 채움(`change_key_kind=CONTENT_HASH`), 권한 필드가 없으면 `AccessInfo(UNKNOWN)`, 필드가 빠진 응답은 `InvalidResponse`. `classify`·`rate_limit_hint`는 domain 기본 함수를 쓴다. 분류 기본 함수(T043)가 생기기 전까지는 2xx만 `OK`로 보는 임시 구현을 쓴다. 모듈 문서 문자열에 "후속 명세 시험용, 실제 원본 없음"
- [x] T022 [US1] `uv run pytest tests/contract tests/unit/sources tests/unit/domain -q`로 T014~T018 통과 확인

**Checkpoint**: 계약과 가짜 어댑터가 단독으로 동작한다(MVP)

---

## Phase 4: User Story 2 - 자료원 설정을 선언하고, 잘못되면 수집 전에 멈춘다 (P1)

**Goal**: `config/sources.toml` 읽기·검증, 등록 종류, `qk-index sources check`, `run`의 사전 검증

**Independent Test**: 틀린 설정 사례마다 검증을 돌려 실행 전에 실패하고 재생 전송 요청 0건, 값이 출력되지 않는지 본다

### Tests (US2)

- [x] T023 [P] [US2] `tests/fixtures/sources/`: `valid.toml`(활성 `fake` 1개, 비활성 1개), `missing_fields.toml`(`scope.include` 누락), `unknown_kind.toml`(`kind = "notion"`), `token_value.toml`(`auth`에 토큰 형식 값), `unknown_key.toml`(오타 키), `duplicate_name.toml`, `bad_auth_name.toml`(레지스트리에 없는 이름), `overlap.toml`(포함·제외 겹침). 토큰 형식 값은 실제 값이 아닌 형식만 맞춘 문자열이고 `scripts/preflight.py` 오탐이면 `scripts/preflight_allowlist.txt`에 사유와 함께 올린다
- [x] T024 [P] [US2] `tests/unit/sources/test_config.py`: 사례마다 오류 코드(`MISSING`, `UNKNOWN_KEY`, `INVALID`, `UNKNOWN_KIND`, `DUPLICATE_NAME`, `UNKNOWN_AUTH_SETTING`, `TOKEN_VALUE`)와 필드 경로가 맞고 한 번에 모두 보고됨(US2-1~3). `UNKNOWN_KIND` 문구에 "결정 기록이 필요하다(AGENTS.md 3.1)". 오류 문자열 어디에도 설정 값이 없음. 비활성 자료원은 `name`, `kind`, `enabled`만 검사하고 상태 `DISABLED`(US2-4). 생략한 `limits`·`retry`·`max_content_bytes`·`allowed_hosts`는 research.md R-16 기본값. 필드 규칙: "`name` 소문자·숫자·`-`, 1~64자. 파일 안에서 유일", "`max_content_bytes` 1 이상", "`max_requests_per_minute` 1 이상", "`max_wait_seconds` 0 이상", "`max_run_seconds` 1 이상", "`max_retries` 0 이상", "`initial_backoff_seconds` 0보다 크다", "`max_backoff_seconds` `initial_backoff_seconds` 이상", "`include` 비어 있지 않은 패턴 목록", GitHub `repo`는 `owner/name`
- [x] T025 [P] [US2] `tests/unit/sources/test_config_report.py`: 표 출력과 `--json` 한 줄 출력이 contracts/cli.md 형식(상태 `OK`·`DISABLED`·`INVALID`, 범위 요약, `issues`의 `field`·`code`), `TOKEN_VALUE`가 난 필드는 값 대신 코드만(US2-5, FR-013)
- [x] T026 [P] [US2] `tests/unit/indexer/test_cli.py`에 사례 추가(기존 사례 유지): `sources check --sources valid.toml`은 0, 틀린 파일은 1, 파일 없음·TOML 문법 오류는 1, `run`은 자료원 설정이 틀리면 1이고 "수집할 자료원 없음"을 출력하지 않음, 활성 자료원이 있으면 자료원별 `수집 대기`·`비활성`, 기본 경로(`config/sources.toml`)로는 지금처럼 "수집할 자료원 없음". 어느 경우에도 `ReplayTransport`·소켓 요청 0건(SC-003)

### Implementation (US2)

- [x] T027 [US2] `src/qello_knowledge/sources/kinds.py`: `SourceKindSpec`(`name`, `requires_auth`, `scope_keys`, `default_allowed_hosts`)와 등록 목록. `github_repo_files`(`requires_auth=True`, scope 키 `repo`(`owner/name`)·`ref` 필수, 기본 호스트 `api.github.com`)와 `fake`(`requires_auth=False`, 종류별 scope 키 없음, 기본 호스트 `fake.invalid`). Notion은 등록하지 않는다. 문서 문자열에 "종류 추가는 결정 기록이 필요하다(AGENTS.md 3.1)"
- [x] T028 [US2] `src/qello_knowledge/sources/config.py`: `ConfigIssue`와 `load_sources(path) -> (configs, issues)`. 결과는 T008의 `domain/source_config.py` 값 객체로 만든다. `tomllib`로 읽고 contracts/sources-config.md 검증 규칙을 적용한다. `auth`는 `config/registry.py`의 `specs_for(Entrypoint.INDEX)` 중 `secret=True` 항목 이름이어야 함. 토큰 형식 검사는 레지스트리 비밀 항목의 형식 규칙과 알려진 접두사(`ghp_`, `gho_`, `ghu_`, `ghs_`, `ghr_`, `github_pat_`, `xox`, `sk-`, `ATATT`, `figd_`)로 모든 문자열 값에 적용. 오류에 값을 넣지 않는다. T024 통과
- [x] T029 [US2] `src/qello_knowledge/sources/report.py`: 설정 점검 결과의 표·JSON 출력(contracts/cli.md). T025 통과
- [x] T030 [US2] `src/qello_knowledge/indexer/cli.py`: `sources check [--sources 경로] [--json]` 하위 명령 추가, `run`에 `--sources`와 자료원 설정 검사 추가(설정 점검 → 자료원 검사 → 자료원별 상태, 활성 없으면 "수집할 자료원 없음"). 기본 경로 `config/sources.toml`. 종료 코드 0·1·2. T026 통과

**Checkpoint**: 설정 검증과 명령줄이 단독으로 동작한다

---

## Phase 5: User Story 3 - 원본의 호출 한도를 넘지 않는다 (P2)

**Goal**: 미끄러지는 창 한도, 실행당 상한, 원본 한도 힌트, 대기 상한에서 멈추고 보고

**Independent Test**: 가짜 시계와 재생 전송으로 자료 200개를 수집해 어떤 60초 창에도 요청이 상한 이하인지, 멈출 때 처리·남은 수와 다시 시도할 시각이 보고되는지 본다

### Tests (US3)

- [x] T031 [P] [US3] `tests/unit/sources/test_limits.py`: 분당 60회 설정에서 요청 200번의 시각 기록을 받아 어떤 60초 창에도 60회 이하(US3-1, SC-004), 선택 초당 상한도 같은 방식, 설정 한도와 원본 힌트 중 더 오래 기다리게 하는 쪽을 따름(FR-015), 필요한 대기가 `max_wait_seconds` 이하면 그만큼 대기(US3-2), 넘으면 `WAIT_TOO_LONG`과 `retry_at`(US3-3), 실행당 상한에 닿으면 `REQUEST_BUDGET`(US3-4)
- [x] T032 [P] [US3] `tests/unit/domain/test_rate_limit_hint.py`: 기본 `default_rate_limit_hint`가 `Retry-After: 30`은 `retry_after_seconds=30.0`·`retry_at=None`으로, HTTP 날짜는 `retry_at`(UTC)·`retry_after_seconds=None`으로 읽고, 헤더가 없거나 해석할 수 없으면 `None`. 함수는 시각을 읽지 않는다(시스템 시계 호출 없음)
- [x] T033 [P] [US3] `tests/fixtures/responses/fake/`: `many_items.json`(200개), `rate_limited.json`(`Retry-After: 30`인 429 뒤 성공), `rate_limited_long.json`(`Retry-After: 3600`)
- [x] T034 [P] [US3] `tests/unit/sources/test_session_limits.py`: 세션에 한도를 붙인 뒤 `many_items.json` 수집에서 SC-004, `rate_limited_long.json`에서 세션이 `RunStopped(WAIT_TOO_LONG)`을 내고 `stop.retry_at`이 맞음(US3-3). `FetchResult`의 `processed`·`remaining` 요약 검증은 `fetch_contents`(T046)가 생긴 뒤 T041에서 한다(2026-10-19 사용자 결정)

### Implementation (US3)

- [x] T035 [US3] `src/qello_knowledge/sources/limits.py`: `RequestGate(limits, clock)`. 최근 요청 시각 `deque`로 창 계산, 실행당 요청 수, `apply_hint(RateLimitHint)`, `before_request()`가 필요한 대기를 계산해 상한 이하면 `clock.sleep`, 넘으면 `RunStopped(WAIT_TOO_LONG, retry_at)`, 실행당 상한이면 `RunStopped(REQUEST_BUDGET)`. T031 통과
- [x] T036 [US3] `src/qello_knowledge/domain/source.py`에 `default_rate_limit_hint(response)` 추가. 원본이 준 형태 그대로 담고 시각을 계산하지 않는다(data-model.md RateLimitHint). T032 통과
- [x] T037 [US3] `src/qello_knowledge/sources/session.py`: 매 요청 전에 `RequestGate.before_request()`, 응답마다 `adapter.rate_limit_hint()`를 받아 `retry_after_seconds`를 `clock.now()` 기준 절대 시각으로 바꾼 뒤(둘 다 있으면 더 늦은 쪽) 게이트에 반영. T034 통과

**Checkpoint**: 한도가 세션에서 동작한다

---

## Phase 6: User Story 4 - 일시적 실패는 재시도하고, 한 자료의 실패가 전체를 멈추지 않는다 (P2)

**Goal**: 응답 분류, full jitter 재시도, 인증 실패 즉시 중단, 리다이렉트 호스트 검사, 크기 상한, 자료별 실패 격리, 결과·로그 비밀값 0건

**Independent Test**: 일시적 실패 2회 뒤 성공, 영구 실패, 정상 자료를 섞어 수집하고 자료별 상태·재시도 횟수를 본다. 인증 실패 시 첫 실패 뒤 요청이 멈추는지 본다

### Tests (US4)

- [x] T038 [P] [US4] `tests/unit/domain/test_classify.py`: `default_classify`가 research.md R-07 표를 따른다(2xx `OK`, 429 `RATE_LIMITED`, 500·502·503·504 `SERVER_ERROR`, 401 `AUTH`, 403 `ACCESS_DENIED`, 404·410 `NOT_FOUND`, 그 밖의 4xx `INVALID_RESPONSE`). `TransportError(timeout|connection)`은 `TIMEOUT`·`CONNECTION`
- [x] T039 [P] [US4] `tests/unit/sources/test_retry.py`: 간격이 `uniform(0, min(max_backoff, initial_backoff × 2^n))`(고정 지연 함수로 값 확인, 기본 `system_jitter`는 `random.SystemRandom` 사용), 원본 힌트가 있으면 세션이 절대 시각으로 바꾼 `retry_at`을 따름, 대기 합이 `max_run_seconds`를 넘으면 `RUN_TIME`으로 멈춤(FR-018, Edge Cases)
- [x] T040 [P] [US4] `tests/fixtures/responses/fake/`: `flaky.json`(502 두 번 뒤 성공), `exhausted.json`(503 네 번), `not_found.json`(404), `auth_failed.json`(401), `redirect_ok.json`(`fake.invalid` 안 302), `redirect_blocked.json`(다른 호스트 302), `too_large.json`(목록 `size_bytes`가 상한 초과), `too_large_unknown.json`(크기 미표시, 본문이 상한 초과), `mixed.json`(정상·영구 실패·정상)
- [x] T041 [P] [US4] `tests/unit/sources/test_collect.py`: 재시도 상한 3에서 `flaky.json` → `SUCCEEDED`, `retries=2`(US4-1, SC-005), `exhausted.json` → `TRANSIENT_EXHAUSTED`이고 나머지 자료 처리(US4-2), `not_found.json` → `PERMANENT_FAILED`, `retries=0`(US4-3, SC-005), `auth_failed.json` → 첫 401 뒤 요청 0건, 그 자료와 남은 자료 `SKIPPED`, `stop.reason=AUTH_FAILED`(US4-4), `mixed.json` → 나머지 100% `SUCCEEDED`(SC-006), `rate_limited_long.json` → 멈춘 `FetchResult`의 `processed`·`remaining`·`stop.retry_at`(US3-3, FR-016, T034에서 옮김), `redirect_blocked.json` → `REDIRECT_BLOCKED`, `redirect_ok.json` → 성공이고 요청 2회 집계(FR-022), `too_large.json` → 본문 요청 없이 `PERMANENT_FAILED(SIZE_EXCEEDED)`, `too_large_unknown.json` → `SIZE_EXCEEDED`(research R-08), 목록 페이지가 재시도 소진하면 `listing_complete=False`(Edge Cases)
- [x] T042 [P] [US4] `tests/unit/sources/test_fetch_result_no_secret_leak.py`: 표식 토큰(테스트 안에서 이어 붙여 만든 형식만 맞춘 값)을 `SecretValue`로 넣고, 응답 본문과 헤더에도 표식을 심은 시나리오로 수집한 뒤 `FetchResult.to_dict()` JSON과 `caplog` 로그를 `scripts/preflight.py`의 `RULES`(`importlib`로 읽음)와 표식 문자열로 검사해 0건(US4-5, FR-021, SC-007). `to_dict()`에 본문·헤더·URL 질의 문자열이 없음

### Implementation (US4)

- [x] T043 [US4] `src/qello_knowledge/domain/source.py`에 `default_classify(response_or_error) -> ResponseClass` 추가(research.md R-07). `adapters/fake.py`의 임시 분류를 이것으로 바꾼다. T038 통과
- [x] T044 [US4] `src/qello_knowledge/sources/retry.py`: `Jitter` 타입, `system_jitter(cap)`(`random.SystemRandom().uniform(0, cap)`), `next_delay(policy, attempt, jitter, retry_at, clock)`(`retry_at`은 세션이 절대 시각으로 바꾼 값)과 실행 소요 시간 검사. T039 통과
- [x] T045 [US4] `src/qello_knowledge/sources/session.py`: 분류에 따라 재시도(일시적), `SourceFailure`(영구·재시도 소진), `RunStopped(AUTH_FAILED)`(인증), 3xx `Location` 호스트가 `allowed_hosts`에 있으면 최대 3번 따라가고 아니면 `SourceFailure(REDIRECT_BLOCKED)`, 요청에 `max_bytes=max_content_bytes`를 채우고 `truncated`면 `SourceFailure(SIZE_EXCEEDED)`. 로그에는 자료원 이름·원본 식별자·상태·재시도 횟수·실패 유형·HTTP 상태 코드만 남긴다(research R-13)
- [x] T046 [US4] `src/qello_knowledge/sources/collect.py`: `fetch_contents(adapter, config, session, items) -> FetchResult`. `size_bytes`가 상한을 넘으면 요청 없이 `SIZE_EXCEEDED`, `SourceFailure`는 그 자료만 기록하고 계속(C-08), `RunStopped`면 남은 자료 `SKIPPED`로 멈춤, `ReadOnlyViolation`은 잡지 않고 올림. `list_all`은 페이지 실패·중단 시 `complete=False`. `FetchResult.to_dict()`는 본문·헤더·토큰을 담지 않는다. T041·T042 통과

**Checkpoint**: 모든 스토리 완료

---

## Phase 7: SC-001 확인 — 두 번째 가짜 어댑터 (별도 커밋)

**Purpose**: 계약만 구현하면 계약 밖 코드(동기화·보안·청커, `src/` 전체) 변경 없이 붙는지 확인한다. 이 단계의 커밋은 `tests/` 아래 파일만 바꿔야 한다

- [x] T047 [US1] `tests/contract/second_fake.py`: `FakeSourceAdapter`와 응답 구조가 다른 두 번째 가짜 어댑터(예: 목록을 `offset`·`limit`으로 나누고, 버전 필드 이름이 다름). `src/`를 고치지 않는다. 종류 이름은 시험 안에서만 쓰는 값으로 두고 등록 목록(`sources/kinds.py`)을 고치지 않는다
- [x] T048 [US1] `tests/contract/test_second_fake_contract.py`와 시나리오 파일(`tests/fixtures/responses/fake/second_*.json`): `SourceAdapterContract` 상속으로 계약 시험 통과
- [x] T049 [US1] T047·T048만 한 커밋으로 만들고 `git show --stat HEAD`로 변경 파일이 `tests/` 아래뿐인지 확인해 PR 증빙으로 남긴다(SC-001)

---

## Phase 8: Polish & Cross-Cutting

- [x] T050 [P] `uv run ruff format .`와 `uv run ruff check .`로 정리
- [x] T051 AGENTS.md 7절 기본 검증 전체 실행: `python scripts/preflight.py`, `git diff --check origin/main...HEAD`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run qk-dev db up`, `QK_REQUIRE_LOCALDB=1 uv run pytest`. 결과를 PR에 남긴다
- [x] T052 quickstart.md의 성공 기준별 명령과 명령줄 확인을 차례로 실행하고 결과를 기록한다(SC-001~007)
- [ ] T053 PR 본문에 사람 확인 항목을 적는다(plan.md "사람 확인이 필요한 것"): 명세 문구 정리 제안(Edge Cases 크기 초과, FR-002 제목 필드), QK-STO-001 필드 대응표 확인 요청(#33), 기본값이 초기값이라는 점, 독립 검토 결과와 반영 내역, QK-ING-002로 넘긴 후속 메모 두 건(가짜 어댑터의 내용 해시 계산을 공용 함수로 모으기, 공통 계약 테스트의 고정값 가정을 하위 클래스가 기대값을 넘기는 방식으로 바꾸기)

---

## Phase 9: 독립 검토 반영 (2026-10-19 검토 결과 변경 요청, 사용자 결정)

**Purpose**: 독립 검토가 재현한 문제 1~3번을 고친다. 테스트를 먼저 쓰고 실패를 확인한 뒤 구현한다

- [ ] T054 [P] `tests/unit/sources/test_config.py`에 사례 추가: 공백 없는 48자 경로 패턴(`specs/QK-ING-001-source-adapter-contract/**/*.md`)이 `include`에 있어도 통과, `ghp_`·`github_pat_`·`cfat_` 접두사 값과 `postgres` 스킴 URL은 `TOKEN_VALUE`, 토큰으로 판정된 필드는 `TOKEN_VALUE` 하나만 보고(같은 필드 `INVALID` 중복 없음), 비활성 자료원의 `auth`·`scope`에 토큰 값이 있으면 `TOKEN_VALUE`. 토큰 형식 문자열은 테스트 안에서 이어 붙여 만든다
- [ ] T055 [P] `tests/unit/indexer/test_cli.py`에 사례 추가: 비활성 자료원에 토큰 값이 있는 설정이면 `sources check`와 `run`이 종료 코드 1이고 출력에 값이 없음
- [ ] T056 `src/qello_knowledge/sources/config.py`: 토큰 판정을 contracts/sources-config.md "토큰 형식 판단"대로 바꾼다(알려진 접두사에 `cfat_` 추가, `postgres` 스킴 URL, 레지스트리 형식 규칙은 토큰 판정에 쓰지 않음). 비활성 자료원에도 토큰 검사를 적용한다. 레지스트리는 `auth` 이름 검사에만 쓴다. T054·T055 통과
- [ ] T057 [P] `tests/unit/sources/test_session_hosts.py`와 시나리오(`tests/fixtures/responses/fake/redirect_http_downgrade.json`, `redirect_port_change.json`): 같은 호스트의 `http` 리다이렉트와 포트가 바뀌는 리다이렉트는 `REDIRECT_BLOCKED`이고 그 주소로 요청 0건(인증 헤더 전달 없음), 첫 요청이 `http`이거나 `allowed_hosts` 밖 호스트면 `HostNotAllowed`가 나고 전송 기록 요청 0건, `fetch_contents`가 `HostNotAllowed`를 자료별 결과로 삼키지 않음
- [ ] T058 `src/qello_knowledge/domain/source.py`에 `HostNotAllowed` 예외를 더하고 `src/qello_knowledge/sources/session.py`에 research.md R-09 보강 규칙(첫 요청 `https`·호스트 검사, 리다이렉트 `https`·호스트·포트 검사)을 넣는다. `src/qello_knowledge/sources/collect.py`는 `HostNotAllowed`를 잡지 않는다. 기존 테스트가 쓰는 설정의 `allowed_hosts`가 새 규칙에 맞는지 확인한다. T057 통과
- [ ] T059 `uv run pytest tests/unit tests/contract`와 `uv run ruff check .`, `uv run ruff format --check .`로 확인. 파일 basename이 기존 테스트와 겹치지 않는지 확인

---

## Dependencies & Execution Order

- Setup(T001~T003) → Foundational(T004~T013) → US1 → US2 → US3 → US4 → SC-001 확인 → Polish
- US1의 세션(T019)과 목록 순회(T020)를 US3(T037)·US4(T045·T046)가 넓힌다. 그래서 US3·US4는 US1 뒤에 한다
- US2는 US1과 독립이다(설정·명령줄만). US1과 병렬로 할 수 있다
- US4의 리다이렉트 검사(T045)는 US2의 `allowed_hosts`(T028)를 쓴다
- Phase 7은 모든 스토리가 끝난 뒤 한다. 최종 계약에 대해 "계약 밖 변경 0줄"을 확인하기 위해서다
- 같은 스토리 안에서는 테스트를 먼저 쓰고 실패를 확인한 뒤 구현한다

## Parallel Examples

- Foundational: T004·T005·T010·T011·T012를 함께 쓴 뒤 T006 → T007 → T008 → T009, T013
- US1: T014~T018을 함께 쓴 뒤 T019 → T020 → T021
- US2: T023~T026을 함께 쓴 뒤 T027 → T028 → T029 → T030. US1 구현과 병렬 가능
- US3: T031~T034를 함께 쓴 뒤 T035·T036 → T037
- US4: T038~T042를 함께 쓴 뒤 T043·T044 → T045 → T046

## Implementation Strategy

1. MVP: Setup → Foundational → US1. 계약, 가짜 어댑터, 공통 계약 시험이 동작하면 QK-SEC-001·QK-CHK-002가 가짜 어댑터로 시험을 시작할 수 있다
2. US2로 설정과 명령줄을 붙인다. QK-ING-002가 첫 실제 자료원을 `config/sources.toml`에 추가할 수 있게 된다
3. US3·US4로 한도·재시도·실패 격리를 세션에 더한다
4. Phase 7을 별도 커밋으로 남겨 SC-001을 증빙한다
5. 커밋은 단계별로 나눈다(`/harness-commit`): 공통 형식·경계, 계약·가짜 어댑터, 자료원 설정·명령줄, 호출 한도, 재시도·실패 격리, 두 번째 가짜 어댑터
