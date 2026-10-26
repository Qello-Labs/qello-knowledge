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
  (재생성한 `.env.example`과 대조). 추가 예외(2026-10-26 사람 승인): `tests/unit/fakes.py::valid_environ()`에 다른 합성 값과 겹치지 않는 18자리 `QK_DISCORD_GUILD_ID` 한 줄을 더한다.
  검사 내용(색인 진입점에 Discord 설정 없음, 비밀값 비노출 등)은 그대로 둔다.
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

- [X] T001 `pyproject.toml`: `[project.optional-dependencies]`에 `query = ["cryptography>=43"]`(질의 서비스의 Ed25519 재검사, research R-04)를 더하고, 주석에 "질의 서비스만 쓴다. Worker 번들에는 넣지 않는다"를 적는다.
  `[dependency-groups] dev`에도 같은 항목을 더한다. 런타임 기본 `dependencies = []`는 그대로 둔다. `uv lock`으로 `uv.lock`을 갱신하고 고정된 `cryptography` 버전을 "실행 기록"에 적는다
- [X] T002 [P] 패키지 자리 만들기: `src/qello_knowledge/discord/__init__.py`, `src/qello_knowledge/adapters/discord/__init__.py`, `tests/unit/discord/`, `tests/localdb/query/conftest.py`.
  conftest는 `tests/localdb/retrieval/conftest.py` 꼴을 따른다(`pytestmark = pytest.mark.localdb`, `db_url`, 시험마다 `qk.embedding_usage`·`qk.embedding_usage_daily`·`qk.generation_usage`·`qk.generation_usage_daily`를 비우는
  자동 픽스처, 합성 문서·인덱스 버전을 심는 도우미). 시험 디렉터리에는 `__init__.py`를 만들지 않는다
- [X] T003 [P] `tests/unit/test_boundaries.py`: 기존 `RESTRICTED`·`ALLOWED_INTERNAL`·검사 함수는 그대로 두고, `discord` 전용 허용 목록(`qello_knowledge.domain`, `qello_knowledge.discord`)과 검사 함수를 따로 더한다
  (QK-GEN-001 `generation` 검사와 같은 꼴). `discord/signature.py`에만 `cryptography`(`cryptography.exceptions`, `cryptography.hazmat.primitives.asymmetric.ed25519`)를 허용한다. `adapters/discord/`는 표준 라이브러리와
  `qello_knowledge.domain`만 허용한다. 위반 사례 시험: `discord/`가 `qello_knowledge.adapters`·`security`·`retrieval`·`generation`·`psycopg`·`urllib.request`를 가져오면 실패, `discord/render.py`가 `cryptography`를 가져오면 실패,
  상대 경로 가져오기면 실패. 경로 비교는 `/`로 맞춘다(QK-GEN-001 실행 기록의 Windows 구분자 문제)
- [X] T004 [P] 시험 도우미 `tests/unit/discord/bot_builders.py`: (1) 시험 안에서 만든 Ed25519 키 쌍과 `sign(body: bytes, timestamp: str) -> headers`, (2) 상호작용 본문 만들기
  (`ping()`, `ask(question, private=None, guild=…, channel=…, channel_type=0, roles=(), interaction_id=…, token=…)`, `component()`, `other_command(name)`, 스레드는 `channel_type` 10·11·12, DM은 `guild_id` 없음),
  (3) 가짜 Discord 전송 `FakeDiscord`(받은 요청의 방법·경로·헤더·본문을 기록하고, 요청마다 정한 응답(200, 204, 404, 429+`retry_after`, 5xx, 연결 오류, 지연)을 돌려준다), (4) 가짜 시계 `FakeClock`(`now()`, `advance(s)`),
  (5) 합성 서버·채널·역할 식별자 상수(17~20자리 숫자, 실제 값 아님). 같은 파일에 `sign`이 다른 키로 서명한 경우를 만드는 도우미도 둔다

---

## Phase 2: Foundational

**목적**: 모든 스토리가 쓰는 타입·설정·서명 검사·본문 해석·안내 문구·Discord 전송. 이 단계가 끝나야 스토리 시험을 쓸 수 있다.

- [X] T005 [P] `tests/unit/discord/test_bot_domain.py`(data-model 2·3·5·6·7절): `Interaction`의 `token`·`question`이 `repr`에 나오지 않음, `InteractionKind` 값 3개(`PING`, `COMMAND`, `OTHER`),
  `ChannelKind` 4개(`TEXT`, `THREAD`, `DM`, `OTHER`), `AccessDecision` 7개(`ALLOWED`, `GUILD_OUTSIDE`, `CHANNEL_OUTSIDE`, `THREAD`, `DM`, `ROLE_MISSING`, `NOT_CONFIGURED`), `QueryStage` 값
  (`AWAITING_START`, `QUEUED`, `RETRIEVING`, `GENERATING`, `RENDERING`, `DELIVERING`, `DONE`, `NOT_STARTED`, `TIMED_OUT`, `FAILED`, `UNDELIVERED`), `FirstResponse`(유형 1·4·5, 플래그 64, `run_id`),
  `RenderedReply`(`messages`, `ephemeral`, `body_truncated`, `allowed_mentions == {"parse": []}`), `DedupEntry`(`interaction_id`, `stage` `IN_PROGRESS`·`DONE`, `expires_at`)에 질문·사용자 필드가 없음,
  `QueryRunLog` 필드가 data-model 5절 표(`run_id`, `access`, `private`, `status`, `failure`, `timings_ms`, `calls`, `deliver_retries`, `deliver_failure`, `retrieval_summary`, `generation_summary`)뿐이고 `to_json()`이
  키 순서가 고정된 한 줄 JSON. 모든 값은 불변(`frozen=True`)
- [X] T006 `src/qello_knowledge/domain/discord.py`: T005의 타입. 외부 SDK 타입 없음(C-06). `Interaction` 필드는 data-model 2절 표 그대로(`interaction_id`, `token`(repr 숨김), `kind`, `command`, `question`(repr 숨김),
  `private`, `guild_id`, `channel_id`, `channel_kind`, `member_roles`). 사용자 식별자·이름 필드를 두지 않는다
- [X] T007 [P] `tests/unit/config/test_bot_settings_registry.py`(data-model 1절): `Entrypoint.RELAY`(`"relay"`)와 `Entrypoint.REGISTER`(`"register"`, 명령 등록 전용) 추가. `specs_for(RELAY)`는
  `DISCORD_PUBLIC_KEY`, `QK_RELAY_TIMEOUT_SECONDS` 두 개뿐. `DISCORD_BOT_TOKEN`의 진입점은 `{REGISTER}`뿐이라 `specs_for(QUERY)`에 없음(R-12, spec FR-023). `DISCORD_APPLICATION_ID`·`QK_DISCORD_GUILD_ID`는 `{QUERY, REGISTER}`.
  `CLOUDFLARE_API_TOKEN`·`CLOUDFLARE_ACCOUNT_ID`는 `{QUERY, INDEX}`(R-08). 새 항목과 범위의 안·밖 경계값: `QK_RELAY_TIMEOUT_SECONDS` "0.5~2.8, 2.5", `QK_DISCORD_GUILD_ID` "17~20자리 숫자" 필수,
  `QK_DISCORD_ALLOWED_CHANNELS`·`QK_DISCORD_ALLOWED_ROLES` "쉼표로 나눈 17~20자리 숫자 목록"(빈 값 허용, 공백·중복·빈 항목 거부), `QK_QUERY_DEADLINE_SECONDS` "15~120, 55", `QK_QUERY_START_WAIT_SECONDS` "4~10, 5",
  `QK_QUERY_MIN_START_SECONDS` "8~60, 15", `QK_QUERY_NOTICE_GRACE_SECONDS` "1~30, 5", `QK_QUERY_CALL_LIMIT` "11~50, 20", `QK_DISCORD_MAX_MESSAGES` "2~10, 4", `QK_DISCORD_TITLE_MAX_CHARS` "20~200, 80",
  `QK_DISCORD_LINK_MAX_CHARS` "50~1000, 300", `QK_QUERY_WORKERS` "1~8, 2", `QK_QUERY_QUEUE_SIZE` "1~16, 4". 오류 문구에 값이 없음
- [X] T008 `src/qello_knowledge/config/registry.py`: T007 항목과 진입점. `config/example.py`의 `_LABELS`에 `RELAY: "중계 Worker"`, `REGISTER: "명령 등록"`을 더한다. `REGISTER` 진입점은 data-model 1절의
  "명령 등록 명령만"을 설정 레지스트리로 나타낸 것이다. 같은 작업에서 data-model 1절 표의 `DISCORD_BOT_TOKEN`·`DISCORD_APPLICATION_ID`·`QK_DISCORD_GUILD_ID` 진입점 열을 같은 값으로 고친다.
  공통 규칙의 예외 시험 세 개와 승인된 합성 설정 도우미만 갱신한다
- [X] T009 [P] `tests/unit/config/test_bot_cross_check.py`(data-model 1절 교차 규칙, spec FR-008·FR-016): 기본값 통과. 거부: `QK_QUERY_DEADLINE_SECONDS + QK_QUERY_NOTICE_GRACE_SECONDS ≥ 900`,
  `2 × QK_GEN_TIMEOUT_SECONDS + 5 > QK_QUERY_DEADLINE_SECONDS`(예: 시간 제한 30, 마감 60), `QK_QUERY_MIN_START_SECONDS ≥ QK_QUERY_DEADLINE_SECONDS`,
  `QK_QUERY_CALL_LIMIT < 7 + 4 + QK_DISCORD_MAX_MESSAGES × 2`(예: 메시지 상한 10, 호출 상한 20). 허용 채널 목록이 비면 경고(통과는 유지, spec FR-023). 결과에 값이 아니라 규칙 이름만 나옴
- [X] T010 `src/qello_knowledge/config/check.py`: 질의 진입점 교차 검사(T009). 기존 `_generation_check`·`_budget_check`는 그대로 두고 새 검사 함수를 `build_report`에 더한다.
  출처 목록 산식(FR-012)은 렌더러 상수가 필요해 US4(T047)에서 더한다
- [X] T011 [P] `tests/unit/discord/test_bot_signature.py`(spec FR-001, research R-04): 맞는 서명 통과, 다른 키·바뀐 본문·바뀐 시각·헤더 없음·16진이 아닌 서명·길이 틀린 서명 거부, 서명 시각이 현재와 300초 넘게
  차이(과거·미래 모두)면 거부, 300초 정확히는 통과, 숫자가 아닌 시각 거부. 검사 함수는 예외를 밖으로 내지 않고 참·거짓만 돌려준다. `cryptography`가 없을 때 `require_backend()`가 설치 안내 문구로 실패한다
  (`monkeypatch`로 가져오기 실패를 흉내 낸다)
- [X] T012 `src/qello_knowledge/discord/signature.py`: `verify(public_key_hex, signature_hex, timestamp, body, now) -> bool`(서명 대상은 `timestamp.encode() + body`), `require_backend()`.
  `cryptography`는 함수 안에서 가져온다(Worker 번들과 기본 설치에 영향 없음)
- [X] T013 [P] `tests/unit/discord/test_bot_interactions.py`(data-model 2절, spec FR-002·FR-003, Edge Cases): `PING` 해석, `/ask`의 `질문`·`나만_보기` 인자, `나만_보기` 없으면 거짓, 참·거짓이 아니면 참,
  본문 64 KiB 초과·JSON 실패·필수 필드 없음은 `OTHER`, 명령 이름이 `ask`가 아니거나 상호작용 `type`이 2가 아니면(버튼 3 등) `OTHER`, 채널 종류(`channel.type` 0·5 → `TEXT`, 10·11·12 → `THREAD`, `guild_id` 없음 → `DM`,
  그 밖 → `OTHER`), `member.roles` 읽기, `member.user`·`user`의 식별자·이름은 읽지 않음(결과 객체에 없음). 첫 응답 결정 `first_response(...)`의 응답 꼴: 연결 확인 `{"type": 1}`, 즉시 안내 유형 4·플래그 64·`allowed_mentions`,
  처리 중 응답 `{"type": 5}`·"나만 보기"면 `{"type": 5, "data": {"flags": 64}}`(contracts/relay.md 2절 표)
- [X] T014 `src/qello_knowledge/discord/interactions.py`: `parse(body: bytes) -> Interaction`, 응답 JSON 만들기(`pong()`, `notice(text)`, `deferred(private)`). 허용 범위·비밀값·중복·자리 판정은 받지 않고
  `query/app.py`가 조립한다
- [X] T015 [P] `tests/unit/discord/test_bot_notices.py`(spec FR-011 표, data-model 6절): `RetrievalFailure` 9개와 `GenerationFailure` 6개, 생성 상태 5개가 빠짐없이 한 문구에 대응(새 값이 생기면 시험이 실패),
  문구가 spec FR-011 표 그대로(질문 길이 문구의 "2,000자"는 `question_max_chars`를 따름), 고정 안내(지원하지 않는 요청 "지원하지 않는 요청입니다.", 허용 범위 "이 채널에서는 `/ask`를 쓸 수 없습니다.",
  비밀값 FR-006 문장, 중복 "이미 처리 중인 요청입니다.", 자리 없음 "지금 요청이 많습니다. 잠시 후 다시 질문해 주세요.", 시작 안 됨 "요청을 처리하지 못했습니다. 잠시 후 다시 질문해 주세요.",
  Worker 실패 "지금은 답할 수 없습니다. 잠시 후 다시 질문해 주세요.", 질의 마감 초과, 예상하지 못한 실패), 실패 안내 끝에 질의 실행 식별자의 짧은 꼴(`(확인 번호 1a2b3c4d)` 같은 꼴, 뒤 8자)을 붙임,
  문구에 실패 종류 이름(`store_unavailable` 등)이 없음, 다음 행동 구분(다시 시도 / 운영 담당자에게 알림 / 내일 다시)
- [X] T016 `src/qello_knowledge/discord/notices.py`: 안내 문구 표 한 곳(T015). 문구는 상수, 대응은 사전
- [X] T017 [P] `tests/unit/adapters/test_bot_discord_webhook.py`(contracts/discord-outbound.md, research R-05 전달 시간, spec FR-009): 주입한 전송(`FakeDiscord`)으로 확인한다.
  첫 메시지 `PATCH /api/v10/webhooks/{application_id}/{token}/messages/@original`, 이어지는 메시지 `POST /api/v10/webhooks/{application_id}/{token}`(질문자만 보기면 `flags: 64`), 본문
  `{"content": …, "allowed_mentions": {"parse": []}}`, `User-Agent: DiscordBot (https://github.com/Qello-Labs/qello-knowledge, <버전>)`, 인증 헤더 없음. 다시 시도: 메시지마다 최대 2회 시도, `429`(`retry_after`)·`5xx`·연결 오류,
  첫 메시지 첫 시도의 `404`면 1초 뒤 1회, 두 번째 `404`와 이어지는 메시지의 `404`와 그 밖 `4xx`는 다시 시도 없이 `UNDELIVERED`. 호출마다 시간 제한 = min(3초, 안내 전달 마감까지 남은 시간),
  (대기 + 1초) > 남은 시간이면 다시 시도 안 함, 남은 시간 < 1초면 호출 0회로 `UNDELIVERED`. 단계별로 늦게 오는 응답을 넣어 호출 전체 경과 시간이 마감을 넘지 않음(완료·중단 시각). 첫 메시지가 끝내 실패하면 이어지는 메시지 0회.
  결과에 실패 종류와 다시 시도 횟수만 있고 토큰·경로·응답 본문이 없음. 명령 등록 `PUT /api/v10/applications/{application_id}/guilds/{guild_id}/commands`, 헤더 `Authorization: Bot <토큰>`
- [X] T018 `src/qello_knowledge/adapters/discord/webhook.py`: T017. `urllib` 기반 기본 전송과 시험용 주입 자리. 경로의 토큰은 예외 문구·로그에 넣지 않는다(예외는 상태 코드와 실패 종류만)

**Checkpoint**: `uv run pytest tests/unit/discord tests/unit/config tests/unit/adapters/test_bot_discord_webhook.py tests/unit/test_boundaries.py` 통과

---

## Phase 3: User Story 1 - 허용된 채널에서 `/ask`로 질문하고 출처가 붙은 답을 받는다 (P1) 🎯 MVP

**Goal**: 서명이 맞는 허용 채널 `/ask`에 처리 중 응답을 바로 돌려주고, 시작 확인 뒤 검색·생성을 질의 마감 안에서 돌려 답변 본문과 출처 목록으로 한 번 갱신한다.

**Independent Test**: 시험 키로 서명한 가짜 상호작용을 `query/app.py`에 넣고, 가짜 검색·생성 제공자 결과를 가짜 Discord 전송이 받은 갱신 메시지로 본다(spec US1 Independent Test).

### Tests for User Story 1

- [X] T019 [P] [US1] `tests/unit/query/test_bot_first_response.py`(contracts/relay.md 2절, spec US1-1·US1-5·US1-6, FR-007): `POST /discord/interactions`에 연결 확인 → `{"type": 1}`, 허용된 `/ask` → `{"type": 5}`와 응답 헤더
  `X-QK-Run`(형식 `q-<UTC 시각>-<16진 8자>`), "나만 보기" → `flags: 64`. 응답을 돌려줄 때까지 검색·생성·저장소·Discord 호출 0회(가짜들의 호출 기록), 작업은 `AWAITING_START`로 등록
- [X] T020 [P] [US1] `tests/unit/query/test_bot_start_confirm.py`(contracts/relay.md 3절, research R-03): `POST /discord/interactions/start`(`{"run_id": …}`, 원본 서명 헤더 두 개)가 시작 대기 중이고 서명이 같으면 `204`이고
  작업이 `QUEUED`로 감. 없는 `run_id`, 서명 불일치, 이미 시작함, 시작 대기 만료는 `409`이고 상태 변화 없음. 시작 확인 없이 `QK_QUERY_START_WAIT_SECONDS`(가짜 시계 5초)가 지나면 `NOT_STARTED` → 첫 메시지
  `PATCH` 한 번("요청을 처리하지 못했습니다…"), 검색·생성 0회, 수명 자리 반환. 시작 확인과 만료가 같은 순간에 오면 둘 중 하나만 일어남. 첫 `PATCH`가 `404`면 1초 뒤 1회만 다시 보냄
- [X] T021 [P] [US1] `tests/unit/query/test_bot_jobs.py`(research R-05, data-model 5·7절, spec FR-010): 수명 자리 `C = QK_QUERY_WORKERS + QK_QUERY_QUEUE_SIZE`(기본 6)를 넘는 새 요청은 "지금 요청이 많습니다" 즉시 안내,
  끝 상태(`DONE`, `UNDELIVERED`)에서 자리 반환, 실행 자리(기본 2)는 `RETRIEVING`에서 잡고 호출이 실제로 끝날 때 반환(질의 마감으로 버린 작업도 끝날 때까지 쥠), 늦게 끝나는 작업 2개가 실행 자리를 쥐어도 동시 검색·생성 ≤ 2,
  `QUEUED`에서 실행 자리를 잡을 때 남은 시간 < `QK_QUERY_MIN_START_SECONDS`면 `TIMED_OUT`, 마감 감시는 상태 전이와 전달 예약만 하고 Discord를 직접 부르지 않음, 전달 권한은 작업마다 한 번(결과·시간 초과·`NOT_STARTED` 중
  먼저 얻은 쪽), 전달 풀 크기 = `C`이고 전달 요청이 풀을 기다리지 않음, 동시 만료 6개·느린 전송·`429` 대기·앞 전송이 느린 동안 새 요청이 계속 오는 경우를 조합해 모든 전송이 안내 전달 마감 안에 끝나거나 멈춤.
  중복 판정: 처리 중·끝난 뒤(900초 안) 같은 상호작용 식별자는 "이미 처리 중인 요청입니다." 즉시 안내이고 질의·갱신 0회 추가, 900초 뒤 항목이 지워짐, 항목에 질문·사용자 정보가 없음, 동시 두 요청 중 하나만 처리.
  새 실행기(재시작 흉내)에 같은 상호작용을 넣으면 다시 처리됨을 기대 결과로 고정(spec SC-011 예외)
- [X] T022 [P] [US1] `tests/unit/query/test_bot_pipeline.py`(research R-06·R-11, spec FR-008·FR-015·FR-017, US1-2·US1-3·US1-4): 가짜 검색·생성으로 답변 결과 → 첫 메시지 `PATCH` 한 번, 같은 내용 두 번 없음, 스트리밍 없음.
  질의별 생성 설정: 남은 시간 R에서 시간 제한 = min(설정 시간 제한, ⌊(R − 5) ÷ 2⌋), 생성 마감 = min(설정 생성 마감, R), 기본 설정이 질의 마감보다 짧으면 설정 그대로, R < 7이면 생성 0회와 시간 초과 안내.
  임베딩 전송 시간 제한 = min(10, R − 여유), 임베딩 재시도 대기 뒤 남은 시간이 시간 제한보다 짧으면 대기 없이 `DeadlineReached` → 시간 초과 안내, 검색 재시도 대기는 질의 마감 안에서만(FR-017).
  `GenerationRequest.run_id`가 `X-QK-Run`과 같음. 질의 마감에서 생성이 안 끝나면 기다리지 않고 시간 초과 안내, 늦게 끝난 생성 결과는 버리고 장부 기록(`MemoryLedger`)은 남음, 저장소·장부 연결이 `finally`에서 닫힘.
  검색 요약의 외부 호출 수 ≤ 7, 생성 ≤ 4, 질의 전체 ≤ `QK_QUERY_CALL_LIMIT`(FR-016)
- [X] T023 [P] [US1] `tests/unit/discord/test_bot_render_basic.py`(spec FR-013, data-model 6절, US1-2): 답변 본문 뒤 출처 목록, 목록 머리 "자료 기준: 색인된 문서", 항목 꼴
  `[S1] <제목> · <URL> · 버전 <앞 7자> · 수정 2026-10-20 · 수집 2026-10-24 09:30 KST`(커밋 해시(40자 16진)면 앞 7자, 아니면 앞 12자, 수정일 없으면 "수정 미상", 날짜는 한국 시간), URL은 `<…>`로 감쌈, 링크 없으면 "링크 없음",
  제목이 `QK_DISCORD_TITLE_MAX_CHARS`(80)를 넘으면 줄이고 "…", 링크가 `QK_DISCORD_LINK_MAX_CHARS`(300)를 넘으면 "링크 생략(길이 초과)"(링크는 자르지 않음), 항목 순서·개수가 생성 결과와 같음, 모든 메시지 2,000자 이하,
  같은 입력이면 같은 결과. 출처 목록은 생성 결과의 출처에서만 만들고 본문에서 가져오지 않음
- [X] T024 [P] [US1] `tests/unit/discord/test_bot_relay.py`(contracts/relay.md 1절): Worker 중계 판단의 순수 함수. 본문 64 KiB 초과 → `413`, 서명 헤더 없음·시각 차이 300초 초과 → `401`(서명 검사 전), 질의 서비스 실패(연결 실패,
  제한 시간 초과, `200` 아닌 응답) → 실패 안내 JSON(`{"type": 4, "data": {"content": "지금은 답할 수 없습니다. 잠시 후 다시 질문해 주세요.", "flags": 64, "allowed_mentions": {"parse": []}}}`), 원본 `type`이 1이면 질의 서비스 없이
  `{"type": 1}`, 응답 헤더 `X-QK-Run`이 있을 때만 시작 확인 요청(본문 `{"run_id": …}`, 원본 서명 헤더 두 개)을 만듦, 요청 하나에 질의 서비스 호출 계획 ≤ 2, 로그 항목은 `relayed`·`relay_failed`·`start_failed`와 걸린 시간뿐
- [X] T025 [P] [US1] `tests/localdb/query/test_bot_store_deadline.py`(research R-06, quickstart 1절 검색 마감 주입): `PostgresStore(url, deadline=…)`. 검색·문맥 호출 직전 남은 시간이 모자라면 저장소 질의 0회로 시간 초과 오류,
  `pg_sleep`으로 오래 걸리는 질의는 마감에 연결 취소로 시간 초과 오류, 질의 완료와 타이머 해제가 겹쳐도 예외·남은 타이머 없음, 취소 뒤 연결이 정리되고 다음 호출이 새 연결로 됨, 남은 시간 < 연결 제한 10초면 새 연결을 맺지 않음,
  `deadline` 없으면 지금 동작 그대로(기존 `tests/localdb/retrieval` 시험이 바뀌지 않고 통과), 검색 요약의 외부 호출 수가 FR-026의 계수 합(저장소 질의 + 임베딩 제공자 호출 + 시도마다 사용량 기록)과 같음(`SET` 문장을 보내지 않음)

### Implementation for User Story 1

- [X] T026 [P] [US1] `src/qello_knowledge/discord/render.py`: 답변 본문 + 출처 목록 기본 렌더링(T023). 길이 상수와 항목 꼴은 모듈 상수로 둔다(US4의 산식이 쓴다). 서식·멘션 무력화는 US3(T042), 분할은 US4(T046)에서 넓힌다
- [X] T027 [P] [US1] `src/qello_knowledge/discord/relay.py`: Worker 중계 판단 순수 함수(T024). Worker와 같은 패키지를 쓰므로 표준 라이브러리만 가져온다
- [X] T028 [US1] `src/qello_knowledge/query/jobs.py`: 수명 자리·실행 자리·마감 감시 스레드·전달 실행기·전달 권한·중복 판정 사전(T020·T021). 시계·실행기·전달 함수를 주입받는다
- [X] T029 [US1] `src/qello_knowledge/adapters/postgres/store.py`: 선택 인자 `deadline: Callable[[], float] | None = None`(남은 초를 돌려주는 함수). 검색·문맥 호출(`search_vector`, `search_keyword`, `search_keyword_terms`,
  `chunk_context`, `chunk_neighbors`, `source_revisions`)마다 실행 직전 남은 시간 확인, 질의 동안만 `Connection.cancel_safe()`를 부르는 타이머(취소는 타이머 스레드에서), 취소되면 시간 초과 오류(`StoreError` 하위)로 바꿈(T025).
  색인 쓰기 메서드는 바꾸지 않는다
- [X] T030 [US1] `src/qello_knowledge/query/pipeline.py`: 작업마다 검색 부품을 새로 만든다. `postgres_search`와 같은 부품(`PostgresStore(url, deadline=…)`, `PostgresUsageLedger`, `EmbeddingService(…, retry_policy=RetryPolicy(max_retries=1),
  retry_delay=query_retry_delay, sleep=<마감 확인 sleep>)`, `WorkersAiRestProvider(transport=UrllibTransport(timeout=…))`)과 `postgres_ask`와 같은 생성 부품(`PostgresGenerationLedger`, `WorkersAiGenerationProvider`)을
  주입 가능한 공장으로 조립하고, `retrieve` → `generate(request, deps, settings)`(질의별 `GenerationSettings`, research R-06) → `render` → 전달(T018)을 잇는다(T022). `indexer/ask_cli.py`·`search_cli.py`는 가져다 쓰기만 한다
- [X] T031 [US1] `src/qello_knowledge/query/app.py`: `POST /discord/interactions`, `POST /discord/interactions/start` 경로. 처리 순서는 contracts/relay.md 2절(서명 재검사 → 해석 → 연결 확인 → 허용 범위 → 비밀값 → 중복 → 수명 자리 →
  시작 대기 등록). 허용 범위·비밀값은 이 단계에서 통과로 두는 자리만 만들고 US3(T041)에서 채운다. 기존 `GET /healthz` 동작과 `tests/unit/query/test_app.py`는 그대로다. 요청 헤더·원본 본문을 받도록 `handle`을 넓히되 기존 호출 꼴도 받는다
- [X] T032 [US1] `src/qello_knowledge/query/server.py`: `serve`가 원본 본문(상한 64 KiB)과 헤더를 `handle`에 넘기고, 시작할 때 설정 검사(필수 없음·교차 규칙 위반이면 종료 코드 2, 허용 채널 비면 경고 뒤 계속)와
  `require_backend()`를 하고, 작업 실행기를 띄운다(contracts/cli.md). 기존 `tests/unit/query/test_server.py`는 그대로 통과한다
- [X] T033 [US1] `src/qello_knowledge/query/worker.py`: 중계 Worker로 바꾼다. 설정은 `Entrypoint.RELAY`만 읽고, Web Crypto `crypto.subtle.verify("Ed25519", …)`로 서명을 검사하고, `env.QUERY_SERVICE.fetch(…)`(VPC 바인딩)로 중계하고,
  `ctx.waitUntil`로 시작 확인을 보낸다. 판단은 `discord/relay.py`가 한다. 이 파일은 Workers 런타임에서만 가져오므로 시험에서 가져오지 않는다(기존 주석 유지). 실제 실행 확인은 사람 단계 H01
- [X] T034 [US1] `wrangler.toml`: Worker 이름, `main = "src/qello_knowledge/query/worker.py"`, `compatibility_flags = ["python_workers"]`, `compatibility_date`, VPC 바인딩 `QUERY_SERVICE`(`service_id = "<vpc-service-id>"` placeholder),
  `[vars] QK_RELAY_TIMEOUT_SECONDS = "2.5"`. `DISCORD_PUBLIC_KEY`는 `wrangler secret`로 넣는다는 주석만 둔다. 계정 ID·서비스 ID·주소를 넣지 않는다. `pywrangler` 설정 꼴은 QK-FND-001 research를 따르고, 구현 때 확인한 문서 URL을 "실행 기록"에 적는다

**Checkpoint**: US1 시험과 기존 시험 전부 통과. 가짜 제공자로 처리 중 응답 → 시작 확인 → 답변 갱신이 이어진다(quickstart 2절을 가짜 전송으로).

---

## Phase 4: User Story 2 - 결과가 답이 아닐 때 무슨 일인지 알아볼 수 있게 안내받는다 (P1)

**Goal**: 확인 불가·출처 확인 안 됨·출력 잘림 표시와 검색·생성 실패 종류별 안내를 spec FR-011 표대로 보인다.

**Independent Test**: 가짜 생성 제공자로 상태와 표시를 하나씩 만들어 갱신 메시지를 본다(spec US2 Independent Test).

- [X] T035 [P] [US2] `tests/unit/query/test_bot_status_messages.py`(spec US2-1~US2-5, FR-011, SC-006): 확인 불가 → 생성 결과 본문 그대로, 출처 목록 없음. 출처 확인 안 됨(`flags.unsupported_answer`) → 본문 앞
  "⚠️ 출처를 확인하지 못한 답변입니다. 원문으로 확인해 주세요." 줄, 출처 목록 없음. 출력 잘림(`flags.truncated`) → 본문 끝 "(답변이 길어 일부가 잘렸습니다.)". 검색 실패 9종·생성 실패 6종·질의 마감 초과·예상하지 못한 예외 각각 → FR-011 문구와
  짧은 실행 식별자. 제공자 할당 소진 → "오늘 사용 한도에 닿아…". 질의 중 전송 차단(검색 `outgoing_blocked`, 생성 상태 "외부 전송 차단") → FR-006 문장, 공개 범위는 처리 중 응답 그대로. 모든 메시지에 실패 종류 이름·예외 메시지·주소·질문 원문이 없음
- [X] T036 [US2] `src/qello_knowledge/discord/render.py`·`src/qello_knowledge/query/pipeline.py`: 표시 줄과 실패 안내 연결(T035). 예상하지 못한 예외는 작업 경계에서 잡아 "요청을 처리하지 못했습니다…"로 보낸다

**Checkpoint**: US1·US2 시험 통과.

---

## Phase 5: User Story 3 - 허용 범위 밖이나 위험한 요청은 처리하지 않는다 (P1)

**Goal**: 서명 거부, 허용 범위 판정, 처리 중 응답 전 비밀값 검사, 알림·서식 무력화, 원문 비기록.

**Independent Test**: 서명이 틀린 요청, 허용 밖 요청, 비밀값 질문, 멘션 꼴을 심은 가짜 결과로 응답·외부 호출 수·알림 설정을 본다(spec US3 Independent Test).

- [X] T037 [P] [US3] `tests/unit/discord/test_bot_access.py`(data-model 2절, spec FR-004, US3-2·US3-3): 허용 채널의 글 채널 → `ALLOWED`, 다른 서버 → `GUILD_OUTSIDE`, 목록 밖 채널 → `CHANNEL_OUTSIDE`, 허용 채널 아래 스레드 → `THREAD`,
  DM → `DM`, 허용 역할 목록이 있고 역할이 없음 → `ROLE_MISSING`, 역할 목록이 비면 역할 제한 없음, 허용 채널 목록이 비었거나 서버가 설정되지 않음 → `NOT_CONFIGURED`(닫힘)
- [X] T038 [P] [US3] `tests/unit/query/test_bot_reject_paths.py`(spec US3-1·US3-2·US3-4, FR-001·FR-006·FR-007, SC-003·SC-004·SC-005·SC-013 자동 부분): 서명 없음·틀림·시각 초과 → `401`, 검색·생성·Discord 호출 0회, 운영 로그 0줄.
  허용 밖 각 경우와 빈 허용 목록 → 질문자만 보는 허용 범위 안내, 검색·생성 0회. `tests/unit/synthetic_secrets.py`의 합성 비밀값이 든 질문 → 질문자만 보는 FR-006 안내, 임베딩·생성 0회, 안내·로그에 맞은 문자열 0건.
  지원하지 않는 요청 → 질문자만 보는 안내. 이 즉시 안내들은 "나만 보기" 인자와 상관없이 플래그 64
- [X] T039 [P] [US3] `tests/unit/query/test_bot_no_raw_logs.py`(spec FR-021, SC-009): 모든 경로(답변, 확인 불가, 실패 주입 전부, 시간 초과, 전달 실패, 서명 거부, 중복, 자리 없음)의 표준 오류 운영 로그와 예외 문구를 모아
  합성 질문 원문·답변 본문·청크 본문·출처 제목·링크·상호작용 식별자·토큰·서명·사용자 식별자·채널 식별자·`DATABASE_URL`·`CLOUDFLARE_API_TOKEN` 표식이 0건
- [X] T040 [P] [US3] `tests/unit/discord/test_bot_neutralize.py`(spec FR-014, US3-5, SC-008): 답변 본문·출처 제목에 `@everyone`, `@here`, `<@123…>`, `<@&123…>`를 심어도 모든 메시지의 `allowed_mentions`가 `{"parse": []}`,
  출처 제목의 `[ ] ( ) * _ ~ \` | >` 같은 서식·링크 꼴 글자는 `\`로 바뀌어 링크 꼴을 바꾸지 못함, 수정일 같은 자료 유래 글도 같음, 답변 본문의 굵게·목록·코드 서식은 그대로
- [X] T041 [US3] `src/qello_knowledge/discord/access.py`와 `src/qello_knowledge/query/app.py`: 허용 범위 판정(T037)과 처리 중 응답 전 비밀값 검사(`indexer/embedding.py`의 `security_outgoing_check(policy)`에 질문만, 출처 없이) 연결(T038).
  정책은 `serve` 시작 때 `config/sources.toml`·`config/security_exceptions.toml`로 한 번 읽는다(`ask_cli`와 같은 방식). 읽기에 실패하면 시작하지 않는다(종료 코드 2)
- [X] T042 [US3] `src/qello_knowledge/discord/render.py`: 자료 유래 글의 서식 무력화(T040). 무력화 뒤 길이가 렌더러 상수(항목 최대 길이)에 반영되게 한다
- [X] T043 [US3] 운영 로그 한 줄(`QueryRunLog.to_json()`)을 `query/server.py`에서 표준 오류로 쓰고, 예외 문구에서 원문이 나가지 않게 작업 경계에서 바꾼다(T039)

**Checkpoint**: US1~US3 시험 통과.

---

## Phase 6: User Story 4 - 긴 답변과 출처 목록이 잘리지 않고 나뉜다 (P1)

**Goal**: 메시지 2,000자·메시지 수 상한 안에서 문단·문장 경계로 나누고, 출처 목록은 빠짐없이 마지막 메시지들에 둔다.

**Independent Test**: 긴 본문, 긴 코드 블록, 경계의 링크·인용 표기, 출처 최대 수로 분할 결과를 본다(spec US4 Independent Test).

- [X] T044 [P] [US4] `tests/unit/discord/test_bot_split.py`(spec FR-012, US4-1~US4-4, SC-007): 한도 안이면 메시지 1개, 나눈 자리 문단 → 문장 → 공백 순, 링크·`[S번호]`·무력화한 글 중간에서 안 나눔, 공백 없는 긴 문자열은 한도에서 자름,
  한도를 넘는 링크 하나는 "(긴 링크 생략)", 코드 블록이 나뉘면 조각마다 닫고 같은 언어 표시로 다시 엶, 메시지 수 상한(4)을 넘는 본문은 줄이고 "(답변이 길어 일부를 생략했습니다.)", 출처 목록은 줄이지 않고 항목 사이에서만 나뉘며 본문 뒤 마지막 메시지들에 옴,
  설정이 허용하는 최대 수(`expand_top` 8)의 출처가 모두 최대 길이 제목(무력화로 길이가 최대로 늘어나는 글)·긴 링크를 가진 경우에도 모든 메시지 ≤ 2,000자이고 메시지 수 ≤ 상한, 같은 입력이면 같은 결과, "나만 보기"면 이어지는 메시지도 질문자만 보기
- [X] T045 [P] [US4] `tests/unit/config/test_bot_source_list_check.py`(data-model 1절 출처 목록 산식, SC-007 마지막 문장): `항목 최대 길이`를 렌더러가 내보내는 실제 문자열(최대 길이 제목 전부 무력화, 비해시 버전 12자, 링크 상한)로 계산해
  상수와 같음을 고정, 기본 설정(`expand_top` 8, 2,000자, 제목 80, 링크 300, 메시지 4)은 통과(메시지당 항목 수와 필요한 메시지 수를 "실행 기록"에 적는다), 제목·링크 상한을 키우거나 메시지 상한을 줄여 `⌈expand_top ÷ 메시지당 항목⌉ > 메시지 수 상한 − 1`이 되는 설정은 모두 거부
- [X] T046 [US4] `src/qello_knowledge/discord/render.py`: 분할(T044). 첫 메시지가 처리 중 응답을 바꾸는 글이다
- [X] T047 [US4] `src/qello_knowledge/config/check.py`: 출처 목록 산식 검사(T045). 렌더러 상수를 가져온다(`config` → `discord` 방향만)

**Checkpoint**: US1~US4 시험 통과.

---

## Phase 7: User Story 5 - 질의 경로가 운영 저장소에 열린 포트 없이 최소 권한으로 붙는다 (P2)

**Goal**: `qk_query` 역할과 `qk.embedding_usage` RLS로 질의 서비스 권한을 검색 읽기와 질의 사용량 기록으로 한정하고, 저장소 장애를 안내로 바꾸며, 운영 절차를 쓴다.

**Independent Test**: 로컬 DB에서 `qk_query`로 허용·거부 목록을 확인한다(spec US5 Independent Test 로컬 부분). 공인 주소 접속 시험은 사람 단계 H03.

- [X] T048 [P] [US5] `tests/localdb/query/test_bot_query_role.py`(data-model 4절, spec FR-019, SC-010 로컬 부분): 마이그레이션 뒤 시험 안에서 `qk_query`에 시험용 로그인을 준(`SET ROLE qk_query`로 대신해도 된다) 연결로
  성공: 검색·문맥 함수(`qk.search_vector`, `qk.search_keyword`, `qk.search_keyword_terms`, `qk.chunk_context`, `qk.chunk_neighbors`), `qk.embedding_record`(`purpose = 'query'`), `qk.embedding_usage_today`, `qk.generation_record`,
  `qk.generation_usage_today`, 저장소 검색 경로(`PostgresStore`) 한 번. 거부: 예산이 충분한 값으로 부른 `qk.embedding_reserve`(INSERT 분기까지 가서 RLS 거부), 직접 `purpose = 'index'` INSERT, `qk.artifact`·`qk.chunk`·`qk.embedding`·`qk.index_version`
  쓰기·지우기, 사용량 기존 행 `UPDATE`·`DELETE`, `qk.embedding_usage_daily`·`qk.generation_usage_daily` 쓰기, 정산(`qk.embedding_settle`)·정리(`*_prune`) 함수, `qk.sync_*` 읽기·쓰기, `CREATE`·`ALTER`. 소유자 역할로 `qk.embedding_reserve`와
  `purpose = 'index'` 기록이 그대로 됨(RLS가 소유자에 영향 없음). 마이그레이션을 두 번 실행해도 같음
- [X] T049 [P] [US5] `tests/unit/query/test_bot_store_unavailable.py`(spec US5-4, FR-020): 저장소 연결 실패·질의 시간 초과를 넣으면 질의 마감 안에 "지금은 자료를 검색할 수 없습니다…" 안내로 갱신, 검색 재시도는 마감 안에서만
- [X] T050 [US5] `src/qello_knowledge/adapters/postgres/migrations/0007_query_role.sql`: `NOLOGIN` 역할 `qk_query`(이미 있으면 만들지 않음), data-model 4절 권한 목록 그대로, `qk.embedding_usage`에 `ENABLE ROW LEVEL SECURITY`와
  `FOR SELECT TO qk_query USING (true)`, `FOR INSERT TO qk_query WITH CHECK (purpose = 'query')` 정책. `FORCE ROW LEVEL SECURITY`를 쓰지 않고, `PUBLIC`의 함수 `EXECUTE`를 거두지 않으며, `UPDATE`·`DELETE` 정책을 두지 않는다.
  권한 목록을 함수가 실제로 쓰는 표·시퀀스와 대조한 결과(빠진 권한, 더한 권한)를 data-model 4절과 "실행 기록"에 적는다. 운영 적용은 사람 단계(H02)다
- [X] T051 [US5] `docs/ops/oci-production-store.md`: 질의 서비스 절을 더한다(quickstart 3절과 research R-14). 전제(ADR-022 승인, 팀원 동의, Tunnel 요금·데이터 처리 정책 기록, 바깥 방향 UDP 7844 읽기 전용 확인,
  운영 색인·마이그레이션 역할이 `qk.embedding_usage` 소유자나 슈퍼유저인지 확인), 전용 사용자 `qkquery`, `qk-query.service`(`User=qkquery`, `EnvironmentFile=/etc/qello-knowledge/query.env`, 루프백 포트, 격리 설정은
  `qk-sync-notify@.service`와 같은 수준), `query.env`(root:qkquery, 0640, 숨김 입력), `cloudflared`(원격 관리 터널, 2025.7.0 이상), 마이그레이션 0007 적용 순서(코드 병합 전), `qk_query` `LOGIN`·암호 숨김 입력,
  Workers VPC Service·Worker 배포·Discord 수신 주소·명령 등록, SC-010 공인 주소 포트 확인, 되돌리기. 주소·토큰·식별자는 placeholder로 쓴다

**Checkpoint**: US5 로컬 DB 시험 통과(`QK_REQUIRE_LOCALDB=1`).

---

## Phase 8: User Story 6 - 운영 담당자가 명령을 등록하고, 실행 환경의 한도 안인지 잰다 (P2)

**Goal**: `qk-query register-commands`와 실측에 쓸 운영 로그(단계별 시간·호출 수)를 둔다.

**Independent Test**: 등록 명령을 가짜 Discord 전송으로 두 번 실행해 결과가 같은지 본다(spec US6 Independent Test). 실측은 사람 단계.

- [X] T052 [P] [US6] `tests/unit/query/test_bot_register_commands.py`(contracts/cli.md, contracts/discord-outbound.md 2절, spec FR-003·FR-022, SC-011 등록 부분): `--dry-run`은 contracts 2절 JSON 그대로(`name` `ask`, `contexts: [0]`,
  `질문` `required`·`min_length: 1`·`max_length` = `RetrievalSettings.question_max_chars`(2,000), `나만_보기` 선택 참·거짓)를 표준 출력에 내고 전송 0회, 토큰 없이도 됨. 실제 실행은 `PUT …/guilds/{guild_id}/commands`와 `Authorization: Bot`을 쓰고 두 번 실행해도
  같은 본문. 종료 코드 0 성공, 2 설정 오류(필요 설정: `DISCORD_APPLICATION_ID`, `QK_DISCORD_GUILD_ID`, `DISCORD_BOT_TOKEN`, 진입점 `REGISTER`), 3 Discord 오류(상태 코드만 출력, 응답 본문·토큰 없음)
- [X] T053 [P] [US6] `tests/unit/query/test_bot_run_log.py`(spec FR-016·FR-021·FR-025, SC-012 자동 부분): 질의마다 운영 로그 한 줄, `timings_ms`에 `first_response`·`retrieve`·`generate`·`deliver`, `calls`에 단계별 실제 호출 수,
  합이 `QK_QUERY_CALL_LIMIT` 이하, `deliver_retries`·`deliver_failure`, 요약은 수치·이름 항목만, Neurons는 측정·추정 구분이 요약에 남음
- [X] T054 [US6] `src/qello_knowledge/query/server.py`: `register-commands --env-file <경로> [--dry-run]` 하위 명령(T052)과 운영 로그 항목 채우기(T053)
- [X] T055 [US6] 이 파일 "사람 단계"의 실측 기록 꼴을 확정한다: FR-025 항목(날짜, 질문 세트 이름·버전, 질문 수, SC-002 판정 기준, 생성 모델·프롬프트 버전, 질의 임베딩 모델, 인덱스 버전·색인 시점, 실행 방식)과
  질문별 처리 중 응답 시간·갱신까지 시간·단계별 시간·Worker CPU·외부 호출 수·Neurons(측정·추정). 질문 원문은 넣지 않고 번호로 가리킨다. 실측 질문 세트는 코드와 다른 커밋으로 넣는다(AGENTS.md 3.4 취지)

**Checkpoint**: 전체 단위·로컬 DB 시험 통과.

---

## Phase 9: Polish & Cross-Cutting

- [X] T056 `.env.example`을 `uv run python -m qello_knowledge.config.example`로 다시 만든다(손으로 고치지 않는다). `tests/unit/config/test_example_file.py` 통과
- [X] T057 [P] `docs/sdd/decisions/ADR-008-runtime-and-cost-cap.md`에 "질의 경로 실행 위치는 ADR-022가 일부 고친다(Proposed)" 링크 한 줄을 더한다. ADR-022 상태는 PR 리뷰 뒤 사람이 Accepted로 바꾼다
- [X] T058 경계·회귀 확인: `uv run pytest tests/unit/test_boundaries.py`, 기존 QK-EMB-001·QK-RET-001·QK-GEN-001·QK-SEC-001·QK-STO-001·QK-SYN-001 시험 전부 통과, `uv run qk-migrate` 두 번(대상 `target=local` 확인, 두 번째 `applied=0`),
  `git diff origin/main --stat -- src/qello_knowledge/retrieval src/qello_knowledge/generation src/qello_knowledge/embedding src/qello_knowledge/security src/qello_knowledge/indexer src/qello_knowledge/adapters/workers_ai src/qello_knowledge/adapters/postgres/migrations/000[1-6]*`가
  비어 있음(바꾸지 않기로 한 파일)
- [X] T059 quickstart.md 1절 전체 실행(`python scripts/preflight.py`, `git diff --check`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run qk-dev db up`, `uv run qk-migrate` × 2, `QK_REQUIRE_LOCALDB=1 uv run pytest`)과
  2절 로컬 질의 서비스 확인(가짜 제공자, 외부 호출 0건). 결과를 "실행 기록"에 적고 체크 표시를 갱신한다
- [X] T060 독립 검토(다른 지침을 받은 별도 에이전트, AGENTS.md 2절)로 diff·시험 결과를 확인받고, 지적 반영 이력을 "실행 기록"에 남긴다
- [ ] T061 `TASK.md` Decisions·검증 기록 갱신, `/pr-draft-summary`로 PR 초안(CLAUDE.md 의무 사용)

---

## 사람 단계

모두 코드 병합 전 PR 리뷰(ADR-022 승인, 팀원(인스턴스 관리자) 동의)와 quickstart 3절 전제를 마친 뒤, 사람이 인증하고 명령마다 승인해서 한다. 값과 주소는 기록하지 않는다.

| 단계 | 내용 | 상태 | 비용·허락 |
| --- | --- | --- | --- |
| H00 | 운영 게이트 닫기: Cloudflare Tunnel 요금과 Worker·Tunnel 트래픽의 데이터 처리 정책(보존, 학습 사용)을 ADR-022 Data and cost에 URL과 함께 적는다. 인스턴스 바깥 방향 UDP 7844 읽기 전용 확인. 운영 색인·마이그레이션 역할의 `qk.embedding_usage` 소유 확인. 질의 서비스 전용 Workers AI 토큰 발급 계획(PR #62 계정 교체 결과와 맞춘다) | 2026-10-26 완료(아래 "H00 운영 게이트") | 없음. 유료·학습 사용·장기 보존이면 멈추고 결정 재검토 |
| H01 | M-01: 시험 질의 서비스(연결 확인만)로 터널·VPC Service·Worker 배포, Discord 수신 주소 등록 때 서명 확인(401) 통과, Python Worker에서 VPC 바인딩 `fetch` 동작 확인 | 2026-10-27 완료(아래 "H01 배포 확인"). Worker CPU 초과 위험은 H04 | 0 Neurons |
| H02 | quickstart 3절 1~8 운영 구성(마이그레이션 0007 적용과 `qk_query` 로그인, `query.env`, `qkquery`·`qk-query.service`, `cloudflared`, Worker, 명령 등록) | 2026-10-27 완료(아래 "H02 질의 서비스 구성") | 0 Neurons |
| H03 | SC-010: 인스턴스 공인 주소로 DB 포트와 질의 서비스 포트 접속 실패 확인 | 2026-10-27 완료(아래 "H03 외부 접속 차단 확인") | 0 Neurons |
| H04 | M-02·M-03: 연결 확인·허용 밖 채널 요청 각 10회 이상으로 Worker CPU 시간(Free 10 ms)과 첫 응답 시간 p50·p95 기록. CPU 한도를 자주 넘으면 중계만 TypeScript로 옮기는 안(research R-13)을 올린다. 질의 없는 기준선의 인스턴스 자원(아래 "인스턴스 자원 기록")도 이때 잰다 | 2026-10-27 완료(아래 "H04 일부 측정", "H04 TS 중계 재측정", "H04 실제 질의 서비스 기준 측정"). Discord PING 10회는 미측정 | 0 Neurons |
| H05 | M-04: 질문 세트 10~12개(자료로 답할 수 있는 질문, 자료에 없는 질문, "나만 보기" 1개 이상)로 SC-001·SC-002·SC-012·SC-013 기록, 합성 비밀값 질문으로 SC-005 화면 대조. 화면 기록은 값을 가린다. 실측 동안 인스턴스 자원(아래 "인스턴스 자원 기록")을 함께 잰다 | H04 뒤 | 약 500~610 Neurons. 실행 전 예상량 보고와 사람 확인(AGENTS.md 3.5) |

---

### 실측 기록 꼴 (T055, 2026-10-26 확정, 아직 미실행)

실측 질문·정답 라벨은 개인정보를 지우고 코드와 **다른 커밋**으로 먼저 고정한다. 아래에는 질문 번호만 쓴다. 질문·답변·출처 원문, 주소·Discord 식별자·토큰은 기록하지 않는다.
실행 전에 질문 수 × 예상 Neurons와 당일 잔여량을 보고하고 사람 확인을 받는다. 미측정 값은 0이 아니라 `미측정`으로 남긴다.

| 공통 조건 | 기록할 값 |
| --- | --- |
| 날짜·환경·실행 방식 | `<date-and-timezone>`, `<environment-label>`, Python 중계 Worker → VPC/Tunnel → OCI 질의 서비스, `<release-version>` |
| 질문 세트 | `<set-name>`, `<set-version>`, 질문 수 `<n>`(10~12개), 자료로 답할 수 있음/없음 각 표본 수, 나만 보기 표본 수(≥1) |
| SC-002 판정 기준 | 자료로 답할 수 있는 질문: 모두 출처 목록이 있고 각 링크가 원본 문서를 엶. 자료에 없는 질문: 모두 "제공된 자료만으로 확인할 수 없습니다.". 사람이 화면 대조로 확정 |
| 모델·프롬프트 | 생성 `<model-id>`, `<prompt-version>`, 질의 임베딩 `<embedding-model>` |
| 색인 조건 | `<index-version>`, `<indexed-at>`, `<chunking-version>` |
| 제한·예산 | 질의 마감 `<seconds>`, 안내 전달 마감 `<seconds>`, 외부 호출 상한 `<calls>`(기본 20), Worker CPU 한도 10 ms, 예상/실사용 Neurons, 측정·추정 구분 |

질문마다 다음 두 표를 같은 번호로 연결한다. 첫 표의 처음 두 시간은 **Discord 화면 기준 전체 경로**이고, `first_response`는 **OCI 요청 처리 시간**이다.
OCI 로그의 `first_response`만으로 SC-001의 3초를 판정하지 않는다. Worker 지표의 CPU·subrequest는 별도로 수집하며 OCI 외부 호출 합계와 구분한다.

| 질문 번호 | 유형(있음/없음) | 나만 보기 | 처리 중 응답 ms | 갱신까지 ms | first_response ms | retrieve ms | generate ms | deliver ms | Worker CPU ms |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `<question-number>` | `<kind>` | `<bool>` | 미측정 | 미측정 | 미측정 | 미측정 | 미측정 | 미측정 | 미측정 |

| 질문 번호 | 검색/생성/전달 호출 수·합계 | Worker subrequest 수 | 전달 재시도·실패 종류 | 임베딩 Neurons·측정/추정 | 생성 Neurons·측정/추정 | SC-001·002·012·013 판정 | 값 가린 화면 기록 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `<question-number>` | 미측정 | 미측정 | 미측정 | 미측정 | 미측정 | 미확인 | `<evidence-label>` |

OCI 호출 수는 시작한 제공자 호출·사용량 기록·검색 호출·Discord 전송의 시도 수(실패·재시도 포함)다. 검색·생성 요약은 기존 계약을 그대로 유지하므로 오류 때 보수적으로 센 요약값과 실제 호출 수가 다를 수 있다.
마감 안내 로그는 안내 전달 때까지의 값이며, 아직 진행 중인 제공자 호출의 최종 사용량은 나중에 사용량 장부에 남는다. 실측 합산 때 같은 실행의 최종 장부를 확인하고 중복 합산하지 않는다.
임베딩 요약의 `estimated_neurons`는 호출 전 예상치이고 `neurons`의 측정 여부는 `measured`로 구분한다. 생성도 `neurons`·`measured`를 함께 쓴다.

### 인스턴스 자원 기록 (H04 기준선, H05 실측 동안)

질의 서비스가 회의 봇과 같이 쓰는 인스턴스(A1 Flex 1 OCPU·6 GB, 2026-10-22 가용 메모리 4.6 GiB, ADR-008)에 주는 부담을 잰다. 질의 부담이 작다는 판단(검색·생성 계산은
Workers AI, 인스턴스는 DB 질의 2~3회와 중계, 동시 실행 2)은 아직 추론이므로 이 기록으로 닫는다. 명령은 사람이 서버에서 읽기 전용으로 실행하고, 수치만 적는다. 호스트 이름·주소·프로세스 인자·
컨테이너 환경값은 기록하지 않는다.

| 항목 | 재는 방법(읽기 전용) | 기준선(H04, 질의 없음 10분) | 실측 중(H05) 최대 |
| --- | --- | --- | --- |
| 인스턴스 가용 메모리 | `free -m`의 available | 4,505~4,536 MB(2026-10-26, 질의 없음 10분 20회) | 미측정 |
| 인스턴스 CPU | `uptime`의 1분 load average, `mpstat 5`(설치돼 있으면)의 사용률 | load 0.00~0.20 | 미측정 |
| 질의 서비스 메모리 | `systemctl show qk-query -p MemoryCurrent`를 5초마다 기록한 최대값(`MemoryMax=512M` 대비 %). `memory.peak`가 있으면 그 값 | 33 MB(약 6%, 2026-10-27 질의 없음 10분 120회). 질의 없는 동안 CPU 750 ms/10분 | 미측정 |
| 질의 서비스 CPU 시간 | `systemctl show qk-query -p CPUUsageNSec`의 실측 전후 차이 ÷ 질문 수 | 해당 없음 | 미측정(질문당 ms) |
| 터널(`cloudflared`) 메모리·CPU | 같은 방법으로 `cloudflared` 서비스 | `qk-cloudflared` 14 MB, CPU 882 ms/10분(약 0.15%) | 미측정 |
| DB 컨테이너 | `docker stats --no-stream --format '{{.Name}} {{.CPUPerc}} {{.MemUsage}}'`의 `qk-postgres` 행(상한 1.5 GB 대비 %) | CPU 0~3.1%, 262 MiB(약 17%) | 미측정 |
| 질의 역할 DB 연결 수 | 승인한 관리 연결에서 `SELECT count(*) FROM pg_stat_activity WHERE usename = 'qk_query'` | 미측정(H02 뒤, `qk_query` 로그인 전) | 미측정(실행 자리 수 이하여야 함) |
| 회의 봇 영향 | 같은 `docker stats`의 회의 봇 컨테이너 행(이름은 기록하지 않고 "회의 봇 1·2"로), 실측 동안 재시작 수(`docker ps`의 STATUS) | 회의 봇 1: CPU 0~0.06%, 120 MiB. 회의 봇 2: CPU 0.04~0.62%, 430 MiB. 재시작 0 | 미측정 |
| 메모리 부족 종료 | 실측 시간대의 `journalctl -k --since <start>`에서 'out of memory' 줄 수(`grep -ci`) | 해당 없음 | 미측정(0이어야 함) |
| 동기화와 겹침(선택) | 예약 동기화(00:30 UTC)가 도는 동안 질문 1~2개를 넣어 retrieve ms·갱신까지 ms를 평소 값과 비교. 질문 세트 안의 번호로 하고 Neurons를 따로 늘리지 않는다 | 해당 없음 | 미측정 |

판정: 질의 서비스 메모리가 `MemoryMax`에 닿지 않고, 메모리 부족 종료와 회의 봇 재시작이 0이며, 질의 역할 DB 연결이 실행 자리 수(기본 2) 이하이면 "부담 작음" 판단을 확인한 것으로 본다.
하나라도 어기면 수치와 함께 실행 기록에 남기고 `QK_QUERY_WORKERS`·`QK_QUERY_QUEUE_SIZE`·`MemoryMax` 조정을 팀원(인스턴스 관리자)과 정한다. Ubuntu 22.04의 systemd에는 `MemoryPeak` 속성이 없을 수 있어
`MemoryCurrent` 주기 기록을 기본으로 둔다 `(추론, 서버에서 확인)`.

마지막에 표본 수와 함께 처리 중 응답·갱신 시간 각각 p50·p95, Worker CPU p50·p95, 3초·안내 전달 마감·호출 상한 충족 건수/전체 건수와 SC-002 사람 판정을 기록한다.
초과한 항목은 단계·한도·실측값·대안을 남긴다. Worker CPU 초과가 반복되면 research R-13의 TypeScript 중계 대안을 검토한다.
SC-005는 별도 합성 비밀값 요청으로 질문자/다른 구성원 화면을 대조한다(합성 값도 기록하지 않음). 이는 자동 시험 결과나 승인으로 대신하지 않는다.

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
- 2026-10-26 실행 중단(BLOCKED, T001): `pyproject.toml`에 선택 의존성 `query = ["cryptography>=43"]`와 dev 의존성 및 Worker 번들 제외 주석을 더했다. `uv lock`은 기본 캐시 임시 파일 생성 권한 오류로 실패했다.
  상위 도구 실행 지침에 따라 같은 명령을 권한 확장으로 재시도했으나 PyPI DNS 조회 실패로 종료 코드 2를 반환했다. 캐시 위치 변경·오프라인 잠금·수동 잠금 편집은 하지 않았다. `uv.lock` 갱신과 cryptography 버전 고정은 미완료이므로 T001은 체크하지 않는다.
  사용자 중단 조건에 따라 T002~T018과 이후 단계는 시작하지 않았다. 후속 명령은 캐시 쓰기 권한과 PyPI 연결을 사용할 수 있는 환경에서 이 worktree의 `uv lock`이다.
  Phase 2 Checkpoint·전체 단위 시험·ruff·preflight는 실행하지 않았다. 구현 시험을 쓰기 전 중단했으며, 실행 에이전트의 기록으로 독립 검증·승인을 대신하지 않는다.

- 2026-10-26 T001: 샌드박스에서 uv lock이 캐시 권한·DNS로 막혀 오케스트레이터가 실행했다. 고정 버전 cryptography 50.0.2
- 2026-10-26 재개 후 중단(BLOCKED): T002의 패키지 자리·로컬 DB conftest·합성 문서 도우미를 만들고 T003 경계 위반 시험을 먼저 더했다. `.venv/bin/python -m pytest tests/unit/test_boundaries.py -k bot -q`는
  pytest가 저장소 루트를 수집하며 `.env.example`의 파일 상태를 확인하는 단계에서 `PermissionError`로 실패했다(종료 코드 4, 수집 오류 1건). 시험 본문은 실행되지 않았으므로 TDD의 의도된 실패로 세지 않는다.
  사용자 중단 조건에 따라 경계 검사 구현과 T004~T018은 진행하지 않았다. T002는 파일 생성까지 했으나 수집 검증을 하지 못해 체크를 보류하고, T003도 시험 초안 상태로 둔다. 차단 경로 접근·권한 확장·수집 우회는 하지 않았다.
  후속: 오케스트레이터가 파일 접근 정책과 pytest 수집 충돌을 해결한 환경에서 위 명령을 실행해 경계 검사 부재로 인한 실패를 확인한 뒤 T003 구현부터 재개한다.
  Phase 2 Checkpoint·전체 단위 시험·ruff·preflight는 이번 재개에서도 실행하지 않았다. `git diff --check`는 별도로 실행했으며, 독립 검증·승인은 아직 없다.
- 2026-10-26 사람 결정: pytest는 `.venv/bin/python -m pytest ...` 접두어로 샌드박스 밖 실행을 요청하고, 에이전트는 `.env`·`.env.*`를 읽지 않는다. ruff는 샌드박스 안 `.venv/bin/ruff`로 실행하며, `python scripts/preflight.py`는 오케스트레이터가 실행한다.
- 2026-10-26 실행 도구 제약(BLOCKED): 현재 도구 정책이 `approval_policy=never`이고 `sandbox_permissions` 지정도 금지하므로 위 pytest 실행 요청을 만들 수 없다. 샌드박스 안 재시도나 다른 실행 도구로 우회하지 않았다. T003 실패 확인·구현과 T004~T018은 보류하며 preflight는 오케스트레이터 실행 항목으로 남긴다.
- 2026-10-26 Full Access 전환 안내 뒤 별도 escalation 없이 `.venv/bin/python -m pytest tests/unit/test_boundaries.py -k bot -q`를 실행했다. 실제 결과는 이전과 같은 `.env.example` 파일 상태 확인 `PermissionError`(종료 코드 4, 수집 오류 1건)였다. 시험 본문에 도달하지 못해 T003의 의도된 실패는 아직 확인하지 못했고, 권한 우회 없이 중단했다. T003 구현·T004~T018과 완료 검증은 미실행이다.

- 2026-10-26 실행 재개(이 세션, workspace-write): 첫 명령 `.venv/bin/python -m pytest tests/unit/test_boundaries.py -q`는 수집에 성공했다. 결과 35 passed / 12 failed이며,
  실패 원인은 새 `bot_discord_violations` 검사 함수 부재(NameError)였다. 앞선 PermissionError와 달리 T003의 의도된 RED로 확인했다. 사용자 지시대로 `.env`·`.env.*`를 직접 열거나 검색하지 않았고,
  기존 pytest의 합성 설정 파일·`.env.example` 검사는 그대로 실행했다. 네트워크·외부 API·DB 실행·커밋·push·PR·권한 확장은 하지 않았다.
- 2026-10-26 T002~T006: 기존 패키지 자리와 로컬 DB conftest를 확인했다. conftest는 기존 세션 전용 `db_url`과 합성 인덱스를 재사용하고 사용량 표 네 개를 함께 비운다.
  실제 DB 픽스처는 실행하지 않았다. 경계 위반 12건 RED → 검사 구현 뒤 경계 47 passed. 합성 키·본문·시계·전송 도우미와 불변 도메인 타입은 모듈 부재 수집 오류 RED → 관련 시험과 경계 52 passed.
  시험 도우미는 `tests.unit.discord.bot_builders`의 전체 경로로 가져와 로컬 DB의 같은 이름 도우미와 혼동하지 않게 했다. 도메인의 컬렉션 입력도 복사하고 로그 JSON의 중첩 키 순서를 고정했다(추가 RED → GREEN).
- 2026-10-26 T007~T010: 새 설정과 진입점·교차 규칙 시험 21 failed RED → 21 passed. 중계는 설정 두 개만, 봇 토큰은 register만, 질의 서비스는 별도 서버 ID·Cloudflare 설정을 요구한다.
  T008은 registry·example·data-model 표와 승인된 기존 시험 두 곳의 기대값을 갱신했다. `.env.example`은 `.venv/bin/python -m qello_knowledge.config.example`로 재생성했으며 직접 읽거나 손으로 편집하지 않았다.
  이는 Phase 2의 기존 example 대조 시험을 통과시키기 위한 T008 정합성 작업이다. T056의 이후 단계 전체 완료로 표시하지 않는다. 기존 `test_example_file.py` 자체는 바꿀 필요가 없었다.
  새 교차 규칙은 기존 `_generation_check`처럼 실패 항목만 결과에 추가하고, 빈 허용 채널 경고는 통과 여부와 분리했다. 새 항목의 교차 검사 결과에는 규칙 이름만 남긴다.
- 2026-10-26 T011~T016: 서명·본문 해석은 모듈 부재 수집 오류 RED → 두 시험과 경계 91 passed. 서명 경계 ±300초, 다른 키·본문·시각·누락·잘못된 형식·백엔드 부재,
  본문 64 KiB 경계·잘못된 중첩 구조·질문자만 보기의 보수적 기본값·채널 종류·사용자 정보 미수집을 확인했다. 안내 모듈도 부재 RED → 안내와 경계 68 passed.
  검색 실패 9종·생성 실패 6종·생성 상태 5종과 FR-011 고정 문구를 대응시켰다. T013의 첫 응답 계약은 T014의 `pong`·`notice`·`deferred`와 `FirstResponse.to_dict()`로 시험한다.
- 2026-10-26 T017~T018: 웹후크 모듈 부재 RED → 가짜 전송·경계 시험 통과. 순차 PATCH/POST, 나만 보기, 멘션 차단, 인증 헤더 구분, 명령 등록 PUT,
  메시지마다 최대 두 번 시도, 첫 PATCH의 첫 404만 1초 뒤 재시도, 429의 대기+1초 규칙, 남은 시간 1초 미만 호출 금지, 전체 호출 마감·정리와 오류 원문 비노출을 확인했다.
  5xx·연결 오류의 재시도 대기는 1초로 정했다(계약에 해당 대기 길이는 없으며 첫 404와 동일한 작은 고정값). 잘못된 retry_after는 재시도하지 않는다.
  urllib 전송은 고정 Discord HTTPS 출처와 API 경로, 리다이렉트 거부를 쓴다. 소켓 제한과 별도로 호출 전체의 대기를 제한하며, 늦은 응답은 버리고 실제 호출이 반환되면 닫는다.
  한계: urllib의 진행 중 호출 자체를 강제 종료하지는 못한다. 대기 반환 뒤에도 기저 호출이 끝날 때까지 daemon 스레드가 잠시 남을 수 있다. 운영 전 독립 검토에서 확인할 항목이다.
  예상 밖 전송·close 예외의 원문이 스레드 traceback으로 나가는 회귀도 별도 RED → GREEN으로 막았다. 실제 대기 시험은 이벤트와 짧은 제한을 써 1초 안에 끝나고 외부 연결은 없다.
- 2026-10-26 최종 자동 확인(실행 에이전트 자체 확인, 독립 승인 아님):
  - `.venv/bin/python -m pytest tests/unit/discord tests/unit/config tests/unit/adapters/test_bot_discord_webhook.py tests/unit/test_boundaries.py -q`: **225 passed**, 종료 0.
  - `.venv/bin/python -m pytest tests/unit -q`: **1702 passed / 4 failed**, 종료 1. 로그는 이 worktree의 `.pytest_cache/qk-bot-phase2-unit.log`(git 제외).
    최초 전체 시험 로그를 작업 위치 밖 임시 경로에 썼다가 이 worktree로 옮겼으며, 후속 로그는 worktree 안에만 쓴다.
  - `.venv/bin/ruff check .`: **All checks passed**, 종료 0.
  - `.venv/bin/ruff format --check .`: **503 files already formatted**, 종료 0.
  - `git diff --check`: 출력 없음, 종료 0.
  - `python scripts/preflight.py`: **미실행 — 오케스트레이터 실행**. 로컬 DB 기동·전체 localdb 시험과 독립 검증도 이번 범위에서 실행하지 않았다.
- 2026-10-26 남은 실패·판정 **FAIL**:
  - `tests/unit/embedding/test_settings.py::test_defaults_pass[query]`, `tests/unit/query/test_app.py::test_healthz_ok_when_settings_pass`: 기존 `tests/unit/fakes.py::valid_environ()`에 새 필수 `QK_DISCORD_GUILD_ID`가 없어 실패한다.
    원인을 소스와 실제 결과로 확인했다. 이 도우미·시험은 승인된 기존 시험 수정 예외 세 곳 밖이라 바꾸지 않았다. 필수 설정을 완화하거나 시험 환경을 우회하지 않았다.
    T008의 구현은 들어갔지만 공통 규칙의 기존 시험 통과 조건이 남아 **T008 체크를 보류**한다. 후속은 합성 설정 도우미에 합성 서버 ID를 더하는 최소 수정의 사람 승인과 재검증이다.
  - `tests/unit/query/test_server.py::test_serve_answers_healthz_on_loopback`, `tests/unit/test_conftest_guards.py::test_loopback_connection_is_allowed`: 샌드박스가 루프백 `bind`를 `PermissionError`로 거부한다.
    네트워크 금지·현재 작업 위치 제한에 따라 권한 확장이나 우회 실행을 하지 않았다. 후속은 사람이 허용한 검증 환경에서 같은 시험을 다시 실행하는 것이다.
  - 바꾸지 않기로 한 검색·생성·임베딩·보안·색인·Workers AI와 query 진입점의 작업 diff는 비어 있다. US1(T019~)은 시작하지 않았다. 인덱스·모델·청킹·평가 세트 변경 없음, 외부 호출 0건·0 Neurons.
  - 사람 결정: 기존 합성 설정 도우미 수정 예외 승인, 루프백 시험 실행 환경 제공. preflight와 별도 지침을 받은 독립 검증은 오케스트레이터가 이어서 수행한다.

- 2026-10-26 후속 사람 결정·오케스트레이터 확인(사용자 전달): 샌드박스 밖에서는 루프백 시험 두 개가 통과했다. 당시 전체 단위는 1704 passed / 2 failed(필수 합성 서버 ID 누락 두 개)였고,
  ruff check·format·diff 검사는 통과했다. preflight는 `tests/unit/discord/bot_builders.py`의 TOKEN 직접 할당에서 `assigned-secret`·`env-assigned-secret` 오탐 두 건으로 실패했다.
  사람은 `tests/unit/fakes.py::valid_environ()`에 다른 합성 값과 겹치지 않는 18자리 `QK_DISCORD_GUILD_ID` 한 줄을 더하는 예외를 승인했다. 이 예외를 공통 규칙과 T008에 반영했다.
- 2026-10-26 후속 수정(실행 에이전트): 먼저 기존 설정·healthz 실패 두 개를 재현(2 failed)한 뒤 합성 서버 ID 한 줄을 더해 2 passed를 확인했다.
  TOKEN은 커밋 `d8b9dde`(#53)와 같은 주석·문자열 이어 붙이기로 바꿨으며 실행 중 값은 그대로다. 비밀값 검사 규칙·allowlist·기존 시험의 검증 조건은 바꾸지 않았다.
  같은 꼴의 상수를 포함한 새 Discord·설정·로컬 DB 시험 도우미 Python 파일들에 기존 `secret_rules.RULES`를 직접 적용해 수정 전 오탐 2건 → 수정 후 0건을 확인했다.
  이는 해당 파일들의 규칙 검사이며 저장소 전체 preflight 통과를 뜻하지 않는다. T008을 [X]로 바꿨고, US1(T019~)은 여전히 미착수다.
- 2026-10-26 후속 최종 검증(실행 에이전트 자체 실행):
  - `.venv/bin/python -m pytest tests/unit -q`: **1704 passed / 2 failed**, 종료 1. 실패는 `tests/unit/query/test_server.py::test_serve_answers_healthz_on_loopback`와
    `tests/unit/test_conftest_guards.py::test_loopback_connection_is_allowed`의 샌드박스 루프백 `bind` PermissionError뿐이다. 로그: `.pytest_cache/qk-bot-phase2-followup-unit.log`(git 제외).
    앞선 설정·healthz 실패 두 개는 해소됐다. 위 루프백 두 개의 샌드박스 밖 통과는 오케스트레이터가 전달한 결과이며 이 실행 에이전트가 재실행한 결과와 구분한다.
  - `.venv/bin/ruff check .`: **All checks passed**, 종료 0.
  - `.venv/bin/ruff format --check .`: **503 files already formatted**, 종료 0.
  - `git diff --check`: 출력 없음, 종료 0.
  - `python scripts/preflight.py`: **후속 미실행 — 오케스트레이터 실행**. 전체 preflight 재검증 전에는 통과로 보고하지 않는다. 독립 검증·승인은 이 실행 세션의 자체 확인으로 대신하지 않는다.
  - 후속 상태 **BLOCKED**: 승인한 수정과 T008 완료 기록은 반영했으며, 남은 것은 샌드박스 환경 밖의 전체 검증과 오케스트레이터의 preflight 재실행이다. 추가 구현 결정은 필요 없다.

- 2026-10-26 US1 재개: 시작 시 `git status --short`는 비어 있었고 브랜치는 계약과 같았다. Phase 1·2의 여섯 커밋(b0254b8..6902d09)은 보존했다. 사용자 전달: 오케스트레이터가 샌드박스 밖 전체 1969 passed와 preflight·ruff 통과를 확인하고 사람이 승인했다.
  실행 범위는 T019~T034이며, US2 이후·실제 외부 호출·커밋·push·웹 검색은 하지 않는다. TDD·진행 기록은 이 파일에서 이어 간다.
- 2026-10-26 T025·T029: 먼저 로컬 DB 시험을 작성했고, 샌드박스 및 오케스트레이터의 별도 실행 모두 `StoreDeadline` 부재 수집 오류 RED를 확인했다.
  선택 인자 deadline과 검색 전용 문맥 관리자를 더해 여섯 검색·문맥 메서드만 연결했다. 색인 쓰기 메서드와 기존 `_db`는 변경하지 않았다. 연결 전 남은 시간이 10초 미만이면 연결하지 않고, 질의 중에는 타이머에서 cancel_safe를 부르며 완료 뒤 타이머를 취소·join한다.
  오케스트레이터 첫 GREEN 실행에서 시험 벡터의 768 차원 오기 1건이 드러나 상수 EMBEDDING_DIMENSION(1024)으로 고쳤다. 재실행 `QK_REQUIRE_LOCALDB=1 .venv/bin/python -m pytest tests/localdb/query/test_bot_store_deadline.py tests/localdb/retrieval -q`: **57 passed in 3.38s**(사용자 전달, 샌드박스 밖). 기존 retrieval 회귀 없음.
- 2026-10-26 T023·T024·T026·T027: 렌더링·중계 모듈 부재 수집 오류 RED → 해당 시험과 기존 경계 **55 passed**. 출처는 생성 결과의 citations만 쓰며 한국 시간·제목/링크 길이·버전 표기를 고정했다.
  이 단계의 분할은 단순한 길이·항목 경계 처리다. 서식 무력화·코드/링크 경계 분할·출처 우선 자리 배분은 T042·T046에서 확장한다. 기본 렌더링이 메시지 수를 넘으면 조용히 출처를 버리지 않고 오류로 끝낸다.
- 2026-10-26 T019~T022·T028·T030·T031: 첫 응답·시작 확인·작업 실행 시험은 새 DiscordApp 부재 RED → 기존 app 시험 포함 **19 passed**, 파이프라인은 모듈 부재 RED → **9 passed**.
  허용 범위와 처리 전 질문 비밀값 검사는 T031 지시대로 주입 가능한 통과 자리만 뒀다. US3 T041 전에는 운영 배포를 위한 접근 제어가 완성된 것이 아니다.
  검색·생성의 기존 경계를 바꾸지 않고 질의별 부품 공장·생성 설정·임베딩 전송 시간 제한과 재시도 대기 검사를 조립했다. 기존 생성의 전송 직전 검사는 정책과 함께 그대로 연결한다.
  정책 읽기는 기본 파이프라인 조립에 필요해 서버 시작 조립에 뒀다. 처리 전 접근 제어·질문 검사는 여전히 자리이며 T041에서 연결한다. 늦은 생성 결과 폐기 후에도 장부 기록과 finally 연결 정리를 확인했다.
  추가 압력 시험에서 늦은 실행 두 개 뒤의 만료된 대기 식별자 누적을 재현했고, 실행 전 대기열에서 전달 권한이 이미 넘어간 식별자를 지우게 고쳤다(RED → GREEN).
- 2026-10-26 T032: 서버 시작 검사·원본 본문/헤더 전달 시험 **7 failed** RED → 기존 app 시험 포함 **11 passed**. CLI serve 시작 때 설정과 암호 백엔드를 확인하고 실행기를 만들며 종료 때 닫는다.
  기존 make_server의 healthz 시험 계약은 유지한다. 설정이 없는 CLI serve는 종료 2이고, 기존 시험이 직접 만든 healthz 서버는 이전처럼 503을 돌려준다. 운영 로그에서 임의 요청 경로를 출력하지 않는다.
- 2026-10-26 T033·T034: 런타임 겉껍질과 wrangler.toml은 저장소 안 근거로만 작성했다. 근거: QK-FND-001 research R-01·R-02의 https://developers.cloudflare.com/workers/languages/python/ 및 https://developers.cloudflare.com/workers/languages/python/packages/,
  QK-BOT-001 research R-02·R-13 및 ADR-022의 https://developers.cloudflare.com/workers-vpc/configuration/vpc-services/ 와 https://developers.cloudflare.com/workers/runtime-apis/web-crypto/.
  **미확인(H01에서 확인)**: Python Workers request/response arrayBuffer·Uint8Array/to_py·to_js FFI, crypto.subtle.importKey/verify 인자 변환, env.QUERY_SERVICE.fetch의 RequestInit와 Promise 대기/취소, self.ctx.waitUntil의 코루틴 수락, wrangler [[vpc_services]] service_id 및 pywrangler의 실제 번들링/기동.
  Worker 파일은 시험에서 import하지 않았고 실제 Worker/배포 실행은 하지 않았다. 시작 확인은 처리 중 JSON 응답을 반환하도록 예약한 뒤 waitUntil 작업으로 보내며, 서비스 제한 시간 실패에는 보내지 않는다.

- 2026-10-26 US1 추가 검증·최종 기록:
  - T021·T022·T028: 늦은 실행 두 개 뒤에 만료된 대기 식별자가 누적되는 실패와 연결 close 실패를 별도 RED로 확인한 뒤 수정했다. 작업·파이프라인 추가 시험 **16 passed**.
    수명 자리 여섯 개의 동시 만료·느린 전달·429 대기를 실제 스레드 풀과 가짜 시계로 조합해 전달이 풀을 기다리지 않고 안내 마감 안에서 끝나는 것을 확인했다.
    close 오류는 모든 closer를 호출한 뒤 원문 없는 오류로 바꾸며, 같은 질의의 늦은 실행은 추가 전달 권한을 얻지 못한다.
  - 오케스트레이터 전달: T032 서버 겉껍질 확인 `.venv/bin/python -m pytest tests/unit/query/test_server.py tests/unit/query/test_bot_server_runtime.py -q`: **8 passed**, 샌드박스 밖. 기존 루프백 서버 회귀 없음.
  - 오케스트레이터 전달: T025에 질의 완료·늦은 취소 경합 시험을 추가한 뒤 `QK_REQUIRE_LOCALDB=1 .venv/bin/python -m pytest tests/localdb/query/test_bot_store_deadline.py tests/localdb/retrieval -q`: **58 passed in 3.50s**.
  - 그 뒤 실제 retrieve의 호출 계수 대조 시험 한 개를 더했고, 오케스트레이터 결과는 **1 failed / 58 passed**였다. 원인은 시험 기대식에서 사용량 기록을 누락한 것이었다:
    `specs/QK-RET-001-hybrid-retrieval/spec.md` FR-026은 임베딩 제공자 호출·시도마다 사용량 기록·검색 SQL을 모두 센다. `retrieval/service.py::_embed()`도 `2 * embedded.summary.provider_calls`를 더한다.
    `no_results`의 4회는 검색 SQL 2회 + 임베딩 제공자 1회 + 사용량 장부 기록 1회다. `chunk_context`·`source_revisions`·추가 SET 호출은 없었다.
    기존 `tests/unit/retrieval/test_calls.py::_actual()`과 같은 방식으로 새 시험의 기대식에 메모리 장부의 실제 기록 행 수를 더했다. store.py deadline 및 retrieval/ 구현은 이 정정에서 바꾸지 않았다.
    T025 설명도 FR-026의 계수 합으로 명확히 했다. **이 마지막 기대식 정정 뒤 로컬 DB 시험은 아직 재실행하지 못했으므로 T025 체크를 보류**한다.
  - 사용자 지시: 샌드박스 밖 검증은 더 중간 요청하지 않고 체크포인트 끝에 명령 목록으로 모아 보고한다(새 시험 RED 확인이 꼭 필요한 경우만 예외).
- 2026-10-26 US1 Checkpoint(실행 에이전트 자체 실행, 독립 승인 아님):
  - `.venv/bin/python -m pytest tests/unit -q`: **1746 passed / 2 failed**, 종료 1. 로그 `.pytest_cache/qk-bot-us1-unit.log`(git 제외).
    실패는 기존 `tests/unit/query/test_server.py::test_serve_answers_healthz_on_loopback`, `tests/unit/test_conftest_guards.py::test_loopback_connection_is_allowed`의 샌드박스 bind PermissionError뿐이다. 통과로 표현하지 않는다.
  - `.venv/bin/ruff check .`: **All checks passed**, 종료 0.
  - `.venv/bin/ruff format --check .`: **516 files already formatted**, 종료 0.
  - `git diff --check`: 출력 없음, 종료 0.
  - Worker 파일은 import하지 않고 ast.parse만, wrangler.toml은 tomllib로 문법·placeholder만 확인했다. 런타임 실행 확인이 아니다.
  - 변경된 Python·문서·TOML 파일에 기존 secret_rules.RULES만 적용한 검사: **검출 0건**. 전체 `python scripts/preflight.py`는 미실행 — 오케스트레이터 실행.
  - 검색·생성·임베딩·보안·색인·Workers AI·마이그레이션 0001~0006의 작업 diff는 비어 있으며, 기존 시험 파일은 바꾸지 않았다. US2(T035~)는 미착수다.
  - 인덱스 버전은 변경 없음(계약 iv-4c0bc4fcc642), 임베딩 모델 선택·청킹·평가 세트 변경 없음, 품질/운영 실측 없음(n=0), 실제 외부 호출 0건·사용 Neurons 0.
    조립은 기존 RetrievalDeps의 DEFAULT_QUERY_MODEL(@cf/baai/bge-m3)을 그대로 쓴다. TASK의 embeddinggemma 문구와 차이가 있으나 이 범위에서 기존 모델·색인을 바꾸거나 실제 활성 모델을 추정하지 않았다.
- 2026-10-26 최종 상태 **BLOCKED**: T019~T034의 구현은 작성했고, T025의 마지막 로컬 DB 기대식 정정 재검증과 샌드박스 밖 US1 전체 단위 검증·preflight가 남았다.
  접근 제어·처리 전 질문 검사 자리와 기본 분할의 한계는 위 기록처럼 US3·US4의 범위다. Worker API 꼴은 H01에서 확인한다. 이 실행 결과는 독립 승인이나 운영 배포 가능 판정이 아니다.
  오케스트레이터 실행 목록(현재 worktree에서):
  1. `.venv/bin/python -m pytest tests/unit -q` — 샌드박스 밖에서 기존 루프백 두 개를 포함한 전체 단위 확인.
  2. `QK_REQUIRE_LOCALDB=1 .venv/bin/python -m pytest tests/localdb/query/test_bot_store_deadline.py tests/localdb/retrieval -q` — 정정한 T025 계수와 기존 검색 회귀 확인.
  3. `python scripts/preflight.py` — 저장소 전체 검사. 이 실행 에이전트는 .env·.env.*를 직접 읽지 않았다.
- 2026-10-26 T025 GREEN(오케스트레이터, 샌드박스 밖): `QK_REQUIRE_LOCALDB=1` 전체 2,024 passed(외부 2 제외), preflight·ruff·format·`git diff --check` 통과. 호출 수 시험은 FR-026의 사용량 기록 1회 계수를 기대식에 넣었다(구현 변경 없음).

- 2026-10-26 US2~US4 시작: 작업 트리는 깨끗했고 승인된 US1 커밋 cdeacce..02d9759를 보존했다. 사용자 전달: 오케스트레이터가 샌드박스 밖 `QK_REQUIRE_LOCALDB=1` 전체 2024 passed, preflight·ruff 통과를 확인했고 사람이 승인했다.
  이번 실행 범위는 T035~T047이다. US5(T048~)·네트워크/외부 API·커밋·push·PR·웹 검색은 하지 않았으며 .env·.env.*를 직접 열거나 검색하지 않았다.
- 2026-10-26 T035·T036: 먼저 상태별 시험을 작성해 33 failed / 2 passed RED를 확인한 뒤 안내·표시를 연결했다. 관련 상태·파이프라인·기본 렌더링 시험 48 passed.
  확인 불가 본문 유지, 출처 확인 안 됨 경고·출력 잘림 안내, 검색 실패 9종·생성 실패 6종·전송 차단·질의 마감·예상 밖 실패를 고정 문구와 짧은 실행 식별자로 보인다.
  검색 질문 길이 안내는 RetrievalSettings.question_max_chars를 따르고, 실패 안내의 공개 범위는 첫 처리 중 응답과 같다. 검색·생성 경계는 바꾸지 않았다.
- 2026-10-26 T037~T043: 접근 제어 모듈·무력화 함수·로그 출력 함수 부재로 단위 시험 RED(수집 오류)를 확인했다. 구현 뒤 접근 제어·거부·원문 비기록·무력화 관련 90 passed.
  AccessPolicy는 서버·글 채널·선택 역할을 판정하고, 서버나 채널 목록이 없으면 닫는다. 운영 create_app은 기존 security_outgoing_check(policy)에 질문만·출처 없이 넘기는 검사를 처리 중 응답 앞에 명시적으로 연결한다.
  기존 시험의 주입 인터페이스는 유지했다. 운영 서버 조립 시험에서 정책 한 번 읽기와 실제 허용 범위·합성 비밀값 거부를 확인했으며 정책 읽기 실패는 원문 없이 종료 2다.
  T038 합성 비밀값은 tests/unit/synthetic_secrets.py만 사용했다. 실제 키·채널·역할·질문은 쓰지 않았다.
  자료 유래 제목·원본 버전·날짜의 서식 글자는 이스케이프하고 답변 본문의 굵게·목록·코드 서식은 유지한다. 링크의 닫는 괄호·공백·제어 문자는 URL 안에서 인코딩하며 인코딩 뒤 상한을 넘으면 링크를 생략한다.
  QueryJobs의 완료 콜백과 QueryReply의 수치 요약으로 QueryRunLog를 조립하고 server.write_run_log가 표준 오류에 한 줄 JSON을 쓴다. 즉시 거부도 고정 상태 이름만 기록하고 서명 거부·연결 확인·시작 확인에는 질의 로그를 만들지 않는다.
  HTTP 자동 접근 로그는 끄고, 질문·답변·청크·출처·상호작용/사용자/채널 식별자·서명·자격 정보·예외 원문을 운영 로그에 넣지 않는다. 생성 요약은 숫자·측정 여부만 허용한다.
  기록 항목 확장과 단계별 전체 시간·호출 수 채우기는 US6 T053~T054에 남긴다. 이번 구현은 T043의 원문 없는 로그 경계다.
  전달 실패 상태가 answered로 남는 회귀를 RED로 확인하고 undelivered로 고쳤다. 처리 전 접근 제어·비밀값 검사 함수 자체가 예외를 내는 두 경로도 RED → 고정 비공개 안내·무원문 로그로 고쳤다.
  시작 확인 미도착·실제 마감·전달 실패·중복·자리 없음·예외·사용자 정보가 포함된 요청까지 원문 비기록 시험으로 확인했다.
- 2026-10-26 T044~T047: 분할 시험 13 failed / 1 passed RED와 수용량 상수 부재 수집 오류를 확인한 뒤 구현했다. 분할·설정 수용량·기본 렌더링·상태 안내를 묶은 시험 80 passed.
  보호 구간(중첩 괄호가 있는 Markdown 링크·각괄호 링크·일반 URL·Source ID·이스케이프 글자·코드 펜스)을 넘겨 자르지 않는다. 문단 → 문장 → 공백 → 글자 한도 순서로 자르며 한도보다 긴 링크는 고정 안내로 바꾼다.
  코드 조각은 각각 닫고 같은 언어로 다시 연다. 본문을 줄일 때는 코드 밖에 생략 안내를 붙인다. 코드 펜스만 든 빈 조각을 만들던 실패를 확인해 분할 후보에서 제외했다.
  출처 목록에 메시지 자리를 먼저 배정하고 항목 사이에서만 나누며, 남은 본문 자리가 모자라면 본문만 줄인다. 짧은 본문·출처가 한 메시지에 들어가면 합친다. 분할된 후속 메시지도 선택한 공개 범위와 allowed_mentions를 유지한다.
  T045 계산값: 실제 최악 항목(최대 길이 제목의 전 글자 이스케이프 + 말줄임표, 비해시 버전 12자의 전 글자 이스케이프, 링크 300자, 최대 Source ID S20, 날짜, 줄바꿈 포함)은 **545자**.
  목록 머리글+줄바꿈은 **14자**, 메시지당 항목은 floor((2000-14)/545)=**3**, 기본 expand_top 8개에 필요한 메시지는 ceil(8/3)=**3**, 기본 메시지 상한 4에서 본문 **1자리**가 남는다.
  이 수치는 실제 citation_line 출력 길이와 상수가 같은지 시험으로 고정했다. 제목/링크/메시지 수 27개 조합을 검사하고 출처가 본문 자리를 침범하는 설정을 discord_source_capacity 규칙으로 거부한다.
  check.py 변경은 T042·T046 뒤에 했고 config → discord 방향만 가져온다. 기본 통과 설정은 기존 보고 꼴을 유지한다.
- 2026-10-26 변경 파일 비밀값 규칙 검사에서 링크 시험의 변수 이름 때문에 assigned-secret 오탐 1건을 확인했다. bot_builders와 같은 주석·문자열 이어 붙이기로 런타임 값은 유지하며 고쳤다. 비밀값 규칙·allowlist는 바꾸지 않았다.
  샌드박스 밖 검증은 중간 요청하지 않았으며 마지막 명령 목록으로만 넘긴다. 새로 추가한 로컬 DB 시험은 없다. US5는 미착수다.
- 2026-10-26 T045 계산값(오케스트레이터가 시험·상수에서 확인): 기본 설정(제목 80, 링크 300, `expand_top` 8, 2,000자)에서 출처 항목 최대 길이 545자, 메시지당 3항목, 출처에 필요한 메시지 3개 ≤ 메시지 상한 4 − 1(`source_capacity(80, 300, expand_top=8) == (3, 3)`). spec FR-012 추론값(551자, 3항목, 3개)과 같은 결론이다.
- 2026-10-26 US2~US4 검증(오케스트레이터, 샌드박스 밖): `QK_REQUIRE_LOCALDB=1` 전체 2,197 passed(외부 2 제외), preflight·ruff·format·`git diff --check` 통과. Codex 세션은 마지막 검증 중 모델 용량 초과로 멈췄다.

- 2026-10-26 US5~US6 재개: git log에서 `117ecbe`·`877a151`, 시작 시 깨끗한 작업 트리와 작업 브랜치를 확인했다. 이번 범위는 T048~T055뿐이며 Polish는 시작하지 않았다.
- 2026-10-26 T048 RED(오케스트레이터, 샌드박스 밖): `QK_REQUIRE_LOCALDB=1 .venv/bin/python -m pytest tests/localdb/query/test_bot_query_role.py -q` 결과 40 failed.
  38건은 `0007 role missing`, 나머지는 RLS 미설정과 0007 파일 부재다. 이 결과를 받은 뒤에만 0007을 작성했다. 이후 DB 시험 실행을 중간에 다시 요청하지 않았다.
  T048은 GREEN 미확인으로 체크하지 않는다. 시험은 기존 세션별 임시 DB에서 SET LOCAL ROLE을 쓰며 운영 DB·로그인·공유 테이블에는 적용하지 않았다.
- 2026-10-26 T050: 0007에 NOLOGIN 역할, 검색·문맥 읽기, 질의 임베딩·생성 사용량 INSERT/SELECT, 두 사용량 시퀀스 USAGE, embedding_usage SELECT/INSERT RLS를 썼다.
  0002~0006 함수 본문과 권한 목록을 대조한 결과를 data-model 4절에 적었다. 빠진 표·시퀀스 권한이나 승인 밖 추가 권한은 없고, 보조 함수 세 개(embedding_utc_day·embedding_amount·embedding_used)를 명시했다.
  오늘 합계 함수는 daily 표를 읽지 않지만 승인된 집계 읽기 계약의 SELECT는 유지했다. PUBLIC EXECUTE를 유지하므로 reserve는 RLS, settle·prune은 표 변경 권한에서 막는 구성이다.
  FORCE·UPDATE/DELETE 정책은 없으며 0001~0006을 바꾸지 않았다. 로컬 DB GREEN·기존 localdb 회귀와 운영 소유권 확인은 별도 오케스트레이터/사람 단계다.
- 2026-10-26 T049: 저장소 시간 초과를 전체 질의 시간 초과로 바꾸던 경로의 RED를 확인한 뒤 질의 조립 경계에서 StoreUnavailable로 바꿨다.
  추가 경계 시험으로 50초에 저장소 실패가 돌아와도 생성 최소 7초 검사에 가려지는 RED 2건을 확인했다. 검색 실패·빈 Context의 생성 API 없는 안내는 그 하한 검사를 거치지 않게 했다.
  마감 전 연결 실패·시간 초과는 검색 불가 안내, 55초 마감 도달은 기존 시간 초과 안내다. 저장소 검색 재시도는 없고 늦은 결과도 다시 실행하지 않는다. retrieval/과 store.py는 바꾸지 않았다.
- 2026-10-26 T051: OCI 운영 문서에 H00 게이트, 소유권 확인, 별도 읽기 전용 질의 릴리스, qkquery, query.env 숨김 입력·원자 교체, systemd, 원격 관리 터널·VPC·Worker·Discord, 폐쇄 포트 확인과 되돌리기를 더했다.
  주소·토큰·비공개 식별자는 placeholder뿐이다. 별도 릴리스는 기존 동기화의 uv sync가 query 의존성을 제거하거나 실행 중 코드를 교체하지 않게 하기 위함이다.
  qk-sync-notify@.service 원문은 현재 저장소에 없으므로 관리자 대조를 운영 적용 전 게이트로 적었다. 제시한 MemoryMax는 실측값이 아니며 관리자 확인이 필요하다. 운영 명령은 실행하지 않았다.
- 2026-10-26 T052~T054: register-commands 부재 RED 15건을 확인한 뒤 REGISTER 설정·토큰 없는 dry-run·동일한 PUT 본문·종료 코드 0/2/3을 구현했다. 시험은 가짜 전송만 쓴다.
  T053은 QueryCalls 부재 수집 오류 RED를 확인하고 호출·시간 기록을 구현했다. 조립 경계에서 제공자·장부·검색 시도를 세고 기존 검색·생성 요약은 바꾸지 않는다.
  작업 상태 잠금 아래 단계 시간을 마무리하고, 즉시 안내에는 실행하지 않은 단계 0을 넣는다. 허용된 수치만 로그로 보내며 임베딩/생성 Neurons 측정·추정 구분을 남긴다.
  마감 안내가 먼저 나가면 그 시점 호출 수로 로그 한 줄을 확정하며 늦은 사용량은 장부에 남는다. 성공·실패 호출, 지연 사용량 경합, 양쪽 모델 측정·추정, 최대 재시도와 4메시지(검색 7 + 생성 4 + 전달 8 = 19 ≤ 20)를 가짜 시계로 확인했다.
- 2026-10-26 T055: 사람 단계에 FR-025 공통 조건·질문 번호별 시간/호출/Neurons·SC-002 화면 판정·p50/p95 기록 꼴을 확정했다. OCI first_response와 Discord 전체 경로 첫 응답을 구분한다.
  질문 세트·정답 라벨은 코드와 다른 커밋에 먼저 고정하고, 이번에는 실제 질문·측정값·평가 자료를 만들거나 외부 API를 호출하지 않았다(0 Neurons).

- 2026-10-26 US6 체크포인트(실행 에이전트 자체 검사): `.venv/bin/python -m pytest tests/unit -q --tb=short` 결과 **1,946 passed, 2 failed**(3.18초).
  실패는 기존 `tests/unit/query/test_server.py::test_serve_answers_healthz_on_loopback`, `tests/unit/test_conftest_guards.py::test_loopback_connection_is_allowed`뿐이며 둘 다 socket.bind의 PermissionError(샌드박스)다.
  `.venv/bin/ruff check .` 통과, `.venv/bin/ruff format --check .` 통과(530 files), `git diff --check` 통과. T048 시험 40건 수집만 통과했고 DB GREEN은 실행하지 않았다.
  변경 파일 12개에 domain.secret_rules.RULES를 직접 적용한 보조 검사 검출 0건(전체 preflight 대체 아님). 기존 추적 시험 diff와 변경 금지 경로(retrieval/generation/embedding/security/indexer/workers_ai/store.py/0001~0006)의 HEAD 대비 diff는 비어 있다.
  오케스트레이터 실행 필요: `QK_REQUIRE_LOCALDB=1 .venv/bin/python -m pytest`(T048 GREEN·전체 localdb 회귀·루프백 2건 포함), `.venv/bin/python scripts/preflight.py`(오케스트레이터 실행).
  마지막 두 문서 기록 변경 뒤 정적 검사는 다시 확인한다. 현재 필수 DB·루프백·전체 preflight 확인 전이므로 최종 상태 BLOCKED다. 독립 검증·사람 승인으로 간주하지 않는다. 커밋·push·운영 변경·외부 API 호출은 하지 않았다.

- 2026-10-26 US5~US6 오케스트레이터 검증(샌드박스 밖, `QK_REQUIRE_LOCALDB=1` 전체): **2,225 passed, 39 failed, 2 deselected**.
  실패 39건은 T048의 `SET LOCAL ROLE qk_query` 준비 단계에서 발생한 권한 오류다. 로컬 supabase/postgres 17.11의 postgres는 **슈퍼유저가 아니다**(`rolsuper=false`).
  PG16+ 역할 생성자는 ADMIN을 가져도 기본 createrole_self_grant가 비어 있으면 SET 멤버십이 자동 부여되지 않는다. preflight·ruff·format·diff와 루프백 시험은 오케스트레이터 확인으로 통과했고 금지 경로 변경도 없었다.
  T048의 소유자 시험 `test_bot_owner_index_writes_still_work_and_rls_is_not_forced`는 통과했다(해당 파일 1 passed). 마이그레이션 역할이 표 소유자이면 비슈퍼유저여도 RLS를 건너뛰므로 data-model 4절 전제는 유지된다.
  운영 DB의 마이그레이션 역할 속성과 실제 표 소유권도 H00에서 확인한다. 로컬 결과로 운영 속성을 추정하지 않는다.
- 2026-10-26 T048 시험 준비 수정: 0007은 그대로 두고 bot_as_query의 트랜잭션에서만 `GRANT qk_query TO CURRENT_USER WITH SET TRUE, INHERIT FALSE` 후 SET LOCAL ROLE을 수행한다.
  psycopg transaction(force_rollback=True)로 성공·실패 모두 멤버십 변경을 되돌려 기존 ADMIN/SET/INHERIT 상태를 보존한다. 역할 멤버십은 클러스터 전역이므로 세션 DB 삭제에 정리를 맡기지 않는다.
  오케스트레이터의 39건 실패가 이 수정의 RED 증거다. T048 GREEN은 아직 미확인으로 미체크를 유지하며 역할 시험 파일만 재확인 요청한다.
  수정 후 역할 시험 40건 수집·해당 파일 ruff check/format·git diff --check는 통과했다. 설치된 psycopg의 force_rollback 인자 지원도 확인했다. DB 실행 결과는 오케스트레이터에게 해당 파일만 재확인 요청했으며 아직 미수신이다.

- 2026-10-26 T048 최종 GREEN(오케스트레이터, 샌드박스 밖, `QK_REQUIRE_LOCALDB=1`): `tests/localdb/query/test_bot_query_role.py` **40 passed**.
  이어서 전체 재실행 **2,264 passed, 2 deselected in 42.32s**를 확인했다. 임시 SET 멤버십 준비 뒤 역할 성공·거부·소유자 색인·마이그레이션 재실행이 모두 통과했으며 T048을 [X]로 바꿨다.
  앞의 39건 권한 실패와 DB GREEN 대기 상태는 이 결과로 해소됐다. 0007에 마이그레이션 역할 멤버십을 추가하지 않았다. 이번 재실행 결과는 오케스트레이터가 전달한 증거이며 실행 에이전트의 자체 승인이나 운영 검증을 뜻하지 않는다.
  preflight는 앞선 오케스트레이터 실행에서 통과했고, 이후 변경은 시험의 임시 멤버십 준비와 문서 기록이다. 해당 변경의 수집·ruff·format·diff 검사는 통과했다. 최종 기록 갱신 뒤 전체 ruff check·format(530 files)·git diff --check와 이번 수정 3개 파일의 비밀값 규칙 보조 검사(검출 0건)도 통과했다.
  US5~US6 T048~T055를 완료했다. Polish T056~T061과 사람 단계 H00~H05는 시작하지 않았으며 운영 적용·네트워크 호출·커밋·push는 하지 않았다.

- 2026-10-26 Phase 9 T056~T059 시작: git log의 `9361991`~`783cce3` 네 커밋, 작업 브랜치, 시작 시 깨끗한 작업 트리를 확인했다.
  이번 범위는 T056~T059뿐이며 T060 독립 검토·T061 TASK.md/PR 초안은 하지 않는다. 기록은 기존 tasks.md에만 남긴다.
- 2026-10-26 T056 완료: `.venv/bin/python -m qello_knowledge.config.example`을 실행했다. `.env.example` 내용은 열거나 출력하지 않았다.
  `git status --short -- .env.example`에 변경이 없었고 `.venv/bin/python -m pytest tests/unit/config/test_example_file.py -q` **1 passed**로 생성 결과를 확인했다. 손으로 고치지 않았다.
- 2026-10-26 T057 완료: ADR-008에 "질의 경로 실행 위치는 ADR-022가 일부 고친다(Proposed)" 링크 한 줄만 추가했다. ADR-022는 Proposed를 유지하고 변경하지 않았다.
- 2026-10-26 T058 부분 확인: `.venv/bin/python -m pytest tests/unit/test_boundaries.py -q` **47 passed**.
  tasks.md의 변경 금지 경로 목록 그대로 `git diff origin/main --stat -- src/qello_knowledge/retrieval src/qello_knowledge/generation src/qello_knowledge/embedding src/qello_knowledge/security src/qello_knowledge/indexer src/qello_knowledge/adapters/workers_ai 'src/qello_knowledge/adapters/postgres/migrations/000[1-6]*'`를 실행해 출력이 비어 있음을 확인했다.
  네트워크 갱신 없이 로컬 origin/main을 사용했다. qk-migrate 두 번(target=local, 두 번째 applied=0)과 기존 localdb 회귀는 오케스트레이터 실행이 남아 T058은 [ ]로 유지한다.
- 2026-10-26 T059 부분 확인: `.venv/bin/python -m pytest tests/unit -q --tb=short` 결과 **1,946 passed, 2 failed in 3.13s**.
  실패는 기존 `tests/unit/query/test_server.py::test_serve_answers_healthz_on_loopback`, `tests/unit/test_conftest_guards.py::test_loopback_connection_is_allowed`뿐이며 둘 다 socket.bind PermissionError(샌드박스)다. 기존 시험을 수정하거나 skip하지 않았다.
  `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`(530 files), `git diff --check`는 통과했다. preflight·DB 구동·마이그레이션·로컬 DB 시험과 quickstart 2절 로컬 서비스 확인은 여기서 실행하지 않았다.
  quickstart 2절의 기본 serve는 실제 제공자·Discord 웹훅을 조립하므로 오케스트레이터가 가짜 파이프라인·전송을 주입한 시험 하네스에서 확인해야 한다. env 파일만으로 가짜 모드가 선택된다고 가정하지 않는다.
  연결 확인 PONG, 허용 요청 처리 중 응답·시작 확인·가짜 수신부 갱신, 시작 확인 누락 NOT_STARTED, 등록 dry-run까지 외부 API 0건으로 확인할 몫이 남아 T059는 [ ]로 유지한다.
  오케스트레이터 명령(모두 로컬 합성 시험 설정만): 필요하면 `.venv/bin/qk-dev db up`; `.venv/bin/qk-migrate --env-file <local-test-config>` 두 번; `QK_REQUIRE_LOCALDB=1 .venv/bin/python -m pytest`; `.venv/bin/python scripts/preflight.py`.
  quickstart 2절 명령은 가짜 주입 하네스에서 `.venv/bin/qk-query serve --port 8787 --env-file <local-test-config>`, 별도 셸에서 `.venv/bin/qk-query register-commands --env-file <local-register-test-config> --dry-run`이다. 실제 명령 등록·운영 구성은 하지 않는다.
  이번 세션의 최종 상태는 남은 필수 검증 때문에 BLOCKED다. T056·T057만 [X]로 갱신하며 네트워크·외부 API·커밋·push·PR은 실행하지 않았다. 이 기록은 독립 검토·사람 승인을 대신하지 않는다.
- 2026-10-26 T058·T059 오케스트레이터 몫(샌드박스 밖): `DATABASE_URL`을 비운 빈 env 파일로 `qk-migrate --dry-run`이 `target=local`임을 확인한 뒤 두 번 실행했다. 첫 번째 `applied=3 skipped=4`(로컬 개발 DB가 0004에 멈춰 있어 0005~0007 적용), 두 번째 `applied=0 skipped=7`. `QK_REQUIRE_LOCALDB=1` 전체 2,264 passed(외부 2 제외), preflight·ruff·format·`git diff --check` 통과. `qk-query register-commands --dry-run`(합성 애플리케이션·서버 ID, 봇 토큰 없음)이 외부 호출 없이 contracts/discord-outbound.md 2절과 같은 JSON을 내고 종료 코드 0.
- 2026-10-26 발견(T059): quickstart 2절의 `qk-query serve` 로컬 확인은 지금 실행할 수 없다. `serve`는 실제 검색·생성·Discord 전송을 조립하고 가짜 제공자 선택이 없어, 시작 확인을 보내지 않아도 5초 뒤 실제 Discord로 `PATCH`가 나간다(외부 호출). 그래서 실행하지 않았다. **당시 `test_bot_server_runtime.py`가 루프백 서버를 확인한다고 적은 기록은 틀렸다.** 이 시험은 서버를 모킹하고 핸들러를 BytesIO·가짜 handle로 검사한다.
- 2026-10-26 사용자 결정(T059 발견): quickstart 2절을 시험 기반 확인과 `register-commands --dry-run`으로 고쳤다. `serve`에 가짜 제공자 모드는 더하지 않는다. 당시 `test_bot_server_runtime.py` 등의 통과는 단위 경계 검증이며 실제 루프백 HTTP 증빙은 아니었다.
- 2026-10-26 T060 독립 검토 변경 요청 M1~M3 반영(이 실행 세션은 스스로 승인하지 않음): M1 재현 시험은 연속 12회 시간 초과 뒤 이전 구현에서 전송 스레드 12개가 남아 **RED**였다. 소켓이 연결된 기본 urllib 경로는 마감에 `shutdown`·`close`하고, 끊을 수 없는 DNS·TLS·주입 opener 작업은 실제 종료까지 전역 전송 자리 8개를 쥐게 했다. 가짜 소켓의 헤더·본문 대기 종료와 12회 호출 상한을 시험으로 고정했다. urllib의 작업별 `timeout`만으로 전체 경과 시간을 보장하지 못하고, 소켓 등록 전 작업은 강제 종료할 수 없다는 한계를 research R-05에 적었다.
- 2026-10-26 M2: 코드 블록 안 1,995자 링크 등의 재현 시험은 이전 분할의 `ValueError`로 **19 failed, 12 passed(RED)**였다. 펜스 여유를 빼고 긴 링크를 대체하며, 긴 펜스 언어를 80자로 제한하고 보호 구간이 끝까지 담기지 않으면 남은 본문을 생략한다. 경계 조합과 결정적 100개 입력, 실제 파이프라인 답변 전달을 추가해 관련 시험 **86 passed**(M1·기존 웹훅·기존 분할 포함)로 확인했다.
- 2026-10-26 M3/T059 정정: 실제 `make_server` → `ThreadingHTTPServer` → `HTTPConnection` 하네스에 가짜 검색·생성·Discord를 넣은 새 통합 시험을 추가했다. 서명한 PING, 허용 `/ask`와 시작 확인·갱신, 시작 누락 `NOT_STARTED`, 잘못된 서명 `401`의 5건은 오케스트레이터가 샌드박스 밖에서 **5 passed**로 확인했다. quickstart 2절 시험 목록을 새 시험으로 바꿨다. 위 T059의 `test_bot_server_runtime.py` 루프백 증빙 주장은 틀렸음을 명시했다.
- 2026-10-26 이 세션 검증: `.venv/bin/python -m pytest tests/unit -q --tb=short`는 **1,981 passed, 2 failed, 5 errors**. 실패·오류 7건은 기존 루프백 2건과 새 통합 5건 모두 샌드박스의 `socket.bind` PermissionError이며, 새 통합 5건은 위 오케스트레이터 GREEN 확인이 있다. `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`(534 files), `git diff --check`, 금지 경로 `git diff origin/main --stat -- ...`(출력 없음)는 통과했다. 남은 샌드박스 밖 검증: 수정 전체 `.venv/bin/python -m pytest tests/unit -q`, `QK_REQUIRE_LOCALDB=1 .venv/bin/python -m pytest`, `.venv/bin/python scripts/preflight.py`. 네트워크·외부 API·커밋·push·PR은 실행하지 않았다.
- 2026-10-26 T060 재검토 후속 M1: 위 M1의 **전역 HTTP 상한 8은 폐기**했다. 설정이 허용하는 `C=24`에서 전송부에 24를 넘기지 못하는 시험 2건과 웹훅 용량 전달 시험 1건이 **RED**(TypeError, IndexError, TypeError)였다. 이제 `create_app`이 검사를 통과한 `workers + queue_size`를 `DiscordWebhook`에 넘기고, 웹훅의 `UrllibTransport`는 그 값의 전송 자리를 갖는다(기본 `C=6`, 설정 최대 24). 가짜 opener로 앞의 23개가 아직 끝나지 않았을 때 시간이 남은 24번째 전송이 성공하고, 25번째 끊을 수 없는 전송은 시작하지 않음을 확인했다. 연결 전 DNS·TLS 단계의 스레드를 강제 종료할 수 없다는 한계는 그대로이며, 남는 작업 상한은 단일 운영 전송 인스턴스의 `C`다(research R-05 정정).
- 2026-10-26 T060 재검토 후속 M2: 한 줄 코드 펜스 120자와 닫는 펜스 뒤 120자가 각각 80자로 잘리고 `body_truncated=False`였던 **2 failed, 2 passed(RED)**를 확인했다. 줄바꿈까지 있는 여는 펜스의 언어 표시만 80자로 제한한다. 한 줄 코드·닫는 펜스 뒤 본문·긴 언어 표시 뒤 코드·언어 없는 펜스의 본문은 생략 없이 보존하고, 2,100자 한 줄 코드처럼 담을 수 없는 경우에는 `body_truncated=True`와 생략 줄을 확인했다.
- 2026-10-26 후속 검증: 새 M1 관련 시험 **7 passed**, M2 분할 관련 시험 **53 passed**. 처음 1ms 제한으로 만든 M1 시험은 스레드가 opener에 들어가기 전에 취소되는 순서 경합이 있어, 23개 동시 호출의 시작을 확인하고 24번째를 보내도록 시험을 고쳤다. 최종 `.venv/bin/python -m pytest tests/unit -q --tb=short`는 **1,990 passed, 2 failed, 5 errors**이며 실패·오류 7건은 위와 같은 샌드박스 `socket.bind` 권한 오류뿐이다. `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`(535 files), `git diff --check`, 금지 경로 diff(출력 없음) 통과. 샌드박스 밖 수정 전체 단위·로컬 DB 회귀·preflight 확인은 오케스트레이터 몫으로 남는다. 이 실행 세션은 재검토 결과를 승인하지 않으며 네트워크·외부 API·커밋·push·PR을 실행하지 않았다.
- 2026-10-26 T060 독립 검토: 구현 세션과 따로 띄운 읽기 전용 Codex 세션(`sandbox_mode=read-only`, 검증 에이전트)이 `origin/main...HEAD`를 검토했다.
  1차 변경 요청 M3(전송 스레드 누적, 코드 블록 안 긴 링크의 분할 예외, 루프백 통합 근거 불일치) → 재검토 변경 요청 M2(고정 전송 상한 8과 수명 자리 설정 충돌, 펜스 언어 줄이기의 본문 유실) → 2차 재검토 승인(H·M·L 0, 수정분 범위).
  검토가 받아들인 한계: 연결 전 DNS·TLS 작업은 강제 종료할 수 없어 남는 전송 스레드가 그 인스턴스의 수명 자리 수(C, 기본 6)까지 실제 반환 때까지 남을 수 있고, 모두 남으면 회복 전 추가 전송은 실패한다(research R-05). FR-008은 모든 기저 스레드의 종료 보장이 아니다.
  수정 뒤 오케스트레이터 검증(샌드박스 밖): `QK_REQUIRE_LOCALDB=1` 전체 2,313 passed(외부 2 제외), preflight·ruff·format·`git diff --check` 통과. 같은 세션(오케스트레이터)이 앞서 quickstart 2절 근거를 시험 내용 확인 없이 쓴 오류는 M3으로 잡혀 고쳤다.
- 2026-10-26 사용자 요청: 사람 단계 H04·H05에 인스턴스 자원 기록(가용 메모리, CPU, 질의 서비스·터널·DB 컨테이너 메모리, 질의 역할 DB 연결 수, 회의 봇 영향, 메모리 부족 종료, 동기화와 겹침)과 판정 기준을 더했다. 부담이 작다는 판단은 아직 추론이며 이 기록으로 닫는다.


### PR #64 병합 전 운영 확인 (2026-10-26)

- 사용자 요청 범위: PR 승인 기록, 두 운영 연결의 표 소유권 확인, 0007 적용·재실행, 적용 뒤 수동 동기화 확인이다. 질의 서비스·Cloudflare Tunnel·Worker·Discord 배포와 로그인·암호 설정은 제외한다.
- 승인 근거: tkv00의 PR #64 APPROVED 리뷰(마지막 `pullrequestreview-5649650760`). 기존 ADR-008·020의 팀원·OCI 계정 소유자 기록과 대조하고, ADR-022를 Accepted로 기록했다. 별도 검증 에이전트가 PR 원본 API와 문서 diff를 확인했다.
- 운영 연결: 기존 OCI 인증 만료는 사람이 재인증해 해소했다. 승인된 Bastion 관리 SSH 세션과 터널에서 색인·마이그레이션 연결을 각각 확인했다. 두 연결 모두 실제 표 소유자이며 비슈퍼유저이고, 같은 DB를 가리켰다. 역할·소유자 이름과 접속 값은 기록하지 않았다.
- 적용 전: 질의 역할이 없고 기존 RLS·FORCE가 비활성인 것을 확인했다. 관리 자격 증명은 기존 서버 설정에서 SSH로 받아 프로세스 메모리에서만 사용했다. 로컬 자격 증명 파일을 만들지 않고, 명시적 `--env-file /dev/null`과 메모리의 `DATABASE_URL`로 CLI를 실행했다.
- 운영 `qk-migrate --dry-run`: `target=remote`, `pending 0007 query_role`, `applied=0 skipped=6 pending=1`. 적용: `apply 0007 query_role ok`, `applied=1 skipped=6`. 재실행: `applied=0 skipped=7`.
- 적용 뒤: RLS 활성·FORCE 비활성·질의 역할 NOLOGIN을 확인하고 관리 터널을 닫았다. 별도 검증 에이전트가 실제 운영 DB의 마이그레이션 체크섬 전체 일치, RLS 상태, NOLOGIN·NOSUPERUSER·NOBYPASSRLS, 예상 정책 이름 2개를 읽기 전용 조회로 확인했다. 정책 표현 자체는 별도로 조회하지 않았으며 적용 SQL 체크섬과 로컬 역할 시험이 근거다.
- 동기화 preview: `target=remote`, 실행 가능, 추가 임베딩 0건, 예상 0 Neurons, 당일 색인 사용 0·잔여 5,000 Neurons. 임시 점검 도우미의 uv 경로 오류로 첫 preview는 실행하지 못했고, 실제 `/usr/local/bin/uv` 경로를 확인해 다시 실행한 결과다. 운영 코드·서비스 설정은 고치지 않았다.
- 동기화 1회: `sudo systemctl start qk-sync.service`로 시작했다. 2026-10-26 09:43:23~09:44:34 UTC, `Result=success`, `ExecMainStatus=0`, 종료 뒤 inactive/dead. 새 systemd 실행 ID의 journal만 조회한 결과는 `run_id=sync-20261026T094324-88367c1a`, `status=succeeded`, `exit_code=0`, 문서 `UNCHANGED=79`, `SKIP=1`, 제공자 호출 0·사용/추정 0 Neurons다. 추가 임베딩이 없어 이번 실행은 새 사용량 INSERT를 실측한 증거는 아니다.
- 조건: 운영 DB에서 직접 확인한 활성 인덱스는 `iv-4c0bc4fcc642`, 임베딩 모델은 `@cf/baai/bge-m3`이고 청킹 `chk-md-20d966f730bb`, 보안 규칙 `sec-7222e5dd1d6e` 유지. 질문 평가 세트·정답 라벨은 해당 없음(평가 미실행). 기존 타이머는 active, 다음 실행은 2026-10-27 00:30 UTC다.
- 별도 운영 검증: 검증 에이전트가 systemd 상태와 이번 실행 ID의 결과를 직접 조회해 위 성공·건수·0 Neurons를 재확인했다. 활성 인덱스·모델·청킹 값도 운영 DB에서 조회했다.
- 이번 세션 로컬 검증: `python3 scripts/preflight.py`, `git diff --check`, `uv run --no-sync ruff check --no-cache .`, `uv run --no-sync ruff format --check --no-cache .`, `uv run --no-sync qk-dev db up`, `QK_REQUIRE_LOCALDB=1 uv run --no-sync pytest` 통과(2,313 passed, 외부 2 deselected).
- 남은 단계: H00의 소유권 확인과 승인 기록만 닫았다. Tunnel 요금·Worker/Tunnel 데이터 처리 정책, UDP 7844, 질의 전용 토큰 계획과 H01~H05는 미완료다. 이번 운영 확인은 Discord 전체 경로·Workers 런타임 검증을 대신하지 않는다. PR 병합·Jira 완료 처리는 하지 않았다.

### H00 운영 게이트 (2026-10-26, PR #64 병합 뒤)

- 작업 위치: 브랜치 `docs/SCRUM-115-gh-58-discord-ask-ops`(최신 `main` `3a5a98e`에서 분기). 이 단계는 읽기 전용 확인과 문서 기록만 했다.
- 요금·데이터 처리: 공식 문서 근거와 판단은 ADR-022 Data and cost·Evidence에 적었다. Tunnel 나가는 연결은 무료다. Worker·Tunnel 트래픽은 약관·DPA의 목적 제한 조항만 있고 학습 금지 명시 문장은 없다.
  사용자 결정: 이 수준을 받아들이고, Workers Logs(Free 3일 보존)는 H01~H05 동안 기본값으로 둔다. H01에서 로그에 요청 본문이 없는지 확인하고, H05 뒤 `invocation_logs` 끄기를 다시 정한다.
- UDP 7844: OCI CLI(`qello-team`, 다시 인증한 세션)로 서브넷 보안 목록과 NSG egress를 조회했다. 이어 Bastion 관리형 SSH 세션(TTL 30분, 확인 뒤 삭제)으로 호스트 방화벽을 조회했다.
  보안 목록 egress는 모든 프로토콜·`0.0.0.0/0`·stateful 허용이고 NSG는 없다. iptables·ip6tables OUTPUT 정책은 ACCEPT이고, UDP·7844를 막는 규칙이 없다. nftables output 훅은 모두 accept, ufw는 꺼져 있다.
  방화벽·보안 목록은 바꾸지 않았다. 식별자·주소는 출력에서 가렸다. 실제 QUIC 연결은 H01에서 확인한다.
- 전용 토큰: 사용자가 `qk-workers-ai-query-prod`(Qello 전용 계정 소유, Workers AI만, TTL 365일)를 만들고 verify `active`를 확인했다. 값·계정 ID는 대화·저장소에 없다. 서버 배치는 H02다(`docs/sdd/research/tokens.md` 6·7절).
- 비용: 0 Neurons, 외부 모델 호출 0건.
- 다음: H01(시험 질의 서비스로 터널·VPC Service·Worker 배포, Discord 수신 주소 서명 확인). 공유 인스턴스·Cloudflare·Discord를 바꾸므로 사람이 인증하고 명령마다 승인한다.

### H01 Worker 로컬 확인 (2026-10-26)

- 조건: 저장소 밖 사본(`pywrangler sync`·`dev`, wrangler 4.149.0 고정)에서 실행했다. VPC 바인딩은 원격이 필요해 로컬 설정 사본에서만 뺐다. 로컬 workerd가 호환 날짜 2026-10-13까지라 `--compatibility-date 2026-10-13`으로 낮췄다(배포는 2026-10-26 그대로). 합성 Ed25519 키, 외부 호출 0, Neurons 0.
- 찾은 문제(원래 코드):
  - `wrangler.toml`에 `base_dir`가 없어 번들에 `query/` 폴더 파일만 들어갔다. `qello_knowledge.config`·`discord`를 가져오지 못한다.
  - 모든 요청이 500(`'Request' object has no attribute 'arrayBuffer'`).
  - SDK 소스 기준(추론): SDK는 JS 클래스 이름이 `Fetcher`인 바인딩을 감싸 `fetch(url, **kwargs)`로 받고, 그 응답은 `bytes()`·`headers.get`을 쓴다. VPC Service 바인딩이 `Fetcher`인지는 소스로 확인할 수 없어 배포에서 확인한다.
    `waitUntil`은 SDK ASGI 구현처럼 작업 프록시를 넘긴다.
- 수정: `worker.py`(본문 `bytes()`, `fetch` 키워드 인자, `headers.get`, `waitUntil` 프록시와 정리, 실패 로그에 예외 클래스 이름만), `wrangler.toml`(`base_dir = "src"`, 번들 164개 모듈 약 710 KiB).
- 수정 뒤 로컬 결과: `/healthz` 200, 서명 없음·잘못된 서명 401, 서명된 PING `{"type":1}`(Web Crypto Ed25519 FFI 동작), 바인딩 없는 `/ask` → 대체 안내 type 4(나만 보기), 로그 `{"kind": "relay_failed", "error": "AttributeError"}`.
- 남은 확인(배포): VPC 바인딩 `fetch`의 요청 본문 전달, 응답 헤더 `X-QK-Run`, `waitUntil` 시작 확인 204, 호환 날짜 2026-10-26 배포.
- 독립 검토(별도 에이전트, 읽기 전용, SDK 1.9.5·wrangler 4.149.0 소스 대조): 승인. High 0. Medium 1: VPC Service 바인딩이 `Fetcher`가 아니면 `/ask`가 대체 안내로 끝난다. 배포 첫 `/ask` 로그의 `error`로 확인하고 필요하면 그때 고친다.
  Low: 확인 범위보다 단정적인 문구(반영), 시간 초과 때 응답 본문 읽기가 중단되지 않음(동작 영향 없음, 유지). 번들의 import 추적에서 표준 라이브러리 밖 모듈 수준 import 0건.
- 시험 서비스 `measurement/h01_probe.py`: 로컬에서 합성 키로 PING 200, 변조·오래된 서명 401, 다른 애플리케이션 거부, `/ask` → type 5·`X-QK-Run`, 다른 서명의 시작 확인 409, 시작 확인 204와 갱신 1회, 재시작 확인 409를 확인했다(Discord 전송은 가짜로 바꿔 외부 호출 0).

### H01 배포 확인 (2026-10-26~27)

- 조건: Cloudflare Qello 전용 계정, wrangler 4.149.0, Worker 호환 날짜 2026-10-26, 커밋 `c512170`의 `worker.py`·`wrangler.toml`. 실제 VPC Service ID를 넣은 배포 설정은 저장소 밖 사본에만 두었다.
  시험 서비스 `measurement/h01_probe.py`(커밋 `2158f42`)를 공유 인스턴스에 임시 유닛(`nobody`, 메모리 상한 128M)으로 띄웠다. Workers AI·DB 호출 0, Neurons 0. 식별자·주소·키·토큰은 기록하지 않는다.
- 공유 인스턴스: `cloudflared` 2026.10.4(Cloudflare 공식 apt 저장소)를 설치했다. 서비스 `qk-cloudflared.service`는 `DynamicUser`, 토큰을 `LoadCredential`로 받아 `--token-file`로 넘기고
  `--protocol quic`으로 고정했다. 토큰은 사람이 숨김 입력했고(root:root 0600) 프로세스 인자에 없다. 설치 뒤 다른 서비스 재시작 0건(apt·journal 확인), 회의 봇 컨테이너·`qk-postgres`·`qk-sync.timer` 유지.
- 터널: QUIC 연결 4개 등록, cloudflared 사전 점검 "Environment is healthy", Cloudflare 쪽 상태 `healthy`. quic-go UDP 수신 버퍼 증가 실패 경고가 있었다(`net.core.rmem_max`). 연결에는 영향이 없어 sysctl은 바꾸지 않았다.
- Cloudflare: VPC Service(HTTP, `127.0.0.1:8787`, 터널 연결), Worker `qello-knowledge-relay` 배포(164개 모듈, gzip 189 KiB, 기동 681 ms), 비밀값 `DISCORD_PUBLIC_KEY`(사람이 숨김 입력).
  비대화형 배포가 계정에 workers.dev 서브도메인이 없다며 작업 폴더 이름으로 서브도메인을 자동 등록했다. 수신 주소 등록 전에 사람이 대시보드에서 팀 이름으로 바꿨다. 이후 배포 전에는 서브도메인 존재를 먼저 확인한다.
- Discord: `Qello Knowledge`를 시험 서버에 `applications.commands`로 설치했다. Interactions Endpoint URL 저장 때 Discord 검증 요청 2건이 서명된 PING 200(CPU 8 ms), 틀린 서명 401로 통과했다.
  `/ask`를 서버 한정으로 등록했다(`register-commands`, 먼저 `--dry-run`. 로컬 `.env`의 봇 토큰 값이 비어 있어 이번 실행에만 숨김 입력하고 바로 지웠다). 역할 제한이 없어 서버의 모든 멤버에게 보인다.
- `/ask` 3회(시험 문구): 3회 모두 Worker 200(`relayed`, VPC 왕복 404~459 ms, `error` 없음), 시험 서비스 type 5, 시작 확인 204(`start_failed` 0), 원 메시지 갱신 200(354~892 ms).
  Discord가 받은 첫 응답의 Worker wall time 852~974 ms(3초 안). 독립 검토 Medium(VPC 바인딩이 `Fetcher`로 감싸지는가)은 실제 동작으로 해소됐다.
- Workers Logs: `wrangler tail`의 요청 항목은 `cf`·`headers`·`method`·`url`뿐이고 본문이 없다. 헤더에는 서명·타임스탬프와 Cloudflare 기본 헤더가 있다. 저장되는 Workers Logs(Free 3일)도 같은 항목으로 본다 `(추론, 대시보드 미확인)`.
- **위험(H04로 넘김)**: `/ask` 중계 요청의 Worker CPU가 121~189 ms다(Free 한도 10 ms의 12~19배). 문서상 가끔 넘는 것은 허용하지만 꾸준히 넘으면 Error 1102(`exceededCpu`)로 끊고,
  그때는 대체 안내도 나가지 않고 Discord에 "응답하지 않음"이 뜬다. 이번 3회는 모두 `ok`였다. H04에서 10회 이상 재서 `exceededCpu`가 나면 중계만 TypeScript로 옮기는 안(research R-13)을 올린다.
  Python 안에서 줄이기, Workers Paid(월 고정비, ADR-008·C-05 승인 필요)도 대안이다. `/healthz` 첫 요청은 CPU 225 ms였다.
- 정리: 시험 서비스 중지(임시 유닛 제거), `h01-probe.env`·값 입력 스크립트·`/usr/local/lib/qk-h01` 삭제, Bastion 세션 삭제. 남긴 것: 터널, `qk-cloudflared`, 터널 토큰 파일과 입력 스크립트 `/usr/local/sbin/qk-tunnel-token-setup`,
  VPC Service, Worker, 수신 주소, `/ask` 명령. H02 전까지 `/ask`는 Worker 대체 안내("지금은 답할 수 없습니다", 나만 보기)를 받는다 `(추론, 중지 뒤 호출 미확인)`.
- 남은 일: H02(실제 질의 서비스 구성), H03(SC-010), H04(CPU·첫 응답 측정), H05(실측). 사람 확인: 로컬 `.env` 권한이 644로 `tokens.md` 기록(600)과 다르다.

### H04 일부 측정 (2026-10-27, H02 전)

- 조건: H01과 같은 Worker(커밋 `c512170`)·터널·VPC Service. 시험 서비스(커밋 대기 중인 거부 경로 흉내 포함)를 임시 유닛으로 다시 띄웠다. 시험 채널에서 사람이 시험 문구로 `/ask`를 보냈다.
  Worker 기록은 `wrangler tail`의 요청별 `cpuTime`·`wallTime`과 Worker 로그(`relayed`, 중계 왕복 ms)다. Workers AI·DB 호출 0, Neurons 0.
- 표본: 23건. 거부 경로 흉내(`나만_보기` 켬 → 시험 서비스 type 4, 시작 확인 없음) 10건, 허용 경로(type 5 + 시작 확인 204 + 원 메시지 갱신 200) 13건. 23건 모두 outcome `ok`, `exceededCpu`·Worker `error` 0건.
  시험 서비스 기록과 건수가 같다(type 4 10, type 5 13, 시작 확인 204 13, 갱신 200 13, 갱신 p50 371 ms·최대 829 ms).

| 경로 | n | Worker CPU p50 / p95 / 최소 / 최대 (ms) | 10 ms 초과 | 중계 왕복 p50 / p95 / 최대 (ms) |
| --- | --- | --- | --- | --- |
| 거부 흉내(type 4) | 10 | 29.5 / 155.5 / 18 / 250 | 10/10 | 357 / 841 / 1,146 |
| 허용(type 5 + 시작 확인) | 13 | 37 / 144 / 21 / 172 | 13/13 | 369 / 381 / 382 |
| 전체 | 23 | 31 / 167 / 18 / 250 | 23/23 | 366 / 460 / 1,146 |

- 해석: 따뜻한 isolate에서도 CPU가 18~52 ms로 Free 한도(10 ms)의 2~5배이고, 새 isolate로 보이는 요청(첫 요청 250 ms, 46초 쉰 뒤 연속 3건 108~172 ms)은 10~25배다. 이번 표본에서는 끊기지 않았지만
  문서상 "꾸준히" 넘으면 1102로 끊는 조건에 해당한다. 허용 경로 CPU에는 `waitUntil` 시작 확인 처리도 들어 있다 `(추론)`. 비교로 서명 검사만 하는 PING은 8 ms(H01, 1건)였다.
- 첫 응답 시간: Discord가 기다리는 첫 응답은 Worker가 시험 서비스 응답을 받아 돌려주는 시점이다. 중계 왕복 p50 366 ms·p95 460 ms·최대 1,146 ms, Worker wall(거부 흉내) 최대 1,164 ms로 3초 안이다.
  실제 질의 서비스의 첫 응답 결정(M-03)은 H02 뒤에 잰다.
- 인스턴스 기준선(질의 없음 10분, 30초 간격 20회): 위 "인스턴스 자원 기록" 표 기준선 열. 측정 시간대(기준선 시작부터 `/ask` 뒤까지) 커널 로그의 메모리 부족 종료 0줄. 측정 뒤 가용 4,526 MB, load 0.15.
  첫 수집 스크립트의 메모리 부족 종료 집계는 시각 형식 오류로 무효였고, 같은 구간을 다시 조회한 값이 위 0줄이다.
- 판정(M-02): Worker CPU가 Free 한도를 **꾸준히** 넘는다(23/23). research R-13의 대안 발동 조건("자주 넘으면")에 해당하므로 중계만 TypeScript로 옮기는 안을 사람 결정으로 올린다.
  대안: Python 안에서 줄이기(PING 8 ms가 하한에 가까워 10 ms 안쪽 보장은 어렵다고 본다 `(추론)`), Workers Paid(월 고정비, ADR-008·C-05 승인 필요).
- 미측정: PING(연결 확인) 10회(Discord는 수신 주소 저장 때만 보낸다), 대시보드 Worker 지표, 실제 질의 서비스 경로. 정리: 시험 서비스 중지·임시 파일 삭제·Bastion 세션 삭제.

### 중계 Worker TypeScript 이전 (2026-10-27, ADR-024 Proposed)

- 사용자 결정: H04 일부 결과로 research R-13 대안(B)을 택했다. Python Worker 코드는 지우고 계약 시험을 TS로 옮긴다. 시험은 `node --test`(npm 의존성 0), CI에 `relay` job을 더한다. 결정 기록은 ADR-024.
- 변경: `workers/relay/relay.ts`(순수 판단), `workers/relay/index.ts`(진입점, 공개 키 isolate 캐시, `AbortSignal.timeout`과 경쟁 타이머로 중계 제한 시간 보장), `workers/relay/relay.test.ts`(14개).
  `wrangler.toml`은 `main = "workers/relay/index.ts"`, `python_workers`·`base_dir` 제거. 삭제: `query/worker.py`, `discord/relay.py`, `test_bot_relay.py`. `signature_headers`는 `discord/interactions.py`로 옮겼다.
  개발 의존성 `workers-py` 제거(`uv.lock`의 패키지 항목 24개 → 16개, `workers-py`와 그 의존성 8개).
- 시험 이동: 이전 Python 계약 시험 5개(precheck·PING, 실패 대체 안내 3, 중계·시작 확인·기록 허용 목록)의 기대값을 TS 시험으로 옮기고, 진입점 시험 7개(healthz, 경로·크기·서명 거부, PING, 중계와 시작 확인,
  즉시 안내, 실패·시간 초과 기록, 시작 확인 실패 기록)를 실제 Ed25519 서명과 가짜 VPC 바인딩·`waitUntil`로 더했다. RED(모듈 없음) → GREEN 확인.
- 검증: `node --test workers/relay/relay.test.ts` 14 passed, `QK_REQUIRE_LOCALDB=1 uv run pytest` 2,309 passed(외부 2 제외, 이전 2,313에서 옮긴 5개 빠지고 1개 더함), ruff check·format, preflight, `git diff --check` 통과.
  로컬 `wrangler dev`(workerd, 호환 날짜 2026-10-13로 낮춤, 합성 키, 외부 호출 0): `/healthz` 200, 서명 없음·잘못된 서명 401, 서명된 PING `{"type":1}`, 바인딩 없는 `/ask` → 대체 안내와 `relay_failed`·`error=TypeError`.
- 독립 검토(별도 에이전트, 읽기 전용, Node 24·esbuild로 재현): 변경 요청 H1·M1·L4건 → 반영.
  H1: CI의 `node --test workers/relay/`(디렉터리 인자)가 Node 24에서 실패 → 시험 파일 경로로 바꿈. M1: 응답 헤더 대기와 본문 읽기에 제한 시간이 따로 걸려 최악 2배 → 한 번의 제한 시간으로 묶음
  (시험을 먼저 더해 1.9초 RED 확인 뒤 GREEN). L1: ADR-024의 로컬 시간 비교 문장(CPU가 아닌 클라이언트 측정 시간) 정정. L2: `uv.lock` 빠진 패키지 수 정정. L3: ADR-022의 지운 파일 참조 정정.
  L4: 숫자가 아닌 Content-Length 400과 본문 읽기 시간 초과 시험 추가(14개). 동작 동등성·healthz·보안 경로 결함 없음.
  재검토: 승인(High·Medium 0). 선택 Low(시간 시험 상한 1,400 → 1,700 ms, 회귀 1.9초와 간격 유지)를 반영했다. Node 24·26 모두 14 passed.
- 남은 확인: 재배포와 운영 Worker CPU 재측정(H04), 타입 검사는 하지 않는다(ADR-024 Negative).

### H04 TS 중계 재측정 (2026-10-27)

- 조건: TS Worker(커밋 `1257d10`, 업로드 8.4 KiB, 기동 2 ms)를 같은 이름·VPC Service·비밀값으로 재배포했다. 시험 서비스(커밋 `7f69179`)를 임시 유닛으로 다시 띄웠고, 사람이 시험 채널에서 시험 문구로 `/ask`를 보냈다.
  `wrangler tail`의 요청별 `cpuTime`·`wallTime`과 Worker 로그로 셌다. 경로는 시험 서비스 기록(type 5 21, type 4 10)과 Worker wall(시작 확인 대기 포함 여부)로 나눴다. Workers AI·DB 호출 0, Neurons 0.
- 첫 20회는 `나만_보기` 옵션이 붙지 않아 모두 허용 경로였고, 거부 경로 10회를 따로 더 보냈다. 시험 서비스가 21건인 것은 로그 수집 연결 직전 1건으로 본다 `(추론)`.

| 경로 | n | Worker CPU p50 / p95 / 최소 / 최대 (ms) | 10 ms 초과 | 중계 왕복 p50 / p95 / 최대 (ms) |
| --- | --- | --- | --- | --- |
| 거부 흉내(type 4) | 10 | 1 / 3.7 / 1 / 5 | 0/10 | 336 / 353 / 355 |
| 허용(type 5 + 시작 확인) | 20 | 2.5 / 5 / 1 / 5 | 0/20 | 340 / 355 / 366 |
| 전체 | 30 | 2 / 5 / 1 / 5 | 0/30 | — |

- 비교(Python Worker, "H04 일부 측정"): CPU p50 31 ms·p95 167 ms·최대 250 ms, 23/23건 초과 → TS는 p50 2 ms·최대 5 ms, 0/30건 초과. outcome 모두 `ok`, Worker `error` 0, 시작 확인 204·원 메시지 갱신 200 21건.
- 판정(M-02 명령 경로): 통과. Worker CPU가 Free 한도 안이다. 30초 넘게 쉰 뒤의 새 isolate 요청은 이번 표본에서 따로 확인하지 못했다(최대 간격 약 14초). PING 10회와 실제 질의 서비스 경로(M-03)는 H02 뒤.
- 정리: 시험 서비스 중지·임시 파일 삭제·Bastion 세션 삭제·로그 수집 종료. 터널·`qk-cloudflared`·VPC Service·Worker·수신 주소·`/ask`는 H02용으로 남긴다.

### H02 질의 서비스 구성 (2026-10-27)

- 실행: 아래쪽 Herdr 패널의 Claude(실행 에이전트)가 운영 문서 7.2·7.3대로 했다. 서버·DB를 바꾸는 명령은 사람이 하나씩 승인했고, 비밀값은 사람이 대화형 SSH에서 숨김 입력했다.
  오케스트레이터가 별도 Bastion 세션에서 읽기 전용으로 결과를 다시 확인했고 보고와 일치했다. 값·주소·식별자는 기록하지 않는다.
- 구성:
  - 시스템 사용자 `qkquery`(추가 그룹 없음, 로그인 셸 없음, 홈 없음)
  - 질의 릴리스 `/opt/qello-knowledge-query`(root:qkquery 0750, `origin/main` `3a5a98e`). `uv sync --locked --extra query --extra postgres`.
    uv 관리 Python 3.13을 릴리스 안 `.python/`에 두어(`UV_PYTHON_INSTALL_DIR`) `qkquery`와 `ProtectHome=yes`에서 읽힌다. 168 MB. main에 남은 개발 의존성 `workers-py`도 함께 설치됐다(PR #66 병합 전).
  - `qk_query`: LOGIN, 암호 SCRAM-SHA-256(사람이 `\password`로 입력), super·createrole·createdb 없음. `qkquery`로 DB 연결과 `qk.embedding_usage` 읽기 권한 확인
  - `/etc/qello-knowledge/query.env`(root:qkquery 0640, 8개 키, 역할 목록만 빈 값). `qk-query check` 누락·형식 오류 0
  - `qk-query.service`(운영 문서 7.3 유닛, `--port 8787`): active, 재시작 0, 루프백 8787만 수신, `/healthz` 200 `ok=true`, 메모리 약 34 MB(상한 512 MB)
- 0 Neurons 확인: 허용 밖 채널 `/ask` 2회 → 거부 안내(나만 보기), 운영 로그 `access=channel_outside`·`status=access_denied`, 검색·생성·전송 호출 0, 첫 응답 결정 0~1 ms.
  운영 로그 키는 `run_id, access, private, status, failure, timings_ms, calls, deliver_retries, deliver_failure, retrieval_summary, generation_summary`뿐이고 원문 필드가 없다.
- 범위 밖 허용 경로 1건: 서비스 기동 약 1분 30초 뒤 시험 서버의 누군가가 허용 채널에서 공개로 `/ask`를 보냈다. 검색 5·생성 2·전송 1회, 결과 `cannot_confirm`, 검색 870 ms·생성 639 ms·전송 1,071 ms,
  생성 13.42 Neurons(측정)·검색 임베딩 0 Neurons(측정). 실제 경로(qk_query 검색, 전용 Workers AI 토큰, 원 메시지 갱신)가 동작한 사실이지만 H05 실측 표본으로는 쓰지 않는다.
  사용자 결정(2026-10-27): 허용 채널을 그대로 열어 둔다(누구나 `/ask`로 Neurons를 쓸 수 있고, 하루 예산 검사는 질의 서비스가 한다).
- 실행 중 실수: 관리 DB 조회 한 번에서 관리 암호가 `docker exec -e PGPASSWORD=<값>` 꼴로 약 1초 동안 같은 호스트의 프로세스 인자에 있었다. 외부 전송·기록은 없다. 이후 명령은 이름만 넘기는 꼴로 바꿨다.
  사용자 결정(2026-10-27): 암호를 교체하지 않는다.
- 공유 인스턴스 영향: `qk-postgres`·회의 봇 컨테이너 재시작 0, `qk-cloudflared`·`qk-sync.timer` active, 가용 메모리 약 4.5 GB. `MemoryMax=512M`은 초기값이며 질의 중 메모리는 H04 남은 항목에서 잰다.
- 되돌리기(운영 문서 7.5): `qk-query` 중지·비활성화, 유닛 삭제, 관리 psql `ALTER ROLE qk_query NOLOGIN;`, `query.env`·릴리스 폴더 삭제, `userdel qkquery`. 터널·Worker·수신 주소·명령은 사람 승인 뒤 해제한다.
- 남은 일: PR #66 병합 뒤 질의 릴리스 갱신 절차가 없다(H03~H05 전에 정하거나 기록한다). 서버 배너 "System restart required"는 범위 밖이라 두었다.

### H03 외부 접속 차단 확인 (2026-10-27, SC-010)

- 조건: 인스턴스 밖(작업자 PC, 일반 인터넷 회선)에서 OCI CLI로 인스턴스 공인 주소를 조회해 기록하지 않고 썼다. `nc -z`(연결 제한 5초)로 포트마다 3회 시도했다. 2026-10-26T18:01Z.
- 결과: 대조 22번은 3회 모두 연결됐다(172~176 ms). DB 포트 5432와 질의 포트 8787은 3회 모두 5초 제한까지 응답 없이 실패했다(거부 응답 없이 버려짐).
- 해석: 보안 목록이 22번만 받고(H00·운영 문서 1절), 그 안쪽에서도 DB 컨테이너는 `127.0.0.1:5432`, 질의 서비스는 `127.0.0.1:8787`에만 묶여 있다(H02 재확인). 두 겹 모두 바깥 접속을 막는다.
  안쪽 경로(질의 서비스 healthz, 터널 경유 Worker 중계)는 H01·H02에서 동작을 확인했다.
- 판정: SC-010 통과. 비용 0, 서버 설정 변경 없음.

### H04 실제 질의 서비스 기준 측정 (2026-10-27)

- 조건: H02의 실제 질의 서비스(`qk-query`, main `3a5a98e`)와 TS Worker. 서버 자원은 Bastion 세션에서 읽기 전용으로 5초마다 기록했다(A구간 질의 없음 10분 120회, B구간 8.5분 96회, `docker stats`는 30초마다).
  B구간에 사람이 허용 밖 채널에서 시험 문구로 `/ask` 10회(4~5초 간격)를 보냈다. Worker는 `wrangler tail`로 기록했다. 0 Neurons(검색·생성 호출 0).
- M-03(첫 응답): 질의 서비스의 첫 응답 결정 `first_response` 0 ms(10/10), 검색·생성·전송 호출 0, `access=channel_outside`·`status=access_denied`·나만 보기.
  Worker 중계 왕복 p50 343 ms·p95 367 ms·최대 376 ms, Worker wall 최대 377 ms로 3초 마감 안이다. 왕복 시간은 대부분 Worker ↔ 터널 ↔ 인스턴스 네트워크다 `(추론, 질의 서비스 결정 0 ms)`.
- M-02(Worker CPU, 실제 질의 서비스 경로): 10건 p50 1 ms·p95 3 ms·최대 3 ms, 10 ms 초과 0, outcome 모두 `ok`. 첫 요청은 앞선 요청 뒤 약 40분 쉰 다음이라 새 isolate일 가능성이 크다 `(추론)`. 그 요청 CPU는 3 ms였다.
- 자원(A → B): 가용 메모리 4,487~4,516 → 4,486~4,513 MB, load 0~0.12 → 0~0.51, `qk-query` 33 → 33 MB(상한 512 MB), `qk-query` CPU 750 → 613 ms(구간 합), `qk-cloudflared` 14 MB,
  `qk-postgres` CPU 0~3.1%·262 MiB, 회의 봇 1 CPU 0~0.03%·120 MiB, 회의 봇 2 CPU 0.04~0.74%·424~427 MiB. `qk-query` 재시작 0, 메모리 부족 종료 0줄, 컨테이너 재시작 0.
- 판정: 허용 밖 경로에서 M-02·M-03 통과. 공유 인스턴스 부담은 질의 없음과 차이를 보기 어렵다. 질의 역할 DB 연결 수와 검색·생성 중 자원은 허용 경로가 있어야 하므로 H05에서 잰다.
- 미측정: Discord PING(연결 확인) 10회. Discord는 수신 주소를 저장할 때만 PING을 보내 반복하기 어렵다. H01의 PING 2건(Python Worker)과 TS Worker 진입점 시험으로 갈음하고, 필요하면 수신 주소를 다시 저장해 잰다.
