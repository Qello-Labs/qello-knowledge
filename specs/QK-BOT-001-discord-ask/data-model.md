# Data Model: QK-BOT-001 Discord `/ask`

도메인 타입은 `src/qello_knowledge/domain/discord.py`에 둔다(외부 SDK 타입 없음, C-06). 값은 모두 불변(`frozen=True`) 데이터 클래스다.

## 1. 설정

설정 진입점을 나눈다. 지금 `Entrypoint.QUERY`는 Worker와 로컬 서버가 같이 쓴다. Worker는 중계만 하므로 `Entrypoint.RELAY`를 새로 두고, `QUERY`는 인스턴스 질의 서비스가 쓴다.

| 이름 | 진입점 | 필수 | 비밀 | 규칙·초기값 | spec |
| --- | --- | --- | --- | --- | --- |
| `DISCORD_PUBLIC_KEY` | relay, query | 예 | 아니오 | 64자 16진(기존) | FR-001 |
| `DISCORD_APPLICATION_ID` | query, register | 예 | 아니오 | 17~20자리 숫자(기존) | FR-022, 웹후크 경로 |
| `DISCORD_BOT_TOKEN` | register(명령 등록 명령만) | 등록 때만 | 예 | 기존 규칙 | R-12 |
| `QK_RELAY_TIMEOUT_SECONDS` | relay | 아니오 | 아니오 | 0.5~2.8, 2.5 | FR-011 마지막 행 |
| `QK_DISCORD_GUILD_ID` | query, register | 예 | 아니오 | 17~20자리 숫자 | FR-004 |
| `QK_DISCORD_ALLOWED_CHANNELS` | query | 아니오 | 아니오 | 쉼표로 나눈 17~20자리 숫자 목록. 비면 모두 거부하고 설정 검사가 경고 | FR-004, FR-023 |
| `QK_DISCORD_ALLOWED_ROLES` | query | 아니오 | 아니오 | 같은 꼴. 비면 역할 제한 없음 | FR-004 |
| `QK_QUERY_DEADLINE_SECONDS` | query | 아니오 | 아니오 | 15~120, 55 | FR-008, research R-06 |
| `QK_QUERY_START_WAIT_SECONDS` | query | 아니오 | 아니오 | 4~10, 5. 하한 4는 Discord 첫 응답 3초 + 1초다. 그래서 `NOT_STARTED` 안내는 Discord가 첫 응답을 받았거나 받을 수 없게 된 뒤에만 나간다 | research R-03(시작 확인 대기) |
| `QK_QUERY_MIN_START_SECONDS` | query | 아니오 | 아니오 | 8~60, 15 | research R-05(대기 작업 최소 시작 시간) |
| `QK_QUERY_NOTICE_GRACE_SECONDS` | query | 아니오 | 아니오 | 1~30, 5 | FR-008 |
| `QK_QUERY_CALL_LIMIT` | query | 아니오 | 아니오 | 11~50, 20 | FR-016 |
| `QK_DISCORD_MAX_MESSAGES` | query | 아니오 | 아니오 | 2~10, 4 | FR-012 |
| `QK_DISCORD_TITLE_MAX_CHARS` | query | 아니오 | 아니오 | 20~200, 80 | FR-013 |
| `QK_DISCORD_LINK_MAX_CHARS` | query | 아니오 | 아니오 | 50~1000, 300 | FR-013 |
| `QK_QUERY_WORKERS` | query | 아니오 | 아니오 | 1~8, 2 | R-05 |
| `QK_QUERY_QUEUE_SIZE` | query | 아니오 | 아니오 | 1~16, 4 | R-05 |
| (설정 아님) 포트 | — | — | — | 기존 `qk-query serve --port`(기본 8787)를 그대로 쓴다. systemd 유닛이 지정 | R-05 |
| `DATABASE_URL` | 기존(index, query) 유지 | 예 | 예 | 운영 질의 서비스는 `qk_query` 역할 URL | FR-019 |
| `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID` | 기존 index에 query를 더함 | 예 | 예/아니오 | 질의 서비스 전용 토큰 | R-08 |
| 생성·검색·예산 설정(`QK_GEN_*`, `QK_RETRIEVAL_CONTEXT_BUDGET`, `QK_EMBED_*`) | 기존 진입점에 query 포함 | 기존 | 기존 | 기존 | FR-015 |

설정 검사(교차 규칙):

- `QK_QUERY_DEADLINE_SECONDS + QK_QUERY_NOTICE_GRACE_SECONDS < 900`(상호작용 토큰 15분), 기본 생성 설정의 `2 × QK_GEN_TIMEOUT_SECONDS + 5 ≤ QK_QUERY_DEADLINE_SECONDS`(FR-008),
  `QK_QUERY_MIN_START_SECONDS < QK_QUERY_DEADLINE_SECONDS`.
- 출처 목록 산식(FR-012): `항목 최대 길이 = 2 × 제목 상한 + 1 + 링크 상한 + 2 × 버전 최대 12 + 고정 이름표·날짜·구분자`, `메시지당 항목 = ⌊(2000 − 목록 머리글) ÷ 항목 최대 길이⌋ ≥ 1`,
  `⌈expand_top ÷ 메시지당 항목⌉ ≤ QK_DISCORD_MAX_MESSAGES − 1`. `expand_top`은 검색 설정 `RetrievalSettings.expand_top`(기본 8)이다. 질의 서비스는 검색 요청별 덮어쓰기를 쓰지 않는다. 고정 길이 상수는 렌더러(`discord/render.py`)가 내보내는 실제 문자열에서 계산해 시험으로 묶는다.
- 질의 외부 호출 상한 ≥ 검색 상한(7) + 생성 상한(4) + 메시지 수 상한 × 2(전송 + 재시도).

## 2. 상호작용

**`Interaction`** (질의 서비스가 원본 본문에서 만든다)

| 필드 | 뜻 |
| --- | --- |
| `interaction_id: str` | 중복 판정에만 쓴다. 운영 로그에 남기지 않는다 |
| `token: str` (repr 숨김) | 상호작용 토큰. 답변 갱신 경로에만 쓰고 기록하지 않는다 |
| `kind: InteractionKind` | `PING`, `COMMAND`, `OTHER` |
| `command: str \| None` | 명령 이름 |
| `question: str \| None` (repr 숨김) | "질문" 인자 |
| `private: bool` | "나만 보기" 인자. 없으면 거짓, 참·거짓이 아니면 참(spec Edge Cases) |
| `guild_id: str \| None`, `channel_id: str \| None` | 허용 범위 판정용 |
| `channel_kind: ChannelKind` | `TEXT`, `THREAD`, `DM`, `OTHER` |
| `member_roles: tuple[str, ...]` | 허용 역할 판정용 |

검증: 본문 크기 상한(64 KiB), JSON 실패·필수 필드 없음은 `OTHER`로 보고 "지원하지 않는 요청" 안내. 사용자 식별자와 이름은 읽지 않는다.

**`AccessDecision`**: `ALLOWED`, `GUILD_OUTSIDE`, `CHANNEL_OUTSIDE`, `THREAD`, `DM`, `ROLE_MISSING`, `NOT_CONFIGURED`. `ALLOWED`가 아니면 모두 같은 허용 범위 안내(spec FR-004).

## 3. 첫 응답

**`FirstResponse`**: 질의 서비스가 Worker에 돌려주는 값이자 Discord에 그대로 가는 상호작용 응답.

| 경우 | 유형 | 플래그 | 뒤따르는 작업 |
| --- | --- | --- | --- |
| 연결 확인 | 1(PONG) | 없음 | 없음 |
| 지원하지 않는 요청, 허용 범위 밖, 비밀값 질문, 수명 자리 없음 | 4 | 64 | 없음 |
| 중복 상호작용 | 4 | 64, 본문 "이미 처리 중인 요청입니다." | 없음 |
| 허용된 `/ask` | 5 | `private`이면 64 | `QueryJob`을 시작 대기로 등록, 응답 헤더 `X-QK-Run: <run_id>` |

Worker가 질의 서비스에서 답을 못 받으면 Worker가 유형 4, 플래그 64, "지금은 답할 수 없습니다…"를 만들고 시작 확인을 보내지 않는다. 답을 받아 처리 중 응답을 Discord에 돌려준 경우에만
`POST /discord/interactions/start`로 시작 확인을 보낸다(contracts/relay.md 3절).

## 4. DB 역할 `qk_query` (마이그레이션 0007)

- `NOLOGIN` 역할로 만든다. 운영 담당자가 서버에서 `LOGIN`과 암호를 정한다(저장소에 없음).
- 권한(최소, 구현 때 로컬 DB 시험으로 확정):
  - `USAGE ON SCHEMA qk`
  - 읽기: `SELECT ON qk.index_version, qk.artifact, qk.chunk, qk.embedding`
  - 검색: `EXECUTE ON FUNCTION qk.active_index_version, qk.visible_access_scope, qk.is_visible, qk.kind_matches, qk.hit_json, qk.search_vector, qk.search_keyword, qk.search_keyword_terms,
    qk.chunk_neighbors, qk.context_item_json, qk.chunk_context`
  - 질의 임베딩 사용량: 질의 경로는 `embedding_record`(기록 INSERT)와 `embedding_usage_today`(읽기)만 쓴다. 예약·정산(`embedding_reserve`·`embedding_settle`)은 색인(`EmbedPurpose.INDEX`)만
    쓴다(`embedding/service.py:256–265`). 그래서 `EXECUTE ON FUNCTION qk.embedding_record, qk.embedding_usage_today`(와 그 함수가 부르는 보조 함수), `SELECT, INSERT ON qk.embedding_usage`,
    `SELECT ON qk.embedding_usage_daily`
  - 생성 사용량: `EXECUTE ON FUNCTION qk.generation_record, qk.generation_usage_today`, `SELECT, INSERT ON qk.generation_usage`, `SELECT ON qk.generation_usage_daily`
  - 식별 열 시퀀스가 있으면 `USAGE`만
- 주지 않는 것: `qk.sync_*` 표, 예약·정산 함수, 정리 함수(`*_prune`), 기존 기록 `UPDATE`, daily 표 쓰기(0003:171, 0006:100의 INSERT는 정리 함수 안에 있다), `DELETE`·`TRUNCATE`,
  스키마 변경, 문서·청크·임베딩·인덱스 버전 쓰기 (2026-10-25 독립 검토 H4).
- 함수는 모두 `SECURITY INVOKER`다(0002~0006에 `SECURITY DEFINER` 없음, 2026-10-25 확인). 그래서 함수가 쓰는 표 권한이 역할에 있어야 한다. 새 함수는 `PUBLIC`이 기본으로 `EXECUTE`를 갖는다
  (https://www.postgresql.org/docs/current/sql-createfunction.html). 정산·정리 함수는 `UPDATE`·`DELETE`가 필요해 표 권한에서 막힌다. 그러나 **예약 함수 `embedding_reserve`는 `SELECT`와
  `INSERT`만 쓰므로**(0003:67–84) 표 권한만으로는 막히지 않는다(2026-10-25 독립 재검토 H4). 직접 `INSERT`로 `purpose = 'index'` 행을 넣는 것도 같다.
- 그래서 `qk.embedding_usage`에 행 단위 보안(RLS)을 켜고 `qk_query`에만 정책을 둔다.
  - `FOR SELECT TO qk_query USING (true)`, `FOR INSERT TO qk_query WITH CHECK (purpose = 'query')`. `UPDATE`·`DELETE` 정책은 두지 않는다.
  - `FORCE ROW LEVEL SECURITY`는 쓰지 않는다. 표 소유자와 슈퍼유저는 RLS를 건너뛰므로 기존 색인·마이그레이션 동작은 바뀌지 않는다 `(일반 설명, PostgreSQL RLS 문서로 구현 때 확인)`.
  - **운영 전제**: 운영 색인(`qksync`의 `DATABASE_URL`)과 마이그레이션이 표 소유자나 슈퍼유저로 붙는지 확인한다. 운영 문서에 그 역할이 적혀 있지 않다(2026-10-25 확인). 소유자가 아닌 다른
    역할이 이 표를 쓰면 그 역할에도 정책을 더한 뒤에 0007을 적용한다. 확인 전에는 0007을 운영에 적용하지 않는다.
  - `qk.generation_usage`는 생성 기록만 담는 표라 RLS를 두지 않는다. 질의 역할이 쓰는 행이 그 표의 유일한 용도다.
- 마이그레이션은 `PUBLIC`의 함수 `EXECUTE`를 거두지 않는다(기존 역할 동작을 바꾸지 않기 위해). 막는 것은 표 권한과 RLS다.
- 로컬 DB 시험(SC-010)이 확인할 것: 검색·문맥·질의 사용량 기록(`purpose = 'query'`)·오늘 합계 성공. 거부: 예산이 충분한 값으로 부른 `embedding_reserve`(INSERT 분기까지 가게 해서 RLS 거부를
  확인), 직접 `purpose = 'index'` INSERT, 문서·청크·임베딩·인덱스 버전 쓰기·지우기, 사용량 기존 행 `UPDATE`·`DELETE`, daily 표 쓰기, 정산·정리 함수, `qk.sync_*` 읽기·쓰기, `CREATE`·`ALTER`.
  또 기존 색인 시험이 소유자 역할로 그대로 통과하는지(RLS가 소유자에 영향 없음) 확인한다.

### 0007 권한 대조 기록 (2026-10-26, T050)

0002·0005의 검색·문맥 함수와 0003·0006의 사용량 함수를 본문까지 대조했다. 모두 호출자 권한으로 실행한다.

| 경로 | 실제 표·보조 함수 | 0007 권한 |
| --- | --- | --- |
| 검색·문맥 | `index_version`, `artifact`, `chunk`; 벡터 검색은 `embedding`도 읽음. 위 검색 보조 함수 사용 | 네 표 SELECT, 위 검색·문맥 함수 EXECUTE |
| 질의 임베딩 기록·오늘 합계 | `embedding_usage` INSERT/SELECT, `embedding_utc_day()`, `embedding_amount(qk.embedding_usage)`, `embedding_used(date,text)` | INSERT/SELECT와 이 세 보조 함수 EXECUTE를 명시 |
| 생성 기록·오늘 합계 | `generation_usage` INSERT/SELECT, 위 임베딩 합계 보조 함수로 질의·색인 사용량도 읽음 | INSERT/SELECT, 생성 함수 EXECUTE와 위 보조 함수 권한 |
| 식별 열 기본값 | `embedding_usage_id_seq`, `generation_usage_id_seq` | 두 시퀀스 USAGE만. SELECT·UPDATE, 인덱스 표 시퀀스 권한 없음 |
| 일별 집계 | 오늘 합계 함수는 daily 표를 읽지 않음. daily 쓰기는 prune 함수에만 있음 | 승인된 집계 읽기 계약에 따라 두 daily 표 SELECT 유지, 쓰기 없음 |

대조 결과 빠진 표·시퀀스 권한이나 승인 목록 밖 추가 권한은 없다. 기존 목록의 "보조 함수"를 위 세 이름으로 구체화하고, 두 사용량 시퀀스의 USAGE를 확정했다.
확장 연산자·함수와 DB CONNECT는 기존 PUBLIC 권한을 사용하며 새 grant를 더하지 않는다. PUBLIC EXECUTE를 유지하므로 reserve·settle·prune에 대한 **명시적 grant가 없음**과
실행 자체의 허용 여부는 다르다. reserve의 index INSERT는 RLS, settle·prune은 표 변경 권한에서 막힌다. 운영에서 PUBLIC 기본 권한을 따로 거뒀다면 관리자와 재검토한다.
로컬 DB RED 뒤 0007을 작성했다. 2026-10-26 오케스트레이터가 역할 시험 40 passed와 전체 2,264 passed·2 deselected로 GREEN·기존 localdb 회귀를 확인했다. 운영 적용·운영 소유권 확인은 하지 않았다.
2026-10-26 오케스트레이터 확인: 로컬 supabase/postgres 17.11의 `postgres`는 `rolsuper=false`다. 표 소유자로 실행한 색인 쓰기·RLS 비강제 시험은 통과했다.
소유자가 마이그레이션 역할이면 슈퍼유저가 아니어도 위 RLS 우회 전제는 성립한다. H00에서는 운영 마이그레이션 역할의 속성과 실제 표 소유권을 함께 확인한다.
PG16+에서 역할 생성자의 ADMIN만으로 SET ROLE을 할 수는 없으므로 시험에만 임시 SET 멤버십을 부여하고 트랜잭션을 강제 롤백한다. 0007에는 멤버십 grant를 더하지 않는다.

## 5. 질의 작업과 실행

**`QueryJob`**: `run_id`(질의 실행 식별자, 질의 서비스가 만듦, `GenerationRequest.run_id`로 넘김), `interaction`(토큰·질문 포함, 메모리에만), `received_at`(단조 시계), `query_deadline`, `notice_deadline`.

**단계(상태 전이)**: `AWAITING_START → QUEUED → RETRIEVING → GENERATING → RENDERING → DELIVERING → DONE`.

- `AWAITING_START`에서 시작 확인 대기(`QK_QUERY_START_WAIT_SECONDS`)가 지나면 `NOT_STARTED → DELIVERING → DONE`. 검색·생성 없이 "요청을 처리하지 못했습니다…" 안내로 첫 메시지를 바꾸고
  전달이 끝나면 수명 자리를 반환한다(contracts/relay.md 3절).
- `QUEUED`·`RETRIEVING`·`GENERATING`·`RENDERING`에서 질의 마감에 닿거나, `QUEUED`에서 실행 자리를 잡을 때 남은 시간이 `QK_QUERY_MIN_START_SECONDS`보다 짧으면 `TIMED_OUT → DELIVERING → DONE`.
- 실패는 `FAILED(종류) → DELIVERING → DONE`.
- `DELIVERING`은 작업마다 한 번만 들어간다(전달 권한, research R-05). `DELIVERING`에서 전송이 끝까지 실패하면 `UNDELIVERED`(운영 로그만).
- 수명 자리(`QK_QUERY_WORKERS + QK_QUERY_QUEUE_SIZE`, 기본 6)는 `AWAITING_START`에서 잡고 `DONE`·`UNDELIVERED`에서 놓는다. 전달 중에도 쥔다(research R-05).
- 실행 자리(`QK_QUERY_WORKERS`)는 `RETRIEVING`에서 잡고, 검색·생성 호출이 실제로 끝날 때 놓는다. `TIMED_OUT`이 먼저 와도 호출이 끝날 때까지 쥔다.

**`QueryRunLog`** (운영 로그 한 줄, spec FR-021의 허용 항목만):

| 필드 | 예 |
| --- | --- |
| `run_id` | `q-20261025T140301-1a2b3c4d` |
| `access` | `allowed` |
| `private` | `false` |
| `status`, `failure` | `answer`, `null` |
| `timings_ms` | `{"first_response": 40, "retrieve": 900, "generate": 2100, "deliver": 300}` |
| `calls` | `{"retrieve": 3, "generate": 2, "deliver": 2}` |
| `deliver_retries`, `deliver_failure` | `0`, `null` |
| `retrieval_summary`, `generation_summary` | 기존 요약의 수치·이름 항목만 |

## 6. 표시

**`RenderedReply`**: `messages: tuple[str, ...]`(첫째가 처리 중 응답을 바꾸는 글), `ephemeral: bool`, `body_truncated: bool`, `allowed_mentions = {"parse": []}`.

- 안내 문구 표는 spec FR-011을 코드 상수 한 곳(`discord/notices.py`)에 둔다. 검색 실패 9종(`RetrievalFailure`)과 생성 실패 6종(`GenerationFailure`)의 대응을 빠짐없이 묶는 시험을 둔다.
- 출처 항목 꼴(본문 꼴): `[S1] <제목> · <URL> · 버전 <앞 7자> · 수정 2026-10-20 · 수집 2026-10-24 09:30 KST`. 서식 글자는 `\`로 바꾸고, URL은 `<…>`로 감싼다.

## 7. 중복 판정 상태

**`DedupEntry`**: `interaction_id`, `stage`(`IN_PROGRESS`, `DONE`), `expires_at`(받은 때 + 900초). 질의 서비스 메모리 안 사전, 조회할 때 만료 항목을 지운다. 잠금으로 동시 요청을 막는다.
