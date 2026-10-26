---

description: "QK-BOT-001 구현 작업 목록"
---

# Tasks: QK-BOT-001 Discord `/ask`·지연 응답·답변 표시·분할·접근 제어·오류 안내

**Input**: `specs/QK-BOT-001-discord-ask/`의 plan.md, spec.md, research.md(R-01~R-15, 독립 검토 4차 반영), data-model.md, contracts/relay.md, contracts/discord-outbound.md, contracts/cli.md, quickstart.md,
`docs/sdd/decisions/ADR-022-discord-query-path.md`

**Tests**: 포함한다. spec FR-024와 C-12가 자동 시험을 요구한다. 시험을 먼저 쓰고 실패(아직 없는 모듈이면 수집 오류 포함)를 확인한 뒤 구현한다. 모든 자동 시험은 외부 호출 0건이다
(시험 안에서 만든 Ed25519 키 쌍, 가짜 Discord 전송, 가짜 검색·생성 제공자 `generation/fake.py`의 `ScriptedProvider`·`MemoryLedger`, 가짜 임베딩 제공자 `embedding/fake.py`, 가짜 시계, 로컬 DB).
실제 Discord·Workers AI·Cloudflare는 맨 끝 "사람 단계"다.

**Organization**: 사용자 스토리별 단계. US1 → US2 → US3 → US4(모두 P1) → US5 → US6(P2). US2~US4는 US1의 `discord/render.py`·`query/pipeline.py`·`query/app.py`를 넓혀 나간다.
커밋은 스토리 단위로 나눈다(`/harness-commit`).

**선행 조건**: spec.md·plan.md·ADR-022 초안 사람 승인과 `TASK.md` 구현 Scope 추가(2026-10-26), 이 목록의 사람 승인(2026-10-26). ADR-022 Accepted와 팀원(인스턴스 관리자) 동의는 PR 리뷰에서 받는다.

**공통 규칙**:
- 질문 원문, 답변 본문, 청크 본문, 출처 제목·링크, Discord 상호작용 식별자·토큰·사용자 식별자·이름·채널 식별자, 서명, 자격 정보를 운영 로그·예외 문구·요약에 넣지 않는다(spec FR-021).
  시험은 이 규칙을 검사한다(T039).
- 시험용 합성 값만 쓴다. 실제 서버·채널·역할 식별자, Discord 공개 키·애플리케이션 ID, 실제 팀 질문을 저장소에 넣지 않는다(AGENTS.md 6절). 합성 비밀값은 `tests/unit/synthetic_secrets.py`를 쓴다.
  시험을 지우거나 `skip`·`xfail`로 체크포인트를 통과시키지 않는다.
- 로컬 DB 시험은 `tests/localdb/` 아래에 두고 QK-STO-001 방식(세션마다 `qk_test_<무작위>` 데이터베이스 생성·마이그레이션·삭제)을 따른다. 공유 `postgres` 데이터베이스는 건드리지 않는다.
- 기존 코드는 plan.md "구현 Scope 승인이 필요한 것" 표의 변경만 한다. `retrieval/`, `generation/`, `embedding/`, `security/`, `indexer/ask_cli.py`, `indexer/search_cli.py`,
  `adapters/workers_ai/`, 마이그레이션 0001~0006은 바꾸지 않는다. `adapters/postgres/store.py`는 선택 인자 `deadline`만 더한다(T029).
- 기존 시험은 바꾸지 않고 그대로 통과해야 한다. 예외는 진입점 계약을 직접 고정한 시험의 기대값 갱신뿐이다(T008): `tests/unit/config/test_registry.py::test_query_does_not_require_index_tokens`
  (질의 진입점이 이제 `CLOUDFLARE_*`를 쓴다, research R-08), `tests/unit/config/test_check.py`의 질의 진입점 통과·실패 사례(새 필수 설정 `QK_DISCORD_GUILD_ID`, `CLOUDFLARE_*`), `tests/unit/config/test_example_file.py`
  (재생성한 `.env.example`과 대조). 검사 내용(색인 진입점에 Discord 설정 없음, 비밀값 비노출 등)은 그대로 둔다.
- 새 시험 파일 이름은 `tests/` 전체에서 겹치지 않게 `test_bot_` 접두어를 붙인다(시험 디렉터리에 `__init__.py`가 없어 같은 이름이면 pytest 수집이 실패한다). 시험 도우미 모듈도 `bot_` 접두어를 붙인다.
- `discord/`는 표준 라이브러리와 `qello_knowledge.domain`·`qello_knowledge.discord`만 가져온다. 예외는 `discord/signature.py`의 `cryptography` 지연 가져오기 하나다(T003). 상대 경로 가져오기를 쓰지 않는다.
  Discord HTTP는 `adapters/discord/`만 하고, `query/`가 둘을 조립한다(C-06).
- 시간은 모두 단조 시계 주입(`clock: Callable[[], float]`)으로 잰다. 시험은 가짜 시계와 이벤트로 기다림 없이 돈다. 실제 `sleep`을 쓰는 시험은 1초 안에 끝나는 것만 둔다.

**TDD 순서**: 각 단계에서 시험 작업을 먼저 쓰고 실패를 확인한 뒤 구현 작업을 한다. [P]는 같은 단계의 시험끼리, 구현끼리 병렬이라는 뜻이다.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: 다른 파일을 다루고 미완료 작업에 기대지 않아 병렬로 할 수 있다
- **[Story]**: 해당 사용자 스토리(US1~US6)

---

## Phase 1: Setup

- [ ] T001 `pyproject.toml`: `[project.optional-dependencies]`에 `query = ["cryptography>=43"]`(질의 서비스의 Ed25519 재검사, research R-04)를 더하고, 주석에 "질의 서비스만 쓴다. Worker 번들에는 넣지 않는다"를 적는다.
  `[dependency-groups] dev`에도 같은 항목을 더한다. 런타임 기본 `dependencies = []`는 그대로 둔다. `uv lock`으로 `uv.lock`을 갱신하고 고정된 `cryptography` 버전을 "실행 기록"에 적는다
- [ ] T002 [P] 패키지 자리 만들기: `src/qello_knowledge/discord/__init__.py`, `src/qello_knowledge/adapters/discord/__init__.py`, `tests/unit/discord/`, `tests/localdb/query/conftest.py`.
  conftest는 `tests/localdb/retrieval/conftest.py` 꼴을 따른다(`pytestmark = pytest.mark.localdb`, `db_url`, 시험마다 `qk.embedding_usage`·`qk.embedding_usage_daily`·`qk.generation_usage`·`qk.generation_usage_daily`를 비우는
  자동 픽스처, 합성 문서·인덱스 버전을 심는 도우미). 시험 디렉터리에는 `__init__.py`를 만들지 않는다
- [ ] T003 [P] `tests/unit/test_boundaries.py`: 기존 `RESTRICTED`·`ALLOWED_INTERNAL`·검사 함수는 그대로 두고, `discord` 전용 허용 목록(`qello_knowledge.domain`, `qello_knowledge.discord`)과 검사 함수를 따로 더한다
  (QK-GEN-001 `generation` 검사와 같은 꼴). `discord/signature.py`에만 `cryptography`(`cryptography.exceptions`, `cryptography.hazmat.primitives.asymmetric.ed25519`)를 허용한다. `adapters/discord/`는 표준 라이브러리와
  `qello_knowledge.domain`만 허용한다. 위반 사례 시험: `discord/`가 `qello_knowledge.adapters`·`security`·`retrieval`·`generation`·`psycopg`·`urllib.request`를 가져오면 실패, `discord/render.py`가 `cryptography`를 가져오면 실패,
  상대 경로 가져오기면 실패. 경로 비교는 `/`로 맞춘다(QK-GEN-001 실행 기록의 Windows 구분자 문제)
- [ ] T004 [P] 시험 도우미 `tests/unit/discord/bot_builders.py`: (1) 시험 안에서 만든 Ed25519 키 쌍과 `sign(body: bytes, timestamp: str) -> headers`, (2) 상호작용 본문 만들기
  (`ping()`, `ask(question, private=None, guild=…, channel=…, channel_type=0, roles=(), interaction_id=…, token=…)`, `component()`, `other_command(name)`, 스레드는 `channel_type` 10·11·12, DM은 `guild_id` 없음),
  (3) 가짜 Discord 전송 `FakeDiscord`(받은 요청의 방법·경로·헤더·본문을 기록하고, 요청마다 정한 응답(200, 204, 404, 429+`retry_after`, 5xx, 연결 오류, 지연)을 돌려준다), (4) 가짜 시계 `FakeClock`(`now()`, `advance(s)`),
  (5) 합성 서버·채널·역할 식별자 상수(17~20자리 숫자, 실제 값 아님). 같은 파일에 `sign`이 다른 키로 서명한 경우를 만드는 도우미도 둔다

---

## Phase 2: Foundational

**목적**: 모든 스토리가 쓰는 타입·설정·서명 검사·본문 해석·안내 문구·Discord 전송. 이 단계가 끝나야 스토리 시험을 쓸 수 있다.

- [ ] T005 [P] `tests/unit/discord/test_bot_domain.py`(data-model 2·3·5·6·7절): `Interaction`의 `token`·`question`이 `repr`에 나오지 않음, `InteractionKind` 값 3개(`PING`, `COMMAND`, `OTHER`),
  `ChannelKind` 4개(`TEXT`, `THREAD`, `DM`, `OTHER`), `AccessDecision` 7개(`ALLOWED`, `GUILD_OUTSIDE`, `CHANNEL_OUTSIDE`, `THREAD`, `DM`, `ROLE_MISSING`, `NOT_CONFIGURED`), `QueryStage` 값
  (`AWAITING_START`, `QUEUED`, `RETRIEVING`, `GENERATING`, `RENDERING`, `DELIVERING`, `DONE`, `NOT_STARTED`, `TIMED_OUT`, `FAILED`, `UNDELIVERED`), `FirstResponse`(유형 1·4·5, 플래그 64, `run_id`),
  `RenderedReply`(`messages`, `ephemeral`, `body_truncated`, `allowed_mentions == {"parse": []}`), `DedupEntry`(`interaction_id`, `stage` `IN_PROGRESS`·`DONE`, `expires_at`)에 질문·사용자 필드가 없음,
  `QueryRunLog` 필드가 data-model 5절 표(`run_id`, `access`, `private`, `status`, `failure`, `timings_ms`, `calls`, `deliver_retries`, `deliver_failure`, `retrieval_summary`, `generation_summary`)뿐이고 `to_json()`이
  키 순서가 고정된 한 줄 JSON. 모든 값은 불변(`frozen=True`)
- [ ] T006 `src/qello_knowledge/domain/discord.py`: T005의 타입. 외부 SDK 타입 없음(C-06). `Interaction` 필드는 data-model 2절 표 그대로(`interaction_id`, `token`(repr 숨김), `kind`, `command`, `question`(repr 숨김),
  `private`, `guild_id`, `channel_id`, `channel_kind`, `member_roles`). 사용자 식별자·이름 필드를 두지 않는다
- [ ] T007 [P] `tests/unit/config/test_bot_settings_registry.py`(data-model 1절): `Entrypoint.RELAY`(`"relay"`)와 `Entrypoint.REGISTER`(`"register"`, 명령 등록 전용) 추가. `specs_for(RELAY)`는
  `DISCORD_PUBLIC_KEY`, `QK_RELAY_TIMEOUT_SECONDS` 두 개뿐. `DISCORD_BOT_TOKEN`의 진입점은 `{REGISTER}`뿐이라 `specs_for(QUERY)`에 없음(R-12, spec FR-023). `DISCORD_APPLICATION_ID`·`QK_DISCORD_GUILD_ID`는 `{QUERY, REGISTER}`.
  `CLOUDFLARE_API_TOKEN`·`CLOUDFLARE_ACCOUNT_ID`는 `{QUERY, INDEX}`(R-08). 새 항목과 범위의 안·밖 경계값: `QK_RELAY_TIMEOUT_SECONDS` "0.5~2.8, 2.5", `QK_DISCORD_GUILD_ID` "17~20자리 숫자" 필수,
  `QK_DISCORD_ALLOWED_CHANNELS`·`QK_DISCORD_ALLOWED_ROLES` "쉼표로 나눈 17~20자리 숫자 목록"(빈 값 허용, 공백·중복·빈 항목 거부), `QK_QUERY_DEADLINE_SECONDS` "15~120, 55", `QK_QUERY_START_WAIT_SECONDS` "4~10, 5",
  `QK_QUERY_MIN_START_SECONDS` "8~60, 15", `QK_QUERY_NOTICE_GRACE_SECONDS` "1~30, 5", `QK_QUERY_CALL_LIMIT` "11~50, 20", `QK_DISCORD_MAX_MESSAGES` "2~10, 4", `QK_DISCORD_TITLE_MAX_CHARS` "20~200, 80",
  `QK_DISCORD_LINK_MAX_CHARS` "50~1000, 300", `QK_QUERY_WORKERS` "1~8, 2", `QK_QUERY_QUEUE_SIZE` "1~16, 4". 오류 문구에 값이 없음
- [ ] T008 `src/qello_knowledge/config/registry.py`: T007 항목과 진입점. `config/example.py`의 `_LABELS`에 `RELAY: "중계 Worker"`, `REGISTER: "명령 등록"`을 더한다. `REGISTER` 진입점은 data-model 1절의
  "명령 등록 명령만"을 설정 레지스트리로 나타낸 것이다. 같은 작업에서 data-model 1절 표의 `DISCORD_BOT_TOKEN`·`DISCORD_APPLICATION_ID`·`QK_DISCORD_GUILD_ID` 진입점 열을 같은 값으로 고친다.
  공통 규칙의 예외 시험 세 개만 기대값을 고친다
- [ ] T009 [P] `tests/unit/config/test_bot_cross_check.py`(data-model 1절 교차 규칙, spec FR-008·FR-016): 기본값 통과. 거부: `QK_QUERY_DEADLINE_SECONDS + QK_QUERY_NOTICE_GRACE_SECONDS ≥ 900`,
  `2 × QK_GEN_TIMEOUT_SECONDS + 5 > QK_QUERY_DEADLINE_SECONDS`(예: 시간 제한 30, 마감 60), `QK_QUERY_MIN_START_SECONDS ≥ QK_QUERY_DEADLINE_SECONDS`,
  `QK_QUERY_CALL_LIMIT < 7 + 4 + QK_DISCORD_MAX_MESSAGES × 2`(예: 메시지 상한 10, 호출 상한 20). 허용 채널 목록이 비면 경고(통과는 유지, spec FR-023). 결과에 값이 아니라 규칙 이름만 나옴
- [ ] T010 `src/qello_knowledge/config/check.py`: 질의 진입점 교차 검사(T009). 기존 `_generation_check`·`_budget_check`는 그대로 두고 새 검사 함수를 `build_report`에 더한다.
  출처 목록 산식(FR-012)은 렌더러 상수가 필요해 US4(T047)에서 더한다
- [ ] T011 [P] `tests/unit/discord/test_bot_signature.py`(spec FR-001, research R-04): 맞는 서명 통과, 다른 키·바뀐 본문·바뀐 시각·헤더 없음·16진이 아닌 서명·길이 틀린 서명 거부, 서명 시각이 현재와 300초 넘게
  차이(과거·미래 모두)면 거부, 300초 정확히는 통과, 숫자가 아닌 시각 거부. 검사 함수는 예외를 밖으로 내지 않고 참·거짓만 돌려준다. `cryptography`가 없을 때 `require_backend()`가 설치 안내 문구로 실패한다
  (`monkeypatch`로 가져오기 실패를 흉내 낸다)
- [ ] T012 `src/qello_knowledge/discord/signature.py`: `verify(public_key_hex, signature_hex, timestamp, body, now) -> bool`(서명 대상은 `timestamp.encode() + body`), `require_backend()`.
  `cryptography`는 함수 안에서 가져온다(Worker 번들과 기본 설치에 영향 없음)
- [ ] T013 [P] `tests/unit/discord/test_bot_interactions.py`(data-model 2절, spec FR-002·FR-003, Edge Cases): `PING` 해석, `/ask`의 `질문`·`나만_보기` 인자, `나만_보기` 없으면 거짓, 참·거짓이 아니면 참,
  본문 64 KiB 초과·JSON 실패·필수 필드 없음은 `OTHER`, 명령 이름이 `ask`가 아니거나 상호작용 `type`이 2가 아니면(버튼 3 등) `OTHER`, 채널 종류(`channel.type` 0·5 → `TEXT`, 10·11·12 → `THREAD`, `guild_id` 없음 → `DM`,
  그 밖 → `OTHER`), `member.roles` 읽기, `member.user`·`user`의 식별자·이름은 읽지 않음(결과 객체에 없음). 첫 응답 결정 `first_response(...)`의 응답 꼴: 연결 확인 `{"type": 1}`, 즉시 안내 유형 4·플래그 64·`allowed_mentions`,
  처리 중 응답 `{"type": 5}`·"나만 보기"면 `{"type": 5, "data": {"flags": 64}}`(contracts/relay.md 2절 표)
- [ ] T014 `src/qello_knowledge/discord/interactions.py`: `parse(body: bytes) -> Interaction`, 응답 JSON 만들기(`pong()`, `notice(text)`, `deferred(private)`). 허용 범위·비밀값·중복·자리 판정은 받지 않고
  `query/app.py`가 조립한다
- [ ] T015 [P] `tests/unit/discord/test_bot_notices.py`(spec FR-011 표, data-model 6절): `RetrievalFailure` 9개와 `GenerationFailure` 6개, 생성 상태 5개가 빠짐없이 한 문구에 대응(새 값이 생기면 시험이 실패),
  문구가 spec FR-011 표 그대로(질문 길이 문구의 "2,000자"는 `question_max_chars`를 따름), 고정 안내(지원하지 않는 요청 "지원하지 않는 요청입니다.", 허용 범위 "이 채널에서는 `/ask`를 쓸 수 없습니다.",
  비밀값 FR-006 문장, 중복 "이미 처리 중인 요청입니다.", 자리 없음 "지금 요청이 많습니다. 잠시 후 다시 질문해 주세요.", 시작 안 됨 "요청을 처리하지 못했습니다. 잠시 후 다시 질문해 주세요.",
  Worker 실패 "지금은 답할 수 없습니다. 잠시 후 다시 질문해 주세요.", 질의 마감 초과, 예상하지 못한 실패), 실패 안내 끝에 질의 실행 식별자의 짧은 꼴(`(확인 번호 1a2b3c4d)` 같은 꼴, 뒤 8자)을 붙임,
  문구에 실패 종류 이름(`store_unavailable` 등)이 없음, 다음 행동 구분(다시 시도 / 운영 담당자에게 알림 / 내일 다시)
- [ ] T016 `src/qello_knowledge/discord/notices.py`: 안내 문구 표 한 곳(T015). 문구는 상수, 대응은 사전
- [ ] T017 [P] `tests/unit/adapters/test_bot_discord_webhook.py`(contracts/discord-outbound.md, research R-05 전달 시간, spec FR-009): 주입한 전송(`FakeDiscord`)으로 확인한다.
  첫 메시지 `PATCH /api/v10/webhooks/{application_id}/{token}/messages/@original`, 이어지는 메시지 `POST /api/v10/webhooks/{application_id}/{token}`(질문자만 보기면 `flags: 64`), 본문
  `{"content": …, "allowed_mentions": {"parse": []}}`, `User-Agent: DiscordBot (https://github.com/Qello-Labs/qello-knowledge, <버전>)`, 인증 헤더 없음. 다시 시도: 메시지마다 최대 2회 시도, `429`(`retry_after`)·`5xx`·연결 오류,
  첫 메시지 첫 시도의 `404`면 1초 뒤 1회, 두 번째 `404`와 이어지는 메시지의 `404`와 그 밖 `4xx`는 다시 시도 없이 `UNDELIVERED`. 호출마다 시간 제한 = min(3초, 안내 전달 마감까지 남은 시간),
  (대기 + 1초) > 남은 시간이면 다시 시도 안 함, 남은 시간 < 1초면 호출 0회로 `UNDELIVERED`. 단계별로 늦게 오는 응답을 넣어 호출 전체 경과 시간이 마감을 넘지 않음(완료·중단 시각). 첫 메시지가 끝내 실패하면 이어지는 메시지 0회.
  결과에 실패 종류와 다시 시도 횟수만 있고 토큰·경로·응답 본문이 없음. 명령 등록 `PUT /api/v10/applications/{application_id}/guilds/{guild_id}/commands`, 헤더 `Authorization: Bot <토큰>`
- [ ] T018 `src/qello_knowledge/adapters/discord/webhook.py`: T017. `urllib` 기반 기본 전송과 시험용 주입 자리. 경로의 토큰은 예외 문구·로그에 넣지 않는다(예외는 상태 코드와 실패 종류만)

**Checkpoint**: `uv run pytest tests/unit/discord tests/unit/config tests/unit/adapters/test_bot_discord_webhook.py tests/unit/test_boundaries.py` 통과

---

## Phase 3: User Story 1 - 허용된 채널에서 `/ask`로 질문하고 출처가 붙은 답을 받는다 (P1) 🎯 MVP

**Goal**: 서명이 맞는 허용 채널 `/ask`에 처리 중 응답을 바로 돌려주고, 시작 확인 뒤 검색·생성을 질의 마감 안에서 돌려 답변 본문과 출처 목록으로 한 번 갱신한다.

**Independent Test**: 시험 키로 서명한 가짜 상호작용을 `query/app.py`에 넣고, 가짜 검색·생성 제공자 결과를 가짜 Discord 전송이 받은 갱신 메시지로 본다(spec US1 Independent Test).

### Tests for User Story 1

- [ ] T019 [P] [US1] `tests/unit/query/test_bot_first_response.py`(contracts/relay.md 2절, spec US1-1·US1-5·US1-6, FR-007): `POST /discord/interactions`에 연결 확인 → `{"type": 1}`, 허용된 `/ask` → `{"type": 5}`와 응답 헤더
  `X-QK-Run`(형식 `q-<UTC 시각>-<16진 8자>`), "나만 보기" → `flags: 64`. 응답을 돌려줄 때까지 검색·생성·저장소·Discord 호출 0회(가짜들의 호출 기록), 작업은 `AWAITING_START`로 등록
- [ ] T020 [P] [US1] `tests/unit/query/test_bot_start_confirm.py`(contracts/relay.md 3절, research R-03): `POST /discord/interactions/start`(`{"run_id": …}`, 원본 서명 헤더 두 개)가 시작 대기 중이고 서명이 같으면 `204`이고
  작업이 `QUEUED`로 감. 없는 `run_id`, 서명 불일치, 이미 시작함, 시작 대기 만료는 `409`이고 상태 변화 없음. 시작 확인 없이 `QK_QUERY_START_WAIT_SECONDS`(가짜 시계 5초)가 지나면 `NOT_STARTED` → 첫 메시지
  `PATCH` 한 번("요청을 처리하지 못했습니다…"), 검색·생성 0회, 수명 자리 반환. 시작 확인과 만료가 같은 순간에 오면 둘 중 하나만 일어남. 첫 `PATCH`가 `404`면 1초 뒤 1회만 다시 보냄
- [ ] T021 [P] [US1] `tests/unit/query/test_bot_jobs.py`(research R-05, data-model 5·7절, spec FR-010): 수명 자리 `C = QK_QUERY_WORKERS + QK_QUERY_QUEUE_SIZE`(기본 6)를 넘는 새 요청은 "지금 요청이 많습니다" 즉시 안내,
  끝 상태(`DONE`, `UNDELIVERED`)에서 자리 반환, 실행 자리(기본 2)는 `RETRIEVING`에서 잡고 호출이 실제로 끝날 때 반환(질의 마감으로 버린 작업도 끝날 때까지 쥠), 늦게 끝나는 작업 2개가 실행 자리를 쥐어도 동시 검색·생성 ≤ 2,
  `QUEUED`에서 실행 자리를 잡을 때 남은 시간 < `QK_QUERY_MIN_START_SECONDS`면 `TIMED_OUT`, 마감 감시는 상태 전이와 전달 예약만 하고 Discord를 직접 부르지 않음, 전달 권한은 작업마다 한 번(결과·시간 초과·`NOT_STARTED` 중
  먼저 얻은 쪽), 전달 풀 크기 = `C`이고 전달 요청이 풀을 기다리지 않음, 동시 만료 6개·느린 전송·`429` 대기·앞 전송이 느린 동안 새 요청이 계속 오는 경우를 조합해 모든 전송이 안내 전달 마감 안에 끝나거나 멈춤.
  중복 판정: 처리 중·끝난 뒤(900초 안) 같은 상호작용 식별자는 "이미 처리 중인 요청입니다." 즉시 안내이고 질의·갱신 0회 추가, 900초 뒤 항목이 지워짐, 항목에 질문·사용자 정보가 없음, 동시 두 요청 중 하나만 처리.
  새 실행기(재시작 흉내)에 같은 상호작용을 넣으면 다시 처리됨을 기대 결과로 고정(spec SC-011 예외)
- [ ] T022 [P] [US1] `tests/unit/query/test_bot_pipeline.py`(research R-06·R-11, spec FR-008·FR-015·FR-017, US1-2·US1-3·US1-4): 가짜 검색·생성으로 답변 결과 → 첫 메시지 `PATCH` 한 번, 같은 내용 두 번 없음, 스트리밍 없음.
  질의별 생성 설정: 남은 시간 R에서 시간 제한 = min(설정 시간 제한, ⌊(R − 5) ÷ 2⌋), 생성 마감 = min(설정 생성 마감, R), 기본 설정이 질의 마감보다 짧으면 설정 그대로, R < 7이면 생성 0회와 시간 초과 안내.
  임베딩 전송 시간 제한 = min(10, R − 여유), 임베딩 재시도 대기 뒤 남은 시간이 시간 제한보다 짧으면 대기 없이 `DeadlineReached` → 시간 초과 안내, 검색 재시도 대기는 질의 마감 안에서만(FR-017).
  `GenerationRequest.run_id`가 `X-QK-Run`과 같음. 질의 마감에서 생성이 안 끝나면 기다리지 않고 시간 초과 안내, 늦게 끝난 생성 결과는 버리고 장부 기록(`MemoryLedger`)은 남음, 저장소·장부 연결이 `finally`에서 닫힘.
  검색 요약의 외부 호출 수 ≤ 7, 생성 ≤ 4, 질의 전체 ≤ `QK_QUERY_CALL_LIMIT`(FR-016)
- [ ] T023 [P] [US1] `tests/unit/discord/test_bot_render_basic.py`(spec FR-013, data-model 6절, US1-2): 답변 본문 뒤 출처 목록, 목록 머리 "자료 기준: 색인된 문서", 항목 꼴
  `[S1] <제목> · <URL> · 버전 <앞 7자> · 수정 2026-10-20 · 수집 2026-10-24 09:30 KST`(커밋 해시(40자 16진)면 앞 7자, 아니면 앞 12자, 수정일 없으면 "수정 미상", 날짜는 한국 시간), URL은 `<…>`로 감쌈, 링크 없으면 "링크 없음",
  제목이 `QK_DISCORD_TITLE_MAX_CHARS`(80)를 넘으면 줄이고 "…", 링크가 `QK_DISCORD_LINK_MAX_CHARS`(300)를 넘으면 "링크 생략(길이 초과)"(링크는 자르지 않음), 항목 순서·개수가 생성 결과와 같음, 모든 메시지 2,000자 이하,
  같은 입력이면 같은 결과. 출처 목록은 생성 결과의 출처에서만 만들고 본문에서 가져오지 않음
- [ ] T024 [P] [US1] `tests/unit/discord/test_bot_relay.py`(contracts/relay.md 1절): Worker 중계 판단의 순수 함수. 본문 64 KiB 초과 → `413`, 서명 헤더 없음·시각 차이 300초 초과 → `401`(서명 검사 전), 질의 서비스 실패(연결 실패,
  제한 시간 초과, `200` 아닌 응답) → 실패 안내 JSON(`{"type": 4, "data": {"content": "지금은 답할 수 없습니다. 잠시 후 다시 질문해 주세요.", "flags": 64, "allowed_mentions": {"parse": []}}}`), 원본 `type`이 1이면 질의 서비스 없이
  `{"type": 1}`, 응답 헤더 `X-QK-Run`이 있을 때만 시작 확인 요청(본문 `{"run_id": …}`, 원본 서명 헤더 두 개)을 만듦, 요청 하나에 질의 서비스 호출 계획 ≤ 2, 로그 항목은 `relayed`·`relay_failed`·`start_failed`와 걸린 시간뿐
- [ ] T025 [P] [US1] `tests/localdb/query/test_bot_store_deadline.py`(research R-06, quickstart 1절 검색 마감 주입): `PostgresStore(url, deadline=…)`. 검색·문맥 호출 직전 남은 시간이 모자라면 저장소 질의 0회로 시간 초과 오류,
  `pg_sleep`으로 오래 걸리는 질의는 마감에 연결 취소로 시간 초과 오류, 질의 완료와 타이머 해제가 겹쳐도 예외·남은 타이머 없음, 취소 뒤 연결이 정리되고 다음 호출이 새 연결로 됨, 남은 시간 < 연결 제한 10초면 새 연결을 맺지 않음,
  `deadline` 없으면 지금 동작 그대로(기존 `tests/localdb/retrieval` 시험이 바뀌지 않고 통과), 검색 요약의 외부 호출 수가 실제 저장소 질의 수와 같음(`SET` 문장을 보내지 않음)

### Implementation for User Story 1

- [ ] T026 [P] [US1] `src/qello_knowledge/discord/render.py`: 답변 본문 + 출처 목록 기본 렌더링(T023). 길이 상수와 항목 꼴은 모듈 상수로 둔다(US4의 산식이 쓴다). 서식·멘션 무력화는 US3(T042), 분할은 US4(T046)에서 넓힌다
- [ ] T027 [P] [US1] `src/qello_knowledge/discord/relay.py`: Worker 중계 판단 순수 함수(T024). Worker와 같은 패키지를 쓰므로 표준 라이브러리만 가져온다
- [ ] T028 [US1] `src/qello_knowledge/query/jobs.py`: 수명 자리·실행 자리·마감 감시 스레드·전달 실행기·전달 권한·중복 판정 사전(T020·T021). 시계·실행기·전달 함수를 주입받는다
- [ ] T029 [US1] `src/qello_knowledge/adapters/postgres/store.py`: 선택 인자 `deadline: Callable[[], float] | None = None`(남은 초를 돌려주는 함수). 검색·문맥 호출(`search_vector`, `search_keyword`, `search_keyword_terms`,
  `chunk_context`, `chunk_neighbors`, `source_revisions`)마다 실행 직전 남은 시간 확인, 질의 동안만 `Connection.cancel_safe()`를 부르는 타이머(취소는 타이머 스레드에서), 취소되면 시간 초과 오류(`StoreError` 하위)로 바꿈(T025).
  색인 쓰기 메서드는 바꾸지 않는다
- [ ] T030 [US1] `src/qello_knowledge/query/pipeline.py`: 작업마다 검색 부품을 새로 만든다. `postgres_search`와 같은 부품(`PostgresStore(url, deadline=…)`, `PostgresUsageLedger`, `EmbeddingService(…, retry_policy=RetryPolicy(max_retries=1),
  retry_delay=query_retry_delay, sleep=<마감 확인 sleep>)`, `WorkersAiRestProvider(transport=UrllibTransport(timeout=…))`)과 `postgres_ask`와 같은 생성 부품(`PostgresGenerationLedger`, `WorkersAiGenerationProvider`)을
  주입 가능한 공장으로 조립하고, `retrieve` → `generate(request, deps, settings)`(질의별 `GenerationSettings`, research R-06) → `render` → 전달(T018)을 잇는다(T022). `indexer/ask_cli.py`·`search_cli.py`는 가져다 쓰기만 한다
- [ ] T031 [US1] `src/qello_knowledge/query/app.py`: `POST /discord/interactions`, `POST /discord/interactions/start` 경로. 처리 순서는 contracts/relay.md 2절(서명 재검사 → 해석 → 연결 확인 → 허용 범위 → 비밀값 → 중복 → 수명 자리 →
  시작 대기 등록). 허용 범위·비밀값은 이 단계에서 통과로 두는 자리만 만들고 US3(T041)에서 채운다. 기존 `GET /healthz` 동작과 `tests/unit/query/test_app.py`는 그대로다. 요청 헤더·원본 본문을 받도록 `handle`을 넓히되 기존 호출 꼴도 받는다
- [ ] T032 [US1] `src/qello_knowledge/query/server.py`: `serve`가 원본 본문(상한 64 KiB)과 헤더를 `handle`에 넘기고, 시작할 때 설정 검사(필수 없음·교차 규칙 위반이면 종료 코드 2, 허용 채널 비면 경고 뒤 계속)와
  `require_backend()`를 하고, 작업 실행기를 띄운다(contracts/cli.md). 기존 `tests/unit/query/test_server.py`는 그대로 통과한다
- [ ] T033 [US1] `src/qello_knowledge/query/worker.py`: 중계 Worker로 바꾼다. 설정은 `Entrypoint.RELAY`만 읽고, Web Crypto `crypto.subtle.verify("Ed25519", …)`로 서명을 검사하고, `env.QUERY_SERVICE.fetch(…)`(VPC 바인딩)로 중계하고,
  `ctx.waitUntil`로 시작 확인을 보낸다. 판단은 `discord/relay.py`가 한다. 이 파일은 Workers 런타임에서만 가져오므로 시험에서 가져오지 않는다(기존 주석 유지). 실제 실행 확인은 사람 단계 H01
- [ ] T034 [US1] `wrangler.toml`: Worker 이름, `main = "src/qello_knowledge/query/worker.py"`, `compatibility_flags = ["python_workers"]`, `compatibility_date`, VPC 바인딩 `QUERY_SERVICE`(`service_id = "<vpc-service-id>"` placeholder),
  `[vars] QK_RELAY_TIMEOUT_SECONDS = "2.5"`. `DISCORD_PUBLIC_KEY`는 `wrangler secret`로 넣는다는 주석만 둔다. 계정 ID·서비스 ID·주소를 넣지 않는다. `pywrangler` 설정 꼴은 QK-FND-001 research를 따르고, 구현 때 확인한 문서 URL을 "실행 기록"에 적는다

**Checkpoint**: US1 시험과 기존 시험 전부 통과. 가짜 제공자로 처리 중 응답 → 시작 확인 → 답변 갱신이 이어진다(quickstart 2절을 가짜 전송으로).

---

## Phase 4: User Story 2 - 결과가 답이 아닐 때 무슨 일인지 알아볼 수 있게 안내받는다 (P1)

**Goal**: 확인 불가·출처 확인 안 됨·출력 잘림 표시와 검색·생성 실패 종류별 안내를 spec FR-011 표대로 보인다.

**Independent Test**: 가짜 생성 제공자로 상태와 표시를 하나씩 만들어 갱신 메시지를 본다(spec US2 Independent Test).

- [ ] T035 [P] [US2] `tests/unit/query/test_bot_status_messages.py`(spec US2-1~US2-5, FR-011, SC-006): 확인 불가 → 생성 결과 본문 그대로, 출처 목록 없음. 출처 확인 안 됨(`flags.unsupported_answer`) → 본문 앞
  "⚠️ 출처를 확인하지 못한 답변입니다. 원문으로 확인해 주세요." 줄, 출처 목록 없음. 출력 잘림(`flags.truncated`) → 본문 끝 "(답변이 길어 일부가 잘렸습니다.)". 검색 실패 9종·생성 실패 6종·질의 마감 초과·예상하지 못한 예외 각각 → FR-011 문구와
  짧은 실행 식별자. 제공자 할당 소진 → "오늘 사용 한도에 닿아…". 질의 중 전송 차단(검색 `outgoing_blocked`, 생성 상태 "외부 전송 차단") → FR-006 문장, 공개 범위는 처리 중 응답 그대로. 모든 메시지에 실패 종류 이름·예외 메시지·주소·질문 원문이 없음
- [ ] T036 [US2] `src/qello_knowledge/discord/render.py`·`src/qello_knowledge/query/pipeline.py`: 표시 줄과 실패 안내 연결(T035). 예상하지 못한 예외는 작업 경계에서 잡아 "요청을 처리하지 못했습니다…"로 보낸다

**Checkpoint**: US1·US2 시험 통과.

---

## Phase 5: User Story 3 - 허용 범위 밖이나 위험한 요청은 처리하지 않는다 (P1)

**Goal**: 서명 거부, 허용 범위 판정, 처리 중 응답 전 비밀값 검사, 알림·서식 무력화, 원문 비기록.

**Independent Test**: 서명이 틀린 요청, 허용 밖 요청, 비밀값 질문, 멘션 꼴을 심은 가짜 결과로 응답·외부 호출 수·알림 설정을 본다(spec US3 Independent Test).

- [ ] T037 [P] [US3] `tests/unit/discord/test_bot_access.py`(data-model 2절, spec FR-004, US3-2·US3-3): 허용 채널의 글 채널 → `ALLOWED`, 다른 서버 → `GUILD_OUTSIDE`, 목록 밖 채널 → `CHANNEL_OUTSIDE`, 허용 채널 아래 스레드 → `THREAD`,
  DM → `DM`, 허용 역할 목록이 있고 역할이 없음 → `ROLE_MISSING`, 역할 목록이 비면 역할 제한 없음, 허용 채널 목록이 비었거나 서버가 설정되지 않음 → `NOT_CONFIGURED`(닫힘)
- [ ] T038 [P] [US3] `tests/unit/query/test_bot_reject_paths.py`(spec US3-1·US3-2·US3-4, FR-001·FR-006·FR-007, SC-003·SC-004·SC-005·SC-013 자동 부분): 서명 없음·틀림·시각 초과 → `401`, 검색·생성·Discord 호출 0회, 운영 로그 0줄.
  허용 밖 각 경우와 빈 허용 목록 → 질문자만 보는 허용 범위 안내, 검색·생성 0회. `tests/unit/synthetic_secrets.py`의 합성 비밀값이 든 질문 → 질문자만 보는 FR-006 안내, 임베딩·생성 0회, 안내·로그에 맞은 문자열 0건.
  지원하지 않는 요청 → 질문자만 보는 안내. 이 즉시 안내들은 "나만 보기" 인자와 상관없이 플래그 64
- [ ] T039 [P] [US3] `tests/unit/query/test_bot_no_raw_logs.py`(spec FR-021, SC-009): 모든 경로(답변, 확인 불가, 실패 주입 전부, 시간 초과, 전달 실패, 서명 거부, 중복, 자리 없음)의 표준 오류 운영 로그와 예외 문구를 모아
  합성 질문 원문·답변 본문·청크 본문·출처 제목·링크·상호작용 식별자·토큰·서명·사용자 식별자·채널 식별자·`DATABASE_URL`·`CLOUDFLARE_API_TOKEN` 표식이 0건
- [ ] T040 [P] [US3] `tests/unit/discord/test_bot_neutralize.py`(spec FR-014, US3-5, SC-008): 답변 본문·출처 제목에 `@everyone`, `@here`, `<@123…>`, `<@&123…>`를 심어도 모든 메시지의 `allowed_mentions`가 `{"parse": []}`,
  출처 제목의 `[ ] ( ) * _ ~ \` | >` 같은 서식·링크 꼴 글자는 `\`로 바뀌어 링크 꼴을 바꾸지 못함, 수정일 같은 자료 유래 글도 같음, 답변 본문의 굵게·목록·코드 서식은 그대로
- [ ] T041 [US3] `src/qello_knowledge/discord/access.py`와 `src/qello_knowledge/query/app.py`: 허용 범위 판정(T037)과 처리 중 응답 전 비밀값 검사(`indexer/embedding.py`의 `security_outgoing_check(policy)`에 질문만, 출처 없이) 연결(T038).
  정책은 `serve` 시작 때 `config/sources.toml`·`config/security_exceptions.toml`로 한 번 읽는다(`ask_cli`와 같은 방식). 읽기에 실패하면 시작하지 않는다(종료 코드 2)
- [ ] T042 [US3] `src/qello_knowledge/discord/render.py`: 자료 유래 글의 서식 무력화(T040). 무력화 뒤 길이가 렌더러 상수(항목 최대 길이)에 반영되게 한다
- [ ] T043 [US3] 운영 로그 한 줄(`QueryRunLog.to_json()`)을 `query/server.py`에서 표준 오류로 쓰고, 예외 문구에서 원문이 나가지 않게 작업 경계에서 바꾼다(T039)

**Checkpoint**: US1~US3 시험 통과.

---

## Phase 6: User Story 4 - 긴 답변과 출처 목록이 잘리지 않고 나뉜다 (P1)

**Goal**: 메시지 2,000자·메시지 수 상한 안에서 문단·문장 경계로 나누고, 출처 목록은 빠짐없이 마지막 메시지들에 둔다.

**Independent Test**: 긴 본문, 긴 코드 블록, 경계의 링크·인용 표기, 출처 최대 수로 분할 결과를 본다(spec US4 Independent Test).

- [ ] T044 [P] [US4] `tests/unit/discord/test_bot_split.py`(spec FR-012, US4-1~US4-4, SC-007): 한도 안이면 메시지 1개, 나눈 자리 문단 → 문장 → 공백 순, 링크·`[S번호]`·무력화한 글 중간에서 안 나눔, 공백 없는 긴 문자열은 한도에서 자름,
  한도를 넘는 링크 하나는 "(긴 링크 생략)", 코드 블록이 나뉘면 조각마다 닫고 같은 언어 표시로 다시 엶, 메시지 수 상한(4)을 넘는 본문은 줄이고 "(답변이 길어 일부를 생략했습니다.)", 출처 목록은 줄이지 않고 항목 사이에서만 나뉘며 본문 뒤 마지막 메시지들에 옴,
  설정이 허용하는 최대 수(`expand_top` 8)의 출처가 모두 최대 길이 제목(무력화로 길이가 최대로 늘어나는 글)·긴 링크를 가진 경우에도 모든 메시지 ≤ 2,000자이고 메시지 수 ≤ 상한, 같은 입력이면 같은 결과, "나만 보기"면 이어지는 메시지도 질문자만 보기
- [ ] T045 [P] [US4] `tests/unit/config/test_bot_source_list_check.py`(data-model 1절 출처 목록 산식, SC-007 마지막 문장): `항목 최대 길이`를 렌더러가 내보내는 실제 문자열(최대 길이 제목 전부 무력화, 비해시 버전 12자, 링크 상한)로 계산해
  상수와 같음을 고정, 기본 설정(`expand_top` 8, 2,000자, 제목 80, 링크 300, 메시지 4)은 통과(메시지당 항목 수와 필요한 메시지 수를 "실행 기록"에 적는다), 제목·링크 상한을 키우거나 메시지 상한을 줄여 `⌈expand_top ÷ 메시지당 항목⌉ > 메시지 수 상한 − 1`이 되는 설정은 모두 거부
- [ ] T046 [US4] `src/qello_knowledge/discord/render.py`: 분할(T044). 첫 메시지가 처리 중 응답을 바꾸는 글이다
- [ ] T047 [US4] `src/qello_knowledge/config/check.py`: 출처 목록 산식 검사(T045). 렌더러 상수를 가져온다(`config` → `discord` 방향만)

**Checkpoint**: US1~US4 시험 통과.

---

## Phase 7: User Story 5 - 질의 경로가 운영 저장소에 열린 포트 없이 최소 권한으로 붙는다 (P2)

**Goal**: `qk_query` 역할과 `qk.embedding_usage` RLS로 질의 서비스 권한을 검색 읽기와 질의 사용량 기록으로 한정하고, 저장소 장애를 안내로 바꾸며, 운영 절차를 쓴다.

**Independent Test**: 로컬 DB에서 `qk_query`로 허용·거부 목록을 확인한다(spec US5 Independent Test 로컬 부분). 공인 주소 접속 시험은 사람 단계 H03.

- [ ] T048 [P] [US5] `tests/localdb/query/test_bot_query_role.py`(data-model 4절, spec FR-019, SC-010 로컬 부분): 마이그레이션 뒤 시험 안에서 `qk_query`에 시험용 로그인을 준(`SET ROLE qk_query`로 대신해도 된다) 연결로
  성공: 검색·문맥 함수(`qk.search_vector`, `qk.search_keyword`, `qk.search_keyword_terms`, `qk.chunk_context`, `qk.chunk_neighbors`), `qk.embedding_record`(`purpose = 'query'`), `qk.embedding_usage_today`, `qk.generation_record`,
  `qk.generation_usage_today`, 저장소 검색 경로(`PostgresStore`) 한 번. 거부: 예산이 충분한 값으로 부른 `qk.embedding_reserve`(INSERT 분기까지 가서 RLS 거부), 직접 `purpose = 'index'` INSERT, `qk.artifact`·`qk.chunk`·`qk.embedding`·`qk.index_version`
  쓰기·지우기, 사용량 기존 행 `UPDATE`·`DELETE`, `qk.embedding_usage_daily`·`qk.generation_usage_daily` 쓰기, 정산(`qk.embedding_settle`)·정리(`*_prune`) 함수, `qk.sync_*` 읽기·쓰기, `CREATE`·`ALTER`. 소유자 역할로 `qk.embedding_reserve`와
  `purpose = 'index'` 기록이 그대로 됨(RLS가 소유자에 영향 없음). 마이그레이션을 두 번 실행해도 같음
- [ ] T049 [P] [US5] `tests/unit/query/test_bot_store_unavailable.py`(spec US5-4, FR-020): 저장소 연결 실패·질의 시간 초과를 넣으면 질의 마감 안에 "지금은 자료를 검색할 수 없습니다…" 안내로 갱신, 검색 재시도는 마감 안에서만
- [ ] T050 [US5] `src/qello_knowledge/adapters/postgres/migrations/0007_query_role.sql`: `NOLOGIN` 역할 `qk_query`(이미 있으면 만들지 않음), data-model 4절 권한 목록 그대로, `qk.embedding_usage`에 `ENABLE ROW LEVEL SECURITY`와
  `FOR SELECT TO qk_query USING (true)`, `FOR INSERT TO qk_query WITH CHECK (purpose = 'query')` 정책. `FORCE ROW LEVEL SECURITY`를 쓰지 않고, `PUBLIC`의 함수 `EXECUTE`를 거두지 않으며, `UPDATE`·`DELETE` 정책을 두지 않는다.
  권한 목록을 함수가 실제로 쓰는 표·시퀀스와 대조한 결과(빠진 권한, 더한 권한)를 data-model 4절과 "실행 기록"에 적는다. 운영 적용은 사람 단계(H02)다
- [ ] T051 [US5] `docs/ops/oci-production-store.md`: 질의 서비스 절을 더한다(quickstart 3절과 research R-14). 전제(ADR-022 승인, 팀원 동의, Tunnel 요금·데이터 처리 정책 기록, 바깥 방향 UDP 7844 읽기 전용 확인,
  운영 색인·마이그레이션 역할이 `qk.embedding_usage` 소유자나 슈퍼유저인지 확인), 전용 사용자 `qkquery`, `qk-query.service`(`User=qkquery`, `EnvironmentFile=/etc/qello-knowledge/query.env`, 루프백 포트, 격리 설정은
  `qk-sync-notify@.service`와 같은 수준), `query.env`(root:qkquery, 0640, 숨김 입력), `cloudflared`(원격 관리 터널, 2025.7.0 이상), 마이그레이션 0007 적용 순서(코드 병합 전), `qk_query` `LOGIN`·암호 숨김 입력,
  Workers VPC Service·Worker 배포·Discord 수신 주소·명령 등록, SC-010 공인 주소 포트 확인, 되돌리기. 주소·토큰·식별자는 placeholder로 쓴다

**Checkpoint**: US5 로컬 DB 시험 통과(`QK_REQUIRE_LOCALDB=1`).

---

## Phase 8: User Story 6 - 운영 담당자가 명령을 등록하고, 실행 환경의 한도 안인지 잰다 (P2)

**Goal**: `qk-query register-commands`와 실측에 쓸 운영 로그(단계별 시간·호출 수)를 둔다.

**Independent Test**: 등록 명령을 가짜 Discord 전송으로 두 번 실행해 결과가 같은지 본다(spec US6 Independent Test). 실측은 사람 단계.

- [ ] T052 [P] [US6] `tests/unit/query/test_bot_register_commands.py`(contracts/cli.md, contracts/discord-outbound.md 2절, spec FR-003·FR-022, SC-011 등록 부분): `--dry-run`은 contracts 2절 JSON 그대로(`name` `ask`, `contexts: [0]`,
  `질문` `required`·`min_length: 1`·`max_length` = `RetrievalSettings.question_max_chars`(2,000), `나만_보기` 선택 참·거짓)를 표준 출력에 내고 전송 0회, 토큰 없이도 됨. 실제 실행은 `PUT …/guilds/{guild_id}/commands`와 `Authorization: Bot`을 쓰고 두 번 실행해도
  같은 본문. 종료 코드 0 성공, 2 설정 오류(필요 설정: `DISCORD_APPLICATION_ID`, `QK_DISCORD_GUILD_ID`, `DISCORD_BOT_TOKEN`, 진입점 `REGISTER`), 3 Discord 오류(상태 코드만 출력, 응답 본문·토큰 없음)
- [ ] T053 [P] [US6] `tests/unit/query/test_bot_run_log.py`(spec FR-016·FR-021·FR-025, SC-012 자동 부분): 질의마다 운영 로그 한 줄, `timings_ms`에 `first_response`·`retrieve`·`generate`·`deliver`, `calls`에 단계별 실제 호출 수,
  합이 `QK_QUERY_CALL_LIMIT` 이하, `deliver_retries`·`deliver_failure`, 요약은 수치·이름 항목만, Neurons는 측정·추정 구분이 요약에 남음
- [ ] T054 [US6] `src/qello_knowledge/query/server.py`: `register-commands --env-file <경로> [--dry-run]` 하위 명령(T052)과 운영 로그 항목 채우기(T053)
- [ ] T055 [US6] 이 파일 "사람 단계"의 실측 기록 꼴을 확정한다: FR-025 항목(날짜, 질문 세트 이름·버전, 질문 수, SC-002 판정 기준, 생성 모델·프롬프트 버전, 질의 임베딩 모델, 인덱스 버전·색인 시점, 실행 방식)과
  질문별 처리 중 응답 시간·갱신까지 시간·단계별 시간·Worker CPU·외부 호출 수·Neurons(측정·추정). 질문 원문은 넣지 않고 번호로 가리킨다. 실측 질문 세트는 코드와 다른 커밋으로 넣는다(AGENTS.md 3.4 취지)

**Checkpoint**: 전체 단위·로컬 DB 시험 통과.

---

## Phase 9: Polish & Cross-Cutting

- [ ] T056 `.env.example`을 `uv run python -m qello_knowledge.config.example`로 다시 만든다(손으로 고치지 않는다). `tests/unit/config/test_example_file.py` 통과
- [ ] T057 [P] `docs/sdd/decisions/ADR-008-runtime-and-cost-cap.md`에 "질의 경로 실행 위치는 ADR-022가 일부 고친다(Proposed)" 링크 한 줄을 더한다. ADR-022 상태는 PR 리뷰 뒤 사람이 Accepted로 바꾼다
- [ ] T058 경계·회귀 확인: `uv run pytest tests/unit/test_boundaries.py`, 기존 QK-EMB-001·QK-RET-001·QK-GEN-001·QK-SEC-001·QK-STO-001·QK-SYN-001 시험 전부 통과, `uv run qk-migrate` 두 번(대상 `target=local` 확인, 두 번째 `applied=0`),
  `git diff origin/main --stat -- src/qello_knowledge/retrieval src/qello_knowledge/generation src/qello_knowledge/embedding src/qello_knowledge/security src/qello_knowledge/indexer src/qello_knowledge/adapters/workers_ai src/qello_knowledge/adapters/postgres/migrations/000[1-6]*`가
  비어 있음(바꾸지 않기로 한 파일)
- [ ] T059 quickstart.md 1절 전체 실행(`python scripts/preflight.py`, `git diff --check`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run qk-dev db up`, `uv run qk-migrate` × 2, `QK_REQUIRE_LOCALDB=1 uv run pytest`)과
  2절 로컬 질의 서비스 확인(가짜 제공자, 외부 호출 0건). 결과를 "실행 기록"에 적고 체크 표시를 갱신한다
- [ ] T060 독립 검토(다른 지침을 받은 별도 에이전트, AGENTS.md 2절)로 diff·시험 결과를 확인받고, 지적 반영 이력을 "실행 기록"에 남긴다
- [ ] T061 `TASK.md` Decisions·검증 기록 갱신, `/pr-draft-summary`로 PR 초안(CLAUDE.md 의무 사용)

---

## 사람 단계

모두 코드 병합 전 PR 리뷰(ADR-022 승인, 팀원(인스턴스 관리자) 동의)와 quickstart 3절 전제를 마친 뒤, 사람이 인증하고 명령마다 승인해서 한다. 값과 주소는 기록하지 않는다.

| 단계 | 내용 | 상태 | 비용·허락 |
| --- | --- | --- | --- |
| H00 | 운영 게이트 닫기: Cloudflare Tunnel 요금과 Worker·Tunnel 트래픽의 데이터 처리 정책(보존, 학습 사용)을 ADR-022 Data and cost에 URL과 함께 적는다. 인스턴스 바깥 방향 UDP 7844 읽기 전용 확인. 운영 색인·마이그레이션 역할의 `qk.embedding_usage` 소유 확인. 질의 서비스 전용 Workers AI 토큰 발급 계획(PR #62 계정 교체 결과와 맞춘다) | 구현 뒤 | 없음. 유료·학습 사용·장기 보존이면 멈추고 결정 재검토 |
| H01 | M-01: 시험 질의 서비스(연결 확인만)로 터널·VPC Service·Worker 배포, Discord 수신 주소 등록 때 서명 확인(401) 통과, Python Worker에서 VPC 바인딩 `fetch` 동작 확인 | H00 뒤 | 0 Neurons |
| H02 | quickstart 3절 1~8 운영 구성(마이그레이션 0007 적용과 `qk_query` 로그인, `query.env`, `qkquery`·`qk-query.service`, `cloudflared`, Worker, 명령 등록) | H01 뒤 | 0 Neurons |
| H03 | SC-010: 인스턴스 공인 주소로 DB 포트와 질의 서비스 포트 접속 실패 확인 | H02 뒤 | 0 Neurons |
| H04 | M-02·M-03: 연결 확인·허용 밖 채널 요청 각 10회 이상으로 Worker CPU 시간(Free 10 ms)과 첫 응답 시간 p50·p95 기록. CPU 한도를 자주 넘으면 중계만 TypeScript로 옮기는 안(research R-13)을 올린다 | H02 뒤 | 0 Neurons |
| H05 | M-04: 질문 세트 10~12개(자료로 답할 수 있는 질문, 자료에 없는 질문, "나만 보기" 1개 이상)로 SC-001·SC-002·SC-012·SC-013 기록, 합성 비밀값 질문으로 SC-005 화면 대조. 화면 기록은 값을 가린다 | H04 뒤 | 약 500~610 Neurons. 실행 전 예상량 보고와 사람 확인(AGENTS.md 3.5) |

---

## Dependencies & Execution Order

- Phase 1 → Phase 2 → US1 → US2 → US3 → US4. US5의 T048·T050(마이그레이션)은 Phase 2 뒤 언제든 할 수 있다. T049는 US1 뒤. US6은 US1 뒤(T054는 `server.py`라 T032·T043 뒤). Polish는 마지막.
- 같은 파일을 고치는 작업은 순서대로 한다: `discord/render.py` T026 → T036 → T042 → T046, `query/app.py` T031 → T041, `query/server.py` T032 → T043 → T054, `query/pipeline.py` T030 → T036, `config/check.py` T010 → T047,
  `config/registry.py` T008 한 번.
- T030은 T018(전송)·T028(작업)·T029(저장소 마감)에 기댄다. T033은 T027 뒤. T047은 T042·T046 뒤(무력화·분할 뒤 항목 최대 길이가 정해진다).
- 사람 단계 H00 → H01 → H02 → H03·H04 → H05.

## Parallel Example

```text
Phase 1: T001, T002, T003, T004
Phase 2: T005, T007, T009, T011, T013, T015, T017 (시험) → T006 → T008, T012, T014, T016, T018 → T010
US1:     T019, T020, T021, T022, T023, T024, T025 (시험) → T026, T027, T029 → T028 → T030 → T031 → T032, T033, T034
US3:     T037, T038, T039, T040 (시험) → T041, T042 → T043
US4:     T044, T045 (시험) → T046 → T047
US5:     T048, T049 (시험) → T050, T051
US6:     T052, T053 (시험) → T054 → T055
```

## Implementation Strategy

1. MVP: Phase 1·2 + US1. 여기서 멈춰도 가짜 제공자로 서명 검사 → 처리 중 응답 → 시작 확인 → 출처가 붙은 답변 갱신이 이어진다.
2. US2~US4로 안내 문구·안전 장치·분할을 완성한다. 여기까지가 운영에 올릴 수 있는 질의 서비스다.
3. US5로 DB 역할·운영 절차를, US6으로 명령 등록·실측 기록을 더한다.
4. 스토리마다 시험 → 구현 → 체크포인트 → 커밋(`/harness-commit`).
5. 구현과 자동 검증, 독립 검토, PR 리뷰 뒤 사람 단계 H00~H05.

## 실행 기록

- 2026-10-26 사용자 결정: 이 목록을 승인했다. plan에 없던 세 결정(`Entrypoint.REGISTER`, 순수 중계 판단 `discord/relay.py`, 진입점 계약을 고정한 기존 시험 3개의 기대값 갱신 예외)을 함께 받아들였다.
