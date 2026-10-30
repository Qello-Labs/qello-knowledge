---
description: "QK-OBS-001 구현 작업 목록"
---

# Tasks: QK-OBS-001 질의 로그, 👍/👎 피드백, `/sources`, 질의 원문 저장 옵션

**Input**: `specs/QK-OBS-001-query-log-feedback/`의 plan.md, spec.md(FR-001~024, SC-001~012), research.md(R-01~R-16), data-model.md, contracts/(2개), quickstart.md

**Tests**: 포함한다. C-12(수용 기준은 검증으로 닫는다)와 spec SC가 자동 시험을 요구한다. 시험을 먼저 쓰고 실패를 확인한 뒤 구현한다.
모든 시험은 외부 호출 0건이다(가짜 Discord 수신부·가짜 검색·생성 제공자·시험 서명 키, 0 Neurons). 실제 Discord 확인은 맨 끝 "사람 단계"다.

**Organization**: 사용자 스토리별 단계다. 순서는 P1(US1 → US2 → US3) 다음 P2(US4 → US5) 다음 P3(US6)다. 공통 타입·설정·저장 구조·기록기·해석·중계 변경은 Phase 2에 모은다.

**선행 조건**:
- spec.md 승인(2026-10-29, 검토 반영 변경 FR-017·SC-004·FR-008 포함), plan.md 승인(2026-10-29)
- 이 목록의 사람 승인, `TASK.md` Scope·Validation·완료 조건 갱신(AGENTS.md 1절)
- 단계 게이트 1.G 미완료 상태의 진행은 2026-10-29 사용자 결정(TASK.md)

**공통 규칙**:
- 비노출: 질문 원문·답변 본문·청크 본문·출처 제목·링크·Discord 사용자·채널·서버 식별자·이름·상호작용 토큰·자격 정보를 운영 로그·예외 문구·CLI 출력(`export` 파일의 질문 제외)에 넣지 않는다(spec FR-002·FR-011, R-14).
- 합성 값만: 시험의 Discord 식별자는 `100000000000000001` 같은 합성 숫자, 질문은 `합성 질문 1` 같은 값이다. 비밀값 모양 문자열은 `tests/unit/synthetic_secrets.py` 도우미로 실행 중에 만든다.
- 통과 방식: 시험을 지우거나 `skip`·`xfail`로 통과시키지 않는다. 경고를 suppress하지 않는다. 새 `# noqa`가 필요하면 멈추고 사람에게 묻는다.
- 기존 시험: 기대값을 바꾸지 않고 사례를 **더하기만** 한다. 예외는 하나다:
  - `tests/unit/query/test_bot_register_commands.py`의 `bot_expected_commands()`에 `/sources` 항목 하나를 더한다(spec FR-017, `/ask` 항목은 그대로). 구현 전에 사람 허용을 받는다(T024).
  - (2026-10-29 구현 중 추가 허용) `tests/unit/discord/test_bot_domain.py` `:22`·`:62`·`:120` 목록에 새 멤버·필드 추가, `tests/unit/discord/test_bot_interactions.py:86`을 비노출 의도 유지 단언으로 바꾸기(TASK.md).
  - 그대로 통과해야 하는 것: `tests/unit/discord/`·`tests/unit/query/`·`tests/localdb/query/`의 `test_bot_*` 전부(기록 기능 기본 꺼짐), `workers/relay/relay.test.ts`의 `:61`·`:224-241`(R-09),
    `tests/unit/config/test_bot_settings_registry.py`, `tests/unit/test_boundaries.py` 기존 사례.
- 시험 파일 이름: 새 파일은 `test_obs_*.py`다(수집 이름 겹침 방지, 기존 `test_bot_*`와 구분).
- 경계: `domain`·`ports`는 표준 라이브러리만(`tests/unit/test_boundaries.py`). `discord/`는 외부 SDK·저장소를 가져오지 않는다. 새 dataclass 필드는 끝에 기본값과 함께 둔다.
- 꺼짐 불변: `QK_QUERY_LOG_ENABLED=false`(기본)에서 `/ask` 응답·전달 본문·운영 로그의 기존 키 값이 지금과 같다(spec FR-024, SC-011). 운영 로그 JSON에는 `record` 키 하나만 더해진다.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 다른 파일이고 미완료 작업에 기대지 않아 병렬로 할 수 있다.
- **[Story]**: 사용자 스토리(US1~US6). Setup·Foundational·Polish에는 없다.

---

## Phase 1: Setup

- [X] T001 시험 도우미 `tests/unit/query/obs_builders.py`: 합성 Discord 식별자 상수, 버튼 상호작용 본문 빌더(종류 3, `data.component_type=2`, `data.custom_id`, `member.user.id`, `member.roles`, `channel`, `guild_id`), `/sources` 명령 본문 빌더,
  가짜 `QueryLog`(포트 메서드별 결과·지연·예외 주입, 호출 기록), 가짜 단조 시계. 기존 `tests/unit/discord/bot_builders.py`·`tests/unit/query/bot_runtime.py`의 서명 도우미를 재사용하고 그 파일은 고치지 않는다.
- [X] T002 [P] 로컬 DB 도우미 `tests/localdb/query/obs_db.py`: 마이그레이션 적용 뒤 `qk_query` 역할로 `SET ROLE` 하는 연결 컨텍스트, 고정 질의 기록·평가·원문 넣기 도우미(관리 연결). 기존 `tests/localdb/query/conftest.py`는 고치지 않는다.

---

## Phase 2: Foundational (모든 스토리의 선행)

**시험 먼저**

- [X] T003 [P] 도메인 시험 `tests/unit/domain/test_obs_query_log.py`: `RecordStatus` 값이 정확히 `answered, cannot_confirm, retrieval_failed, generation_failed, outgoing_blocked, timed_out, not_started, failed, undelivered, busy`,
  `FeedbackValue` `up, down`, `ComponentAction` `up, down, keep, skip`, `QueryRecord`·`PendingQuestion`의 `repr`에 질문자 식별자·질문이 없음, `QueryDelivery.final_status` 기본 `None`,
  `Interaction`의 새 필드(`user_id` 기본 `None`, `repr`에 없음, `component_action`·`component_run_id` 기본 `None`)와 기존 위치 인자 생성 그대로, `RenderedReply.components` 기본 `()`,
  `QueryRunLog.record` 기본 `"off"`이고 `to_json`에 `record` 키가 더해지는 것 말고 기존 키·값이 같음(data-model 2절)
- [X] T004 [P] 버튼 값 시험 `tests/unit/discord/test_obs_components.py`: 만들기·해석 왕복, 정규식 `^qk1:(up|down|keep|skip):q-[0-9]{8}T[0-9]{6}-[0-9a-f]{8}$`(최대 35자), 틀린 접두사·동작·식별자·길이 거부,
  평가 버튼 꼴(액션 줄 1, 버튼 2, 스타일 2, 라벨 👍·👎), 동의 버튼 꼴(`keep` 스타일 1 "저장 동의", `skip` 스타일 2 "저장 안 함"), 동의 문구에 저장 대상·보관 기간(`<보존 상한 날짜>` 치환)·보는 사람·지우기 네 구분이 있음(contracts 1·3절)
- [X] T005 [P] 해석 시험 사례 `tests/unit/discord/test_obs_interactions.py`: 종류 3이 `COMPONENT`로 해석되고 `custom_id`가 동작·`run_id`로 나뉨, 형식이 틀리면 `component_action=None`, 서버 안 `member.user.id`가 `user_id`,
  DM·`member` 없음이면 `user_id=None`, 종류 2 `sources`가 `COMMAND`·`command="sources"`, 기존 `/ask` 해석 결과(같은 입력)가 지금과 같음
- [X] T006 [P] 설정 시험 `tests/unit/config/test_obs_settings.py`: data-model 1절 설정의 진입점·형식·기본값(`QK_QUERY_LOG_ENABLED` `false`, `QK_QUERY_PENDING_SECONDS` 60~3600 `3600`, `QK_QUERY_PENDING_MAX` 10~2000 `500`,
  `QK_QUERY_RECORD_TIMEOUT_MS` 100~1500 `1000`, `QK_DISCORD_COMPONENT_TIMEOUT_MS` 500~2000 `1500`, `QK_QUERY_TEXT_RETAIN_UNTIL` `YYYY-MM-DD` 또는 빈 값, `QK_RELAY_TIMEOUT_SECONDS`가 query 진입점에도 있음),
  교차 검사(켜짐 + 빈 날짜 오류, 날짜 < 오늘(UTC) 경고, 첫 응답 상한 ≥ 중계 제한 × 1000 오류, `/sources` 줄 길이 130 × 등록 자료원 수 + 머리글 > 2,000 경고), 오류·경고 문구에 값 원문 없음
- [X] T007 [P] 마이그레이션 시험 `tests/localdb/query/test_obs_migration.py`: `0008` 적용 뒤 두 번째 `qk-migrate`가 `applied=0`, 표 넷의 열·제약(data-model 3.1: `run_id` 정규식, `questioner_id`·`rater_id` `^[0-9]{17,20}$`, `value IN ('up','down')`,
  `question` 1~4000자, `consent_method = 'feedback_down'`, `UNIQUE (run_id, rater_id)`), DEFINER 함수 여섯의 `prosecdef`, `proconfig`의 `search_path=qk, pg_temp`, 소유자, `PUBLIC` 실행 권한 없음,
  `qk_query`의 네 표 직접 권한 없음과 `qk` 스키마 `CREATE` 없음, `qk.sources_summary`는 INVOKER, 0001~0007 객체 정의 불변
- [X] T008 [P] 질의 역할 권한 시험 `tests/localdb/query/test_obs_query_role.py`: `qk_query`로 네 표 `SELECT`·`DELETE`·`UPDATE`, 직접 `INSERT`, 색인 표 쓰기가 모두 거부되고(spec SC-007), 함수 여섯과 `sources_summary`는 성공.
  `query_record_insert`가 모르는 키·중첩 모르는 키·형식이 틀린 값·형식이 틀린 문자열 항목(64자 초과, `[A-Za-z0-9@/._:+-]` 밖)을 버리거나 NULL로 넣음, 같은 `run_id` 두 번 넣기가 한 행(data-model 3.2)
- [X] T009 [P] 어댑터 시험 `tests/localdb/query/test_obs_adapter.py`: `PostgresQueryLog`의 각 메서드 결과(`feedback` `stored`/`missing`, `store_question` `stored`/`exists`/`missing`/`not_questioner`, `question_status` 네 값, `delivered`의
  `final_status=undelivered`만 상태 변경), 문장 지연 주입 시 `statement_timeout` 취소로 저장 0건과 `timeout` 결과, 연결 끊김 뒤 다음 호출에서 다시 연결, 제약 위반 예외가 종류 이름(`rejected`)으로만 올라오고 문구에 입력 값 없음
- [X] T010 [P] 기록기 시험 `tests/unit/query/test_obs_recorder.py`(가짜 포트·가짜 시계): 앞 길·뒤 길이 서로 기다리지 않음(뒤 길을 막아도 앞 길 응답), 앞 길 절대 마감, 남은 시간 ≤ 300 ms(여유 200 + 최소 실행 100) 작업은 실행하지 않고 버림 → `timeout`,
  문장 제한 = 남은 시간 − 200 ms(≥ 100 ms)로 포트에 넘김, 뒤 길 `insert` 대기 상한(`QK_QUERY_RECORD_TIMEOUT_MS`) 초과 시 `timeout`을 돌려주고 작업은 뒤에서 끝남, 예외 문구를 버리고 종류만 돌려줌, 종료 시 스레드 정리
- [X] T011 [P] 중계 시험 사례 추가 `workers/relay/relay.test.ts`: 원본 종류 3 + 콜백 7·4 통과, 원본 종류 3·종류 2 `sources`의 실패·시간 초과 대체 문구가 "지금은 처리할 수 없습니다. 잠시 후 다시 시도해 주세요.",
  원본 종류 2(`ask`·이름 없음) + 콜백 7은 지금처럼 대체 응답. 기존 사례(`:61`, `:224-241`)는 고치지 않는다

**구현**

- [X] T012 `src/qello_knowledge/domain/query_log.py`(새): data-model 2.2 타입. `src/qello_knowledge/domain/discord.py`: `InteractionKind.COMPONENT`, `Interaction.user_id`·`component_action`·`component_run_id`, `RenderedReply.components`, `QueryRunLog.record`(추가만)
- [X] T013 [P] `src/qello_knowledge/ports/query_log.py`(새): `QueryLog` 포트(data-model 2.3, `question_status` 포함). `tests/unit/test_boundaries.py`에 새 모듈이 경계 검사 대상인지 확인하는 사례 추가
- [X] T014 [P] `src/qello_knowledge/discord/components.py`(새): `custom_id` 만들기·해석, 평가·동의 버튼 꼴, 동의 문구(contracts 1·3절). `src/qello_knowledge/discord/notices.py`: 버튼·`/sources` 안내 문구 추가(contracts 2·4절, 기존 문구 불변)
- [X] T015 `src/qello_knowledge/discord/interactions.py`: 종류 3과 `sources` 해석, `member.user.id`(T005). 기존 `/ask` 분기 결과 불변
- [X] T016 [P] `src/qello_knowledge/config/registry.py`·`config/check.py`: 설정과 교차 검사(T006). 뒤에 `uv run python -m qello_knowledge.config.example`로 `.env.example`을 다시 만든다(내용을 열지 않는다)
- [X] T017 `src/qello_knowledge/adapters/postgres/migrations/0008_query_log.sql`: 표 넷(data-model 3.1, 색인 표 외래 키 없음), DEFINER 함수 여섯(`query_record_insert`, `query_record_delivered`, `query_feedback_set`, `query_text_store`, `query_text_skip`,
  `query_text_status`)과 INVOKER `sources_summary`(research R-11: 활성 인덱스의 `qk.is_visible` 통과 청크가 있는 문서를 `coalesce(source_name, source_kind)`별로 묶어 종류·문서 수·`max(coalesce(last_seen_at, collected_at))`, 이름순),
  같은 트랜잭션에서 `CREATE` → `REVOKE ALL … FROM PUBLIC` → `GRANT EXECUTE … TO qk_query`. 기존 마이그레이션은 고치지 않는다(T007·T008)
- [X] T018 `src/qello_knowledge/adapters/postgres/query_log.py`(새): `PostgresQueryLog`(자동 커밋, 함수 호출 한 문장, 호출마다 `SET statement_timeout`, `connect_timeout`, 예외 종류화)(T009)
- [X] T019 `src/qello_knowledge/query/recorder.py`(새): `QueryRecorder` 앞 길·뒤 길(research R-04)(T010). 기록 기능 꺼짐이면 앞 길만 만든다
- [X] T020 `workers/relay/relay.ts`: 원본 종류별 응답 허용 목록과 대체 문구(research R-09, contracts 5절)(T011)

**Checkpoint**: Phase 2 시험이 통과하고 기존 `test_bot_*`·중계 기존 사례가 그대로 통과한다.

---

## Phase 3: User Story 1 - 모든 `/ask`가 원문 없는 질의 기록으로 남는다 (Priority: P1) 🎯 MVP

**Goal**: 허용 범위 안 `/ask`마다 질의 기록 한 건(spec FR-001~005).

**Independent Test**: 가짜 검색·생성 제공자 + 가짜 `QueryLog`로 FR-002 표의 상태를 하나씩 만들고 기록 건수·항목을 본다. 로컬 DB 왕복은 T025.

- [X] T021 [P] [US1] 시험 `tests/unit/query/test_obs_query_record.py`: FR-002 표의 "남긴다" 상태마다 `insert` 한 번(비밀값 차단 `outgoing_blocked`, 대기열 가득 `busy` 포함), "남기지 않는다"(서명 오류, 허용 범위 밖, 지원하지 않는 요청, 재전송) 0번,
  항목이 FR-001대로(Context 청크 식별자 순서, 묶음 크기 합 = 청크 수, 인용 묶음 순번 1부터, 인덱스 버전, 모델·프롬프트 버전, 토큰, 질문자 식별자), 금지 항목 없음(SC-002),
  `insert`가 전달 전에 호출되고 대기 상한 초과·실패여도 답변 전달 본문이 같음(SC-005), 전달 실패 뒤 `delivered(final_status=undelivered)`(R-04, data-model `QueryDelivery`), 운영 로그 `record` 값, 꺼짐이면 `insert` 0번·`record=off`
- [X] T022 [US1] `src/qello_knowledge/query/pipeline.py`: `QueryReply`에 `context_chunk_ids`, `context_block_sizes`, `cited_blocks`, `index_version`, `model_id`, `prompt_version`, `input_tokens`, `output_tokens`(기본값 있는 끝 필드)를 채운다.
  인용 순번은 `GenerationResult.citations`의 `source_id`를 Context 묶음 순서에 대응시켜 만들고 경로는 남기지 않는다(research R-06)
- [X] T023 [US1] `src/qello_knowledge/query/jobs.py`·`query/app.py`·`query/server.py`: `_send`에서 전달 전 `insert`(상한 대기), 전달 뒤 `delivered`, 첫 응답에서 끝나는 `/ask`(비밀값 차단·대기열 가득·예상 밖 실패)는 기다리지 않고 `insert`,
  `QueryRunLog.record` 채우기, `create_app`에서 기록기 조립(T021)
- [X] T024 [US1] 사람 허용 확인(2026-10-29 사용자 허용, TASK.md): `tests/unit/query/test_bot_register_commands.py`의 `bot_expected_commands()`에 `/sources` 항목을 더하는 기존 시험 기대값 변경(공통 규칙 예외). 허용을 `TASK.md` Decisions에 적은 뒤 T040에서 반영한다
- [X] T025 [P] [US1] 로컬 DB 왕복 `tests/localdb/query/test_obs_record_roundtrip.py`: 질의 경로(가짜 제공자) → 기록기 → `qk_query` 연결로 저장 → 관리 연결로 읽어 FR-001 항목과 금지 항목 없음 확인, 전달 실패 뒤 상태 `undelivered`(SC-001·SC-002)

**Checkpoint**: 기록 기능을 켜면 `/ask`마다 기록 한 건, 꺼짐에서 기존 시험 그대로.

---

## Phase 4: User Story 2 - 답변에 👍/👎를 눌러 평가한다 (Priority: P1)

**Goal**: 평가 버튼과 버튼 상호작용 처리(spec FR-006~010).

**Independent Test**: 서명한 가짜 버튼 상호작용을 `DiscordApp.respond`에 넣고 응답 꼴·저장 호출을 본다.

- [X] T026 [P] [US2] 시험 `tests/unit/query/test_obs_feedback.py`: 결과 상태 `answered`·`cannot_confirm`일 때만 마지막 메시지 전송 본문에 `components`(contracts 1절), 실패·안내·시간 초과에는 없음, 분할된 답변은 마지막 메시지에만,
  본문 `content`·메시지 수가 버튼 없을 때와 같음, 꺼짐이면 없음(FR-006)
- [X] T027 [P] [US2] 시험 `tests/unit/query/test_obs_feedback_flow.py`: contracts 2절 1~5행과 3a행 — 허용 범위 밖, 형식 틀림·`user_id` 없음·꺼짐, `missing`, 결과 불명(실패·상한 초과·버린 작업) → "저장 여부를 확인하지 못했습니다. 다시 눌러 주세요.",
  `stored` → "평가를 남겼습니다.", 값 바꾸기·여러 평가자·재전송에서 평가자·질의마다 하나, 응답이 모두 콜백 4 `flags: 64`·`allowed_mentions` 비움, 검색·생성·Discord 후속 호출 0건, 운영 로그 한 줄에 식별자 없음(SC-004)
- [X] T028 [US2] `src/qello_knowledge/adapters/discord/webhook.py`: `RenderedReply.components`가 있으면 마지막 메시지 `body`에 넣는다(`:224`). 없으면 지금 본문 그대로(T026)
- [X] T029 [US2] `src/qello_knowledge/query/jobs.py`: `_claim`에서 결과 상태·기록 기능을 보고 평가 버튼을 붙인 `RenderedReply`를 만든다(T026)
- [X] T030 [US2] `src/qello_knowledge/query/app.py`: `COMPONENT` 분기(서명 검사 → 해석 → `AccessPolicy` → 버튼 값 → 앞 길 `feedback` → 응답), BOT-001 FR-007 예외(첫 응답 안 저장소 호출) 주석(T027)
- [X] T031 [P] [US2] 로컬 DB 시험 `tests/localdb/query/test_obs_feedback_db.py`: 문장 지연 주입 시 저장 0건과 불명 안내, 커밋 뒤 반환 지연 주입 시 불명 안내 → 다시 누름 → "평가를 남겼습니다."·행 하나(SC-004, research R-04)

**Checkpoint**: 공개·"나만 보기" 답변 모두 평가가 남고, 상한 초과에서 부분 저장 없음.

---

## Phase 5: User Story 3 - 👎 사례 중 질문자가 동의한 질문만 남는다 (Priority: P1)

**Goal**: 원문 대기와 동의 흐름(spec FR-011~013).

**Independent Test**: 가짜 시계·가짜 `QueryLog`로 contracts 2절 5~13행의 조합을 하나씩 만들고 안내·저장 호출·대기 상태를 본다.

- [X] T032 [P] [US3] 시험 `tests/unit/query/test_obs_pending.py`: `PendingQuestions` 넣기 조건(결과 상태 `answered`·`cannot_confirm`, 켜짐, 보존 상한 날짜 ≥ 오늘(UTC), 질문자 식별자 있음), 대기 시간(기본 3600초)·대기 수 상한(기본 500, 만료가 이른 것부터 버림),
  요청 없이 감시 주기만으로 만료 뒤 질문 참조 삭제, 종료 시 전부 삭제, 상태 전이 `waiting`·`uncertain` → `claimed` → `chosen`/`uncertain`(research R-07, data-model 4절), `claimed` 중 다른 선점 실패, 처리 중 만료된 대기를 다시 만들지 않음,
  `repr`·예외 문구에 질문 없음
- [X] T033 [P] [US3] 시험 `tests/unit/query/test_obs_consent_flow.py`: contracts 2절 5~13행을 평가 순서(6행 먼저, 행 번호순 첫 일치)와 선점 전 상태 기준으로 한 행씩 — 질문자 👎 + 대기 → 동의 질문(문구·버튼), 질문자 아님 → 6행 또는 13행 `not_questioner`,
  `claimed` → 7행, `waiting`·`uncertain` + `keep` → 8~11행(비밀값 재검사 → `query_text_skip`, `stored`/`exists`, `missing`/`not_questioner`, 결과 불명 → `uncertain`), `waiting` + `skip` → 12행,
  `uncertain` + `skip`·`chosen`·없음 → 13행 `question_status` 결과별 안내와 조회 불명 → `uncertain` 복원, 보존 상한 날짜 경과 뒤 묻지 않음, 동시 `keep`·`skip`에서 하나만 처리(SC-003, spec US3-1~11)
- [X] T034 [US3] `src/qello_knowledge/query/pending.py`(새): `PendingQuestions`(T032). `src/qello_knowledge/query/jobs.py`: `_claim`에서 대기 넣기, `_watch` 주기 정리, `close` 전부 삭제
- [X] T035 [US3] `src/qello_knowledge/query/app.py`: `down` 처리 뒤 동의 질문 붙이기, `keep`·`skip` 처리(선점, 저장 직전 `security_outgoing_check` 재검사, 앞 길 `store_question`·`mark_text_skipped`·`question_status`, 콜백 7 응답)(T033)
- [X] T036 [P] [US3] 로컬 DB 시험 `tests/localdb/query/test_obs_consent_db.py`: 동의 저장 왕복(원문 기록 한 건, 질의 기록 `consented=true`, 답변 본문 없음), 질문자 불일치 거부, `exists`, `question_status` 네 값, 커밋 뒤 반환 지연 → 불명 → 다시 `keep`·`skip`·만료 뒤 누름의 안내가 실제 원문 유무와 일치(SC-003)

**Checkpoint**: P1 완료. 기록·평가·동의가 켜짐에서 동작하고 원문은 동의한 질문만.

---

## Phase 6: User Story 4 - 팀원이 자기 기록을 지울 수 있다 (Priority: P2)

**Goal**: `qk-index queries erase-user`·`erase-texts`(spec FR-013~015).

**Independent Test**: 로컬 DB에 두 팀원의 기록을 넣고 명령을 실행한다.

- [X] T037 [P] [US4] 시험 `tests/localdb/query/test_obs_erase.py`: `erase-user`가 식별자를 표준 입력 한 줄로만 받음(17~20자리 아니면 종료 코드 2), `--confirm` 없으면 세 건수만·변경 0, `--confirm`이면 data-model 3.3 한 트랜잭션·다른 사용자 불변·두 번째 실행 0,
  `erase-texts`가 원문 전체만 지우고 질의 기록·평가 수 불변, `qk.query_erasure_run`에 대상 식별자 없음, 출력·오류에 식별자·원문 없음, 원문 대기 안내 문장 출력(SC-006·SC-008, contracts/cli.md)
- [X] T038 [US4] `src/qello_knowledge/adapters/postgres/query_log_admin.py`(새): 지우기·건수(관리 연결). `src/qello_knowledge/indexer/queries_cli.py`(새)와 `indexer/cli.py`의 `queries` 하위 명령(`erase-user`, `erase-texts`)(T037)

---

## Phase 7: User Story 5 - `/sources`로 봇이 아는 자료와 그 기준 시각을 본다 (Priority: P2)

**Goal**: `/sources` 명령(spec FR-016~017).

**Independent Test**: 로컬 DB의 활성·비활성 인덱스와 보이는·숨긴 문서로 조회 함수와 응답을 본다.

- [X] T039 [P] [US5] 시험 `tests/unit/discord/test_obs_sources.py`: `SourcesView` 렌더링(contracts 4절 머리글·줄 꼴, KST, 종류 표시 대응, `neutralize`), 2,000자 초과 시 줄 단위로 자르고 "(자료원 N개 더 있음)"(spec FR-017), 활성 인덱스 없음 안내,
  허용 범위 밖·저장소 실패·상한 초과 안내, 기록 기능 꺼짐에서도 동작, 질의 기록 0건(SC-010)
- [X] T040 [US5] `src/qello_knowledge/discord/sources.py`(새) 렌더링, `query/app.py` `sources` 분기(앞 길 `sources()`), `query/server.py` `register-commands`에 `/sources` 추가(contracts 4절), `tests/unit/query/test_bot_register_commands.py` 기대값 변경(T024 허용 뒤)(T039)
- [X] T041 [P] [US5] 로컬 DB 시험 `tests/localdb/query/test_obs_sources_db.py`: `qk.sources_summary`가 보이는 문서가 있는 자료원만, 문서 수는 `qk.is_visible` 통과만, 마지막 확인 시각 = `max(coalesce(last_seen_at, collected_at))`, 숨긴 문서 제목·경로 없음, 활성 인덱스 없음(SC-010)

---

## Phase 8: User Story 6 - 운영 담당자가 파일럿 수치와 👎 사례를 뽑는다 (Priority: P3)

**Goal**: `qk-index queries report`·`export`(spec FR-018~019).

**Independent Test**: 로컬 DB 고정 기록으로 출력과 기대값을 비교한다.

- [X] T042 [P] [US6] 시험 `tests/localdb/query/test_obs_report.py`: 고정 기록의 건수·상태·실패 종류별 건수, `first_response_ms`·`total_ms` p50·p95, 비율, 👍/👎·식별자 없는 평가 수, 동의 수, Neurons(측정·추정), 하루 사용량, 인덱스·모델·프롬프트 분포가
  손으로 계산한 기대값과 같음, `measurement_boundary`·`relay_failures_note` 문구, 보존 상한 날짜 경과 경고, 출력에 원문·식별자 없음(SC-009)
- [X] T043 [P] [US6] 시험 `tests/localdb/query/test_obs_export.py`: 기본 👎만·`--all`, JSON Lines 항목(contracts/cli.md), 식별자·답변·출처 없음, `--out`이 저장소 작업 트리 안이면 2, 기존 파일 덮어쓰지 않음, 파일 권한 `0600`, 표준 출력 안내 문장(SC-002)
- [X] T044 [US6] `adapters/postgres/query_log_admin.py`·`indexer/queries_cli.py`: `report`, `export`(T042·T043)

---

## Phase 9: Polish & Cross-Cutting

- [X] T045 [P] 비노출 점검 시험 `tests/unit/query/test_obs_no_raw_logs.py`: 기록·버튼·동의·`/sources`·명령의 실패 주입 전체에서 운영 로그·예외 문구·CLI 출력에 질문·답변·식별자·토큰이 0건(caplog, 표준 오류, 예외 메시지)(SC-002)
- [X] T046 [P] 꺼짐 불변 회귀 `tests/unit/query/test_obs_disabled.py`: 기본 설정에서 `/ask` 첫 응답·전달 본문·운영 로그 기존 키가 기록 기능 추가 전과 같음, 버튼 0, 대기 0, `/sources`는 동작(SC-011)
- [X] T047 기존 시험 회귀: 기존 시험 전체를 돌려 기대값 변경이 T040의 허용된 한 곳뿐인지 `git diff`로 확인한다
- [X] T048 [P] 운영 문서 `docs/ops/oci-production-store.md`: `0008` 적용·함수 소유자 확인, `LimitCORE=0`, 스왑 확인, 기록 기능 켜기·되돌리기, `/sources` 등록, 중계 재배포(quickstart 3절). 주소·식별자·토큰 없음
- [X] T049 [P] `specs/QK-OBS-001-query-log-feedback/quickstart.md`의 시험 파일 이름을 실제와 맞춘다
- [X] T050 기본 검증(quickstart 1절): `uv run python scripts/preflight.py`, `git diff --check`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run qk-dev db up`, `uv run qk-migrate`(두 번, 두 번째 `applied=0`),
  `QK_REQUIRE_LOCALDB=1 uv run pytest`, `node --test workers/relay/relay.test.ts`. 결과를 TASK.md에 기록한다
- [X] T051 `TASK.md` Decisions·검증 기록 갱신, `/pr-draft-summary`로 PR 초안(CLAUDE.md 의무 사용). 최종 보고에 `index_version`(변경 없음), `embedding_model`(변경 없음), `chunking_version`(변경 없음),
  `eval_set_version`(해당 없음, 사유), `metrics_with_sample_size`(해당 없음), `estimated_or_used_neurons`(0)를 넣는다

---

## 사람 단계 (구현 뒤, 이 작업의 완료 조건 밖)

- [ ] H01 ADR-016 리뷰·승인, Discord 공지와 Confluence 동의 문서 작성, 링크·날짜를 ADR-016 Follow-ups에 기록(spec FR-024).
- [ ] H02 운영 반영(quickstart 3절, 명령마다 승인): `0008` 적용·함수 소유자 확인, `LimitCORE=0`·스왑 확인, 질의 서비스 배포(꺼짐), 중계 재배포, `/sources` 등록, 보존 상한 날짜를 정해 기록 기능 켜기.
- [ ] H03 운영 확인(spec SC-012, quickstart 4절): 예상 약 255 Neurons 이하 보고·승인 뒤 M-01~M-03. 콜백 7로 동의 버튼이 사라지는지(research R-01 미확인) 화면으로 확인.

---

## Dependencies & Execution Order

- **단계 순서**: Phase 1 → Phase 2 → US1(Phase 3) → US2(Phase 4) → US3(Phase 5) → US4(Phase 6) → US5(Phase 7) → US6(Phase 8) → Polish(Phase 9) → 사람 단계.
- **스토리 사이 의존**:
  - US2는 US1의 질의 기록(버튼이 기록을 찾음)에, US3은 US2의 👎 처리에 기댄다.
  - US4·US6은 US1~US3의 표에 기대지만 Phase 2 마이그레이션 뒤 시험 자료로 따로 할 수 있다.
  - US5는 Phase 2 뒤 언제든 할 수 있다(`/sources`는 기록 기능과 무관).
- **같은 파일 작업 순서**:
  - `query/app.py`: T023 → T030 → T035 → T040
  - `query/jobs.py`: T023 → T029 → T034
  - `query/server.py`: T023 → T040
  - `adapters/postgres/query_log_admin.py`·`indexer/queries_cli.py`: T038 → T044
  - `domain/discord.py`: T012 뿐, `discord/notices.py`: T014 뿐
- **TDD**: 각 단계의 시험 작업을 먼저 쓰고 실패를 확인한 뒤 구현한다.

## Parallel Opportunities

- **Phase 2**: 시험 T003~T011을 병렬로 쓴다. 구현은 T012 → (T013·T014·T016 병렬) → T015, T017 → T018 → T019, T020은 따로.
- **스토리 안**: 시험 작업([P])은 서로 병렬이다. US1 T021·T025, US2 T026·T027·T031, US3 T032·T033·T036, US6 T042·T043.
- **스토리 사이**: US5(T039~T041)는 US1~US4와 병렬로 할 수 있다(다른 파일, `query/app.py`만 순서를 지킨다).
- **Polish**: T045·T046·T048·T049는 병렬이고 T047 → T050 → T051이 마지막이다.

## Implementation Strategy

1. **MVP = Phase 1~3(US1)**: 기록 기능을 켜면 `/ask`마다 원문 없는 기록이 쌓인다. 파일럿 지연·건수 측정의 최소 단위다. 기본 꺼짐이라 운영 영향이 없다.
2. **P1 마무리**: US2로 평가 버튼, US3로 👎 동의와 질문 저장을 더한다.
3. **P2·P3**: US4 지우기(파일럿 전 필수), US5 `/sources`, US6 집계·내보내기.
4. **마무리**: Polish(비노출, 꺼짐 불변, 회귀, 운영 문서, 기본 검증, PR 초안). 사람 단계 H01~H03은 구현 뒤 사람이 한다.

## 구현 기록

- 2026-10-29 Phase 1: T001·T002 도우미 import·합성 입력 smoke 검증 통과. 기존 단위 회귀 393 passed. 기존 변경 보존.
- 실행 절차: 사용자 지시대로 현재 브랜치에서 직접 구현하며 git 상태 변경·별도 작업 트리·커밋·PR 초안은 하지 않는다. 진행 ledger는 이 절로 한정한다.
- DB 명령은 `.env` 비읽기와 로컬 대상 고정을 위해 `--env-file /dev/null`을 쓴다. 실제 외부 호출 0건, 0 Neurons.

- 2026-10-29 Phase 2 **BLOCKED**: T003~T011 시험을 추가하고 RED를 확인한 뒤 T012~T020 공통 구현을 진행했다. 새 단위 시험 29 passed, 새 로컬 DB 시험 6 passed, 중계 15 passed(기존 사례 포함). 시험 작업의 모든 세부 사례는 아직 구현하지 않았으며 Phase 2 완료 체크는 하지 않는다.
- 차단 증거: 기존 단위 회귀 418 passed / 4 failed. `test_bot_domain.py`의 `test_bot_enums`(22행), `test_bot_interaction_fields_and_hidden_content`(62행), `test_bot_run_log_exact_fields_stable_single_line_and_immutable`(120행), `test_bot_interactions.py`의 `test_bot_user_fields_are_ignored_and_body_boundary`(86행). 모두 T012·T015의 새 enum/필드와 기존 시험의 정확한 필드 목록·속성 부재 요구가 충돌한다. 기존 기대값은 수정하지 않았다.
- 차단 재현: `uv run pytest tests/unit/discord/test_bot_domain.py tests/unit/discord/test_bot_interactions.py tests/unit/test_boundaries.py -q --tb=short` → 85 passed / 4 failed. `git diff --check` 통과. T021 이후 구현 및 T050 전체 검증은 진행하지 않았다. T051은 현재 차단 상태를 TASK.md에 기록하는 부분만 수행한다(PR 초안 없음).
- 계획과 다른 점: `RenderedReply.components`는 상속 타입 `QueryReply`의 기존 위치 인자 순서를 보존하려고 키워드 전용 기본 필드로 추가했다. 로컬 postgres의 SET ROLE 권한은 기존 시험 방식처럼 롤백 트랜잭션 안의 임시 멤버십으로 처리한다. 기존 시험 자체는 바꾸지 않았다.
- 재개에 필요한 사람 결정: 위 기존 시험 네 사례에서 승인된 enum·필드·record 추가에 한해 기대값 변경을 허용하고 TASK.md Scope 예외를 갱신할지, 또는 spec·plan의 타입 계약을 다시 정할지 결정해야 한다. 현재 작업 트리는 부분 구현이며 병합·운영 사용 대상이 아니다. 같은 세션의 자기 검증이며 독립 검토·승인이 아니다.

이번 실행의 changed_files (27개, 시작 전 변경 파일 중 ADR-016·다른 명세 산출물은 수정하지 않음):

- `.env.example`
- `TASK.md`
- `specs/QK-OBS-001-query-log-feedback/tasks.md`
- `src/qello_knowledge/config/check.py`
- `src/qello_knowledge/config/registry.py`
- `src/qello_knowledge/discord/interactions.py`
- `src/qello_knowledge/discord/notices.py`
- `src/qello_knowledge/domain/discord.py`
- `tests/unit/test_boundaries.py`
- `workers/relay/relay.test.ts`
- `workers/relay/relay.ts`
- `src/qello_knowledge/adapters/postgres/migrations/0008_query_log.sql`
- `src/qello_knowledge/adapters/postgres/query_log.py`
- `src/qello_knowledge/discord/components.py`
- `src/qello_knowledge/domain/query_log.py`
- `src/qello_knowledge/ports/query_log.py`
- `src/qello_knowledge/query/recorder.py`
- `tests/localdb/query/obs_db.py`
- `tests/localdb/query/test_obs_adapter.py`
- `tests/localdb/query/test_obs_migration.py`
- `tests/localdb/query/test_obs_query_role.py`
- `tests/unit/config/test_obs_settings.py`
- `tests/unit/discord/test_obs_components.py`
- `tests/unit/discord/test_obs_interactions.py`
- `tests/unit/domain/test_obs_query_log.py`
- `tests/unit/query/obs_builders.py`
- `tests/unit/query/test_obs_recorder.py`

- 2026-10-29 재개: 사용자 허용 네 곳의 기대값만 갱신했다. localdb 두 모듈 재현 결과 5 passed. 앞선 실패 원인은 PUBLIC ACL 검사에서 소유자 항목까지 맞춘 문자열 검사와 로컬 비슈퍼유저의 SET ROLE 권한이었으며, 이전 실행에서 ACL 항목별 검사·롤백 가능한 임시 멤버십으로 이미 수정됐다. 0001~0007 변경 없음.

- 2026-10-29 Phase 2: 기존 포함 단위·localdb 공통 묶음 273 passed. 생성 지연 뒤 앞 길 마감 재검사 RED→GREEN, 새 제약·문장 취소·메타데이터 허용 목록 사례 추가. 기록기 내부 `set_deadline`은 연결이 늦어진 뒤에도 늦은 저장을 시작하지 않도록 어댑터에 절대 마감을 전달한다(포트의 업무 계약은 불변).

- 2026-10-29 Phase 3: 상태별 기록·즉시 응답·Context 순번·권한 연결 왕복을 추가했다.`QK_REQUIRE_LOCALDB=1 uv run pytest tests/unit/query tests/unit/discord tests/localdb/query -q --tb=short` → 454 passed。기존 기대값 추가 변경 없음.

- 2026-10-29 Phase 4: `QK_REQUIRE_LOCALDB=1 uv run pytest tests/unit/query tests/unit/discord tests/localdb/query -q --tb=short` → 475 passed. 마지막 메시지 버튼·허용 범위·결과 불명·여러 평가자·재시도 멱등 검증 통과.

- 2026-10-29 Phase 5: `QK_REQUIRE_LOCALDB=1 uv run pytest tests/unit/query tests/unit/discord tests/localdb/query -q --tb=short` → 513 passed. 동의 전 상태별 처리·동시 선택·진행 중 만료·날짜 경계·문장 취소/커밋 후 반환 지연 뒤 재선택·만료/재시작 경로 검증 통과.

- 2026-10-29 Phase 6: 삭제 명령·기존 색인 단위 시험 묶음 90 passed. 식별자는 표준 입력만 받고 출력하지 않음, 확인·멱등·다른 사용자 보존·전체 원문 삭제 검증. 동의 저장과 삭제가 경합해도 원문이 남지 않도록 사용자 기록에 행 잠금을 먼저 건다(삭제 계약 순서 불변). queries 인자 오류는 입력을 되비추지 않는 전용 해석기로 처리한다.

- 2026-10-29 Phase 7: 단위·질의 localdb·기존 색인 묶음 611 passed. /sources 보이는 문서 수·마지막 확인 시각·KST·길이 제한·꺼짐 동작·등록 멱등 확인. T024 허용된 /sources 항목 하나만 기존 등록 기대값에 추가했다.

- 2026-10-29 Phase 8: report/export/erase localdb 묶음 10 passed. 고정 수치·분포·측정 경계·보존 경고, 저장소 밖 새 파일·0600·👎/전체·식별자 비노출 확인. query 수치의 누락된 버전은 보고 분포에서 unknown으로 센다.

- 2026-10-29 Phase 9(T045~T049): 로그·CLI 실패 원문 비노출, 꺼짐 불변, 기록 스레드 종료, 실제 보안 규칙 재검사, 감시 주기만의 만료 정리 검증. T047 전체 회귀는 3521 passed / 3 external deselected였으며 기존 기대값 변경은 사용자 허용 다섯 곳뿐임을 diff로 확인했다. 이후 표준 입력 실패·절대 마감 뒤 완료의 RED→GREEN을 추가했다. 운영 절차와 quickstart의 실제 시험 파일 이름을 갱신했다.
- 보완 사항: 즉시 거절된 요청의 재전송도 중복 기록하지 않으며, 질의 기록의 total_ms는 작업 예약 시점 대신 요청 수신 시점부터 잰다. 기존 검색·생성 마감은 바꾸지 않는다. 정리 실패와 표준 입력 오류도 입력 값을 버리고 종류만 출력한다.

- 2026-10-29 T050 **PASS(같은 세션의 자기 검증)**: `uv run python scripts/preflight.py` → 952개 파일 검사 통과, `git diff --check` → exit 0, `uv run ruff check .` → All checks passed, `uv run ruff format --check .` → 681 files already formatted.
- 로컬 DB: `COMPOSE_DISABLE_ENV_FILE=1 DATABASE_URL= QK_LOCAL_DB_PORT=54322 uv run qk-dev db up --env-file /dev/null` 성공. 같은 로컬 고정 환경에서 `uv run qk-migrate --env-file /dev/null` 첫 실행 → `apply 0008 query_log ok; applied=1 skipped=7`, 두 번째 → `applied=0 skipped=8`. `.env` 자동 로딩을 막고 운영 연결을 사용하지 않기 위한 실행 옵션이다.
- `QK_REQUIRE_LOCALDB=1 uv run pytest` → **3523 passed, 3 deselected, 66.45초**(제외된 3개는 기존 external 표식). `node --test workers/relay/relay.test.ts` → **15 passed, 0 failed, 0 skipped**. 최종 실패·차단 검사 없음. 기존 시험 기대값 변경은 사용자 허용 네 단언과 T024의 /sources 항목만이다. 0001~0007·보호 경로 변경 없음.
- T051은 사용자 범위대로 TASK.md Decisions 갱신만 완료했다. PR 초안·git 상태 변경 명령·커밋·push·PR 생성·운영 반영은 하지 않았다. H01~H03과 독립 리뷰·사람 승인은 별도 단계다. 이 구현 세션은 결과를 승인하지 않는다.
- 최종 계획 차이: components는 상속 위치 인자 보존을 위한 키워드 전용 필드, 연결·작업 완료 시 절대 마감 재검사, 수신 시각 별도 계측, 삭제 전 행 잠금, queries 전용 안전한 인자 오류 처리, 미기록 버전 분포 unknown 표시. 모두 승인된 동작을 유지하기 위한 구현 세부다. /sources는 기존 neutralize와 allowed_mentions 비움으로 표시한다.
- 색인 항목: index_version/embedding_model/chunking_version 변경 없음. eval_set_version/metrics_with_sample_size 해당 없음(검색·생성 로직·평가 세트 변경 없음, 품질 평가 실행 없음). estimated_or_used_neurons=0. 실제 Discord·Workers AI·Atlassian·운영 DB 호출 0건.

최종 changed_files (이번 실행 전체, 57개; 시작 전 ADR-016·spec/plan 등 작성 변경은 보존):

- `.env.example`
- `TASK.md`
- `docs/ops/oci-production-store.md`
- `specs/QK-OBS-001-query-log-feedback/quickstart.md`
- `specs/QK-OBS-001-query-log-feedback/tasks.md`
- `src/qello_knowledge/adapters/discord/webhook.py`
- `src/qello_knowledge/adapters/postgres/migrations/0008_query_log.sql`
- `src/qello_knowledge/adapters/postgres/query_log.py`
- `src/qello_knowledge/adapters/postgres/query_log_admin.py`
- `src/qello_knowledge/config/check.py`
- `src/qello_knowledge/config/registry.py`
- `src/qello_knowledge/discord/components.py`
- `src/qello_knowledge/discord/interactions.py`
- `src/qello_knowledge/discord/notices.py`
- `src/qello_knowledge/discord/sources.py`
- `src/qello_knowledge/domain/discord.py`
- `src/qello_knowledge/domain/query_log.py`
- `src/qello_knowledge/indexer/cli.py`
- `src/qello_knowledge/indexer/queries_cli.py`
- `src/qello_knowledge/ports/query_log.py`
- `src/qello_knowledge/query/app.py`
- `src/qello_knowledge/query/jobs.py`
- `src/qello_knowledge/query/pending.py`
- `src/qello_knowledge/query/pipeline.py`
- `src/qello_knowledge/query/recorder.py`
- `src/qello_knowledge/query/server.py`
- `tests/localdb/query/obs_db.py`
- `tests/localdb/query/test_obs_adapter.py`
- `tests/localdb/query/test_obs_consent_db.py`
- `tests/localdb/query/test_obs_erase.py`
- `tests/localdb/query/test_obs_export.py`
- `tests/localdb/query/test_obs_feedback_db.py`
- `tests/localdb/query/test_obs_migration.py`
- `tests/localdb/query/test_obs_query_role.py`
- `tests/localdb/query/test_obs_record_roundtrip.py`
- `tests/localdb/query/test_obs_report.py`
- `tests/localdb/query/test_obs_sources_db.py`
- `tests/unit/config/test_obs_settings.py`
- `tests/unit/discord/test_bot_domain.py`
- `tests/unit/discord/test_bot_interactions.py`
- `tests/unit/discord/test_obs_components.py`
- `tests/unit/discord/test_obs_interactions.py`
- `tests/unit/discord/test_obs_sources.py`
- `tests/unit/domain/test_obs_query_log.py`
- `tests/unit/query/obs_builders.py`
- `tests/unit/query/test_bot_register_commands.py`
- `tests/unit/query/test_obs_consent_flow.py`
- `tests/unit/query/test_obs_disabled.py`
- `tests/unit/query/test_obs_feedback.py`
- `tests/unit/query/test_obs_feedback_flow.py`
- `tests/unit/query/test_obs_no_raw_logs.py`
- `tests/unit/query/test_obs_pending.py`
- `tests/unit/query/test_obs_query_record.py`
- `tests/unit/query/test_obs_recorder.py`
- `tests/unit/test_boundaries.py`
- `workers/relay/relay.test.ts`
- `workers/relay/relay.ts`

### 검토 M1·M2 수정 (2026-10-29)

- 2026-10-29 **검토 M1·M2 수정, 같은 세션의 자기 검증 — status=BLOCKED(필수 검증 환경)**. 사용자 지시로 실행 에이전트가 지정한 7개 파일만 수정했다. 기존 변경·기존 시험 기대값 보존, git 상태 변경 명령·커밋·push·PR·외부 서비스 호출 없음.
- M1: 설정 왕복 뒤 남은 예산으로 statement_timeout을 다시 줄이고, 별도 Timer가 절대 마감 − 200ms에 해당 연결의 cancel_safe(timeout=0.2)를 요청한다. 설정 대기와 함수 실행을 함께 제한하며 취소 결과는 timeout이다. 취소 요청 완료를 join한 뒤 연결을 폐기하여 다음 작업을 잘못 취소하지 않는다. 연결 생성 뒤 최소 실행 예산 재검사는 유지한다. 네트워크 장애·취소 전달 실패 시점의 저장 여부는 기존 결과 불명 계약을 따른다.
- M2: 앞 길 작업 인자를 잠금 있는 상자로 전달한다. front 시간 초과 때 상자를 비우고 Future.cancel()하여 미시작 작업의 원문 참조를 제거한다. 실행할 때 인자를 꺼내 상자도 즉시 비운다. 이미 실행 중인 어댑터 작업은 M1의 취소 경로로 끝난다. 앞 길 대기열에 별도 개수 상한은 추가하지 않았다: 취소된 대기 작업은 빈 상자만 보유하며 기존 절대 마감 검사도 유지한다. 작업 스레드 자체가 멈추는 환경에서는 원문 없는 취소 작업 껍질이 일시 누적될 위험이 남는다.
- TDD: 수정 전 새 단위 시험 3개 실패(설정 대기 취소 부재, 함수 실행 취소 부재, 대기열 원문 weakref 생존)·기존 6개 통과 확인. 수정 뒤 9 passed(2.11s). 원문 대기 close 뒤, worker를 계속 막아 둔 상태에서도 weakref 소멸·Future 취소, worker 해제 뒤 저장 호출 0회를 확인했다. 로컬 DB에는 설정 pg_sleep 및 설정 왕복 600ms + 원문 INSERT AFTER trigger pg_sleep, 취소 뒤 원문 0건·consented=false 시험을 추가했지만 fixture 연결 차단으로 본문은 미실행이다.
- executed_checks / passed_checks: `uv run ruff check .` 통과, `uv run ruff format --check .` 682 files already formatted, `node --test workers/relay/relay.test.ts` 15 passed. `git diff --check` exit 0이나 `.env.example: Operation not permitted` 출력으로 전체 확인은 제한됨; 지정 변경 7파일의 diff check는 경고 없이 exit 0. uv 캐시는 쓰기 가능한 /private/tmp/qk-obs-uv-cache를 사용했다.
- blocked_checks: `uv run python scripts/preflight.py`는 정책상 차단된 설정 예시의 stat에서 PermissionError. `COMPOSE_DISABLE_ENV_FILE=1 DATABASE_URL= QK_LOCAL_DB_PORT=54322 uv run qk-dev db up --env-file /dev/null`은 Docker 소켓 접근 거부(권한 상승 재시도도 동일). 같은 로컬 고정 환경의 `uv run qk-migrate --env-file /dev/null` 두 번 모두 연결 불가(exit 4), 추가 권한 상승 재시도도 동일하여 applied=0을 확인하지 못했다. .env·.env.*·secrets 내용을 읽지 않았다.
- failed_checks / blocked_checks: `QK_REQUIRE_LOCALDB=1 uv run pytest`는 pytest가 루트 항목을 탐색하며 .env의 stat에서 수집 오류. 차단 경로를 탐색에서 제외한 `QK_REQUIRE_LOCALDB=1 uv run pytest --ignore=.env --ignore-glob='.env.*'`는 3196 passed, 3 deselected, 3 failed, 329 errors(11.19s). failed는 test_env_example_matches_registry(차단된 설정 예시 읽기), test_serve_answers_healthz_on_loopback 및 test_loopback_connection_is_allowed(소켓 권한); errors는 로컬 DB fixture 및 HTTP 통합 시험 소켓 권한이다. 시험 삭제·skip·suppress·새 noqa 없음. 관련 단위/query·discord 묶음도 429 passed, 동일 소켓 차단 1 failed·5 errors. 로컬 어댑터+수정 단위 묶음은 9 passed·DB fixture 4 errors. 코드 결함으로 확정된 최종 실패는 없지만 필수 검증 통과를 주장하지 않는다.
- assumptions / risks / required_human_decisions: 로컬 DB와 loopback·Docker 및 설정 예시 검사에 접근할 수 있는 검증 환경에서 필수 검증 전부를 재실행하고, 별도 검토자가 수정 diff와 취소·롤백 증거를 확인해야 한다. Timer 스케줄링·취소 전달은 OS/libpq/네트워크에 의존하며 실제 PostgreSQL 취소와 부분 저장 0건은 아직 확인하지 못했다. 독립 승인·운영 반영은 하지 않는다. jira_issue=SCRUM-120, spec_id=QK-OBS-001, 색인·임베딩·청킹·평가 세트 변경 없음, Neurons=0.

- 2026-10-29 추가 자기 검증: `uv run pytest --ignore=.env --ignore-glob='.env.*' tests/unit/query/test_obs_*.py -q --tb=short` → 86 passed(2.60s). 마지막 lint·format 재실행도 통과. 미추적 수정 파일은 `git diff --no-index --check /dev/null <파일>`로도 검사했으며 공백 오류 출력은 없었다(새 파일 차이로 exit 1). 최종 상태는 필수 환경 검증 차단에 따른 BLOCKED 그대로다.

### 재검토 M1 새 계약 시험 정정 (2026-10-29)

- 2026-10-29 **재검토 M1 새 계약 시험 정정, 같은 세션의 자기 검증 — status=PASS(이번 시험 수정 범위)**. jira_issue=SCRUM-120, spec_id=QK-OBS-001. 변경 파일은 `tests/localdb/query/test_obs_adapter.py`, `specs/QK-OBS-001-query-log-feedback/tasks.md`, `TASK.md` 3개다. `query_log.py`·`recorder.py`는 새 계약과 맞아 수정하지 않았다. 설계 측 research·contracts·Decisions 변경과 나머지 미커밋 변경은 보존했다.
- 시험 정정: 기존 950ms 완료 단언을 제거하고 실제 `QueryRecorder.front` 호출로 검사한다. 연결 래퍼가 cancel_safe 진입의 monotonic 시각을 기록하여 `deadline − 200ms`부터 50ms 이내인지 확인한다. 50ms는 Timer/Future 뒤 Python 스레드 재개 시각의 측정 허용 오차이며 200ms 여유보다 작아서 마감에야 취소하는 구현은 실패한다. 호출자 반환도 `deadline`부터 50ms 이내인지 확인한다. 이는 서버 취소 완료 시각 보장이 아니다.
- 시험 주입: 설정 pg_sleep(2), 또는 설정 왕복 600ms + 원문 INSERT AFTER trigger pg_sleep(2)를 사용한다. 함수 지연 사례에서는 서버 statement_timeout을 시험 연결에서만 끄므로 서버 타이머가 클라이언트 취소 부재를 가리지 못한다(기존 서버 statement_timeout 시험은 유지). 실제 취소 전송 후 cancel_safe 반환을 Event로 막아 어댑터 정리가 늦어도 호출자는 마감에 timeout을 받음을 검증한다. 원문 0건·consented=false 확인 뒤 Event를 풀고 바로 다음 store_question이 stored인지, 첫 연결 폐기·새 backend PID·새 연결 객체·원문 1건·consented=true인지 확인한다. 두 번째 연결에는 지연을 주입하지 않는다.
- executed_checks / passed_checks: `UV_CACHE_DIR=/private/tmp/qk-obs-uv-cache QK_REQUIRE_LOCALDB=1 uv run pytest --ignore=.env --ignore-glob='.env.*' tests/localdb/query/test_obs_adapter.py tests/unit/query/test_obs_adapter_deadline.py tests/unit/query/test_obs_recorder.py -q --tb=short` → 13 passed(4.60s). 대상 시험 파일 ruff check·format --check 통과. 변경 문서 diff check와 미추적 시험 파일 no-index 공백 검사에서 오류 출력 없음(no-index exit 1은 새 파일 차이). 첫 시험 실행은 닫힌 연결에서 backend_pid를 읽는 시험 계측 오류로 2 failed·2 passed였고, PID를 연결 생성 때 캡처하도록 고친 뒤 위 최종 시험이 통과했다. 구현 결함으로 인한 RED라고 주장하지 않는다.
- failed_checks=없음(최종 실행), blocked_checks=없음(이번 범위). 전체 preflight·전체 pytest·마이그레이션·중계 등 기본 검증은 이번 사용자 지시대로 오케스트레이터가 재실행하며 이번 세션에서는 실행하지 않았다. pytest의 차단 경로 탐색은 ignore 옵션으로 제외했으며 .env·.env.*·secrets 내용 읽기, 시험 삭제·skip·noqa, git 상태 변경·커밋·외부 API 호출 없음. 이번 시험은 기존 로컬 DB의 세션 전용 시험 DB만 사용했다. Neurons=0.
- assumptions / risks / required_human_decisions: OS 부하가 측정 허용 오차 50ms를 넘으면 시험이 실패할 수 있다. 취소 요청은 서버 완료 시각을 보장하지 않고, 늦은 커밋은 기존 결과 불명·재시도 계약을 따른다. 독립 재검토와 오케스트레이터의 전체 검증이 남았다. 이번 자기 검증은 독립 승인·병합·운영 승인이 아니다.
