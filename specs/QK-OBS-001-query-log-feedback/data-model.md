# Data Model: QK-OBS-001

**Spec**: [spec.md](spec.md) | **Research**: [research.md](research.md)

## 1. 설정 (`config/registry.py`)

| 이름 | 진입점 | 형식·범위 | 기본 | 근거 |
| --- | --- | --- | --- | --- |
| `QK_QUERY_LOG_ENABLED` | query | `true`/`false` | `false` | spec FR-024, R-10 |
| `QK_QUERY_TEXT_RETAIN_UNTIL` | query, index | `YYYY-MM-DD` 또는 빈 값 | 빈 값 | FR-013 |
| `QK_QUERY_PENDING_SECONDS` | query | 정수 60~3600 | `3600` | FR-011 |
| `QK_QUERY_PENDING_MAX` | query | 정수 10~2000 | `500` | FR-011 |
| `QK_QUERY_RECORD_TIMEOUT_MS` | query | 정수 100~1500 | `1000` | FR-004 |
| `QK_DISCORD_COMPONENT_TIMEOUT_MS` | query | 정수 500~2000 | `1500` | FR-008, R-04(여유 200 + 최소 실행 100) |
| `QK_RELAY_TIMEOUT_SECONDS` | relay, **query(추가)** | 기존 규칙 0.5~2.8 | `2.5` | FR-008 교차 검사 |

교차 검사(`config/check.py`):

- `QK_QUERY_LOG_ENABLED=true`이고 `QK_QUERY_TEXT_RETAIN_UNTIL`이 비면 오류(FR-023).
- `QK_QUERY_TEXT_RETAIN_UNTIL` < 오늘(UTC)이면 경고 "원문 기록 보존 상한이 지났습니다. `qk-index queries erase-texts`를 확인하세요"(FR-013).
- `QK_DISCORD_COMPONENT_TIMEOUT_MS` ≥ `QK_RELAY_TIMEOUT_SECONDS` × 1000이면 오류(FR-008).
- `/sources` 줄 길이 상한(130자) × 등록 자료원 수 + 머리글 > 2,000이면 경고(R-11).

기록 기능이 꺼지면 기록·버튼·대기 설정은 검사만 하고 쓰지 않는다. `QK_DISCORD_COMPONENT_TIMEOUT_MS`는 `/sources` 때문에 꺼짐에서도 쓴다. 설정 추가 뒤 `.env.example`은 생성기(`uv run python -m qello_knowledge.config.example`)로 다시 만든다.

## 2. 도메인 타입 (`domain/discord.py`, `domain/query_log.py`)

### 2.1 상호작용 확장 (`domain/discord.py`)

- `InteractionKind`에 `COMPONENT = "component"`를 더한다. 명령 `sources`는 기존 `COMMAND`에 `command="sources"`로 담는다.
- `Interaction`에 `user_id: str | None = field(default=None, repr=False)`(서버 안 `member.user.id`)와 `component_action: str | None = None`, `component_run_id: str | None = None`을 더한다.
  기존 위치 인자 순서는 바꾸지 않는다(끝에 기본값 있는 필드로 추가).
- `RenderedReply`에 `components: tuple[Mapping, ...] = ()`를 더한다. 비어 있으면 지금 전송 본문과 같다.
- `QueryRunLog`에 `record: str = "off"`를 더한다(`stored`, `failed`, `timeout`, `off`).

### 2.2 질의 기록 (`domain/query_log.py`, 새 파일)

```text
QueryRecord(frozen)
  run_id: str                      # q-YYYYMMDDTHHMMSS-xxxxxxxx
  received_at: datetime (UTC)
  questioner_id: str | None        # repr=False
  private: bool
  status: RecordStatus
  failure: str | None              # QK-BOT-001 _safe_failure 허용 값만
  first_response_ms: int
  stage_ms: Mapping[str, int]      # retrieve, generate
  calls: Mapping[str, int]         # retrieve, generate
  retrieval: Mapping[str, number|bool]   # QueryRunLog.retrieval_summary와 같은 허용 키
  generation: Mapping[str, number|bool]  # QueryRunLog.generation_summary와 같은 허용 키
  input_tokens: int | None
  output_tokens: int | None
  context_chunk_ids: tuple[int, ...]
  context_block_sizes: tuple[int, ...]   # 묶음마다 청크 수, 합 = len(context_chunk_ids)
  cited_blocks: tuple[int, ...]          # 1부터, 인용한 묶음 순번
  index_version: str | None
  model_id: str | None
  prompt_version: str | None

QueryDelivery(frozen)
  run_id, final_status: RecordStatus | None, total_ms: int, deliver_ms: int, deliver_calls: int, deliver_retries: int, deliver_failure: str | None
  # final_status: 전달 실패면 undelivered(현재 `query/jobs.py:295-298`의 규칙과 같음), 성공이면 None(넣을 때 상태 유지)

RecordStatus(StrEnum)
  answered, cannot_confirm, retrieval_failed, generation_failed, outgoing_blocked,
  timed_out, not_started, failed, undelivered, busy

FeedbackValue(StrEnum): up, down
ComponentAction(StrEnum): up, down, keep, skip

PendingQuestion(frozen)
  run_id: str, questioner_id: str (repr=False), question: str | None (repr=False), state: waiting | claimed | uncertain | chosen, expires_at: float

SourceSummary(frozen)
  name: str, kind: str, documents: int, last_seen_at: datetime
SourcesView(frozen)
  index_version: str | None, activated_at: datetime | None, sources: tuple[SourceSummary, ...]
```

상태 대응(spec FR-002): `answered`·`cannot_confirm`·`retrieval_failed`·`generation_failed`·`outgoing_blocked`는 생성 결과 상태 값 그대로(`GenerationStatus`). `timed_out`·`not_started`·`failed`·
`undelivered`는 `QueryStage` 값. `busy`는 대기열 가득(`query/app.py:84`). 질의 시작 전 비밀값 차단(`query/app.py:79-81`)도 `outgoing_blocked`다. `duplicate`·`access_denied`·`unsupported`는 기록하지 않는다.

### 2.3 포트 (`ports/query_log.py`, 새 파일)

```text
QueryLog(Protocol)
  insert(record: QueryRecord) -> None
  delivered(delivery: QueryDelivery) -> None
  feedback(run_id: str, rater_id: str, value: FeedbackValue) -> FeedbackResult   # stored | missing
  store_question(run_id: str, questioner_id: str, question: str) -> TextResult  # stored | exists | missing | not_questioner
  mark_text_skipped(run_id: str) -> None
  question_status(run_id: str, questioner_id: str) -> TextStatus  # stored | none | missing | not_questioner
  sources() -> SourcesView
```

어댑터 `adapters/postgres/query_log.py`가 3절 함수를 부른다. 기록기(`query/recorder.py`)는 이 포트를 길마다 작업 스레드 하나(켜짐에서 앞·뒤 길 둘, 꺼짐에서 앞 길 하나)에서 부르고, 호출자에게 상한 대기 결과(`ok`, `failed`, `timeout`)를 돌려준다.

## 3. 저장 구조 (`0008_query_log.sql`)

### 3.1 표

```text
qk.query_record
  run_id text PRIMARY KEY CHECK (run_id ~ '^q-[0-9]{8}T[0-9]{6}-[0-9a-f]{8}$')
  received_at timestamptz NOT NULL
  questioner_id text CHECK (questioner_id ~ '^[0-9]{17,20}$')     -- 지우기 뒤 NULL
  private boolean NOT NULL
  status text NOT NULL CHECK (status IN (...RecordStatus...))
  failure text
  first_response_ms int NOT NULL CHECK (>= 0)
  total_ms int CHECK (>= 0)                                         -- 전달 뒤 갱신
  stage_ms jsonb NOT NULL DEFAULT '{}'   -- 숫자 값만(CHECK: jsonb 값 종류)
  calls jsonb NOT NULL DEFAULT '{}'
  retrieval jsonb NOT NULL DEFAULT '{}'
  generation jsonb NOT NULL DEFAULT '{}'
  input_tokens int, output_tokens int
  context_chunk_ids bigint[] NOT NULL DEFAULT '{}'
  context_block_sizes int[] NOT NULL DEFAULT '{}'
  cited_blocks int[] NOT NULL DEFAULT '{}'
  index_version text, model_id text, prompt_version text
  deliver_ms int, deliver_calls int, deliver_retries int, deliver_failure text
  consented boolean NOT NULL DEFAULT false
  text_skipped boolean NOT NULL DEFAULT false                       -- 저장 직전 비밀값 검사(FR-012)
  INDEX (received_at)

qk.query_feedback
  run_id text NOT NULL REFERENCES qk.query_record(run_id)
  rater_id text CHECK (rater_id ~ '^[0-9]{17,20}$')                -- 지우기 뒤 NULL
  value text NOT NULL CHECK (value IN ('up', 'down'))
  first_at timestamptz NOT NULL DEFAULT now(), last_at timestamptz NOT NULL DEFAULT now()
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY
  UNIQUE (run_id, rater_id)        -- NULL 평가자는 여럿 허용(지우기 뒤 옛 평가, spec Edge Cases)

qk.query_text
  run_id text PRIMARY KEY REFERENCES qk.query_record(run_id)
  question text NOT NULL CHECK (char_length(question) BETWEEN 1 AND 4000)
  consented_at timestamptz NOT NULL DEFAULT now()
  consent_method text NOT NULL CHECK (consent_method = 'feedback_down')

qk.query_erasure_run
  id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY
  ran_at timestamptz NOT NULL DEFAULT now()
  kind text NOT NULL CHECK (kind IN ('user', 'all_texts'))
  texts_deleted int NOT NULL, records_cleared int NOT NULL, feedback_cleared int NOT NULL
```

답변 본문·출처·채널·서버·이름 열은 없다(spec FR-002·FR-011). 색인 표 외래 키는 없다(R-05). 원문 기록에 보존 만료 열을 두지 않는다. 보존 상한은 설정 하나이고 자동 삭제가 없다(FR-013).

### 3.2 함수와 권한

| 함수 | 보안 | 하는 일 | 질의 역할 |
| --- | --- | --- | --- |
| `qk.query_record_insert(jsonb)` | DEFINER | 기록 넣기. 같은 `run_id`가 있으면 아무것도 하지 않음(재시도 안전) | 실행 |
| `qk.query_record_delivered(text, jsonb)` | DEFINER | 전달 결과 항목 갱신. `final_status = 'undelivered'`면 상태도 바꾼다(다른 값은 무시) | 실행 |
| `qk.query_feedback_set(text, text, text) → text` | DEFINER | 기록 없으면 `missing`. 있으면 (run, rater) 넣기·바꾸기 → `stored` | 실행 |
| `qk.query_text_store(text, text, text) → text` | DEFINER | 기록 없음 `missing`, 질문자 불일치 `not_questioner`, 이미 있음 `exists`, 아니면 넣고 `consented=true` → `stored` | 실행 |
| `qk.query_text_skip(text)` | DEFINER | `text_skipped=true` | 실행 |
| `qk.query_text_status(text, text) → text` | DEFINER | 기록 없음 `missing`, 질문자 불일치 `not_questioner`, 원문 있음 `stored`, 없음 `none`. 원문 내용은 돌려주지 않는다 | 실행 |
| `qk.sources_summary() → jsonb` | INVOKER | R-11 조회 | 실행 |

- DEFINER 함수: `SET search_path = qk, pg_temp`, 같은 마이그레이션 트랜잭션 안에서 `CREATE` → `REVOKE ALL ON FUNCTION … FROM PUBLIC` → `GRANT EXECUTE … TO qk_query`.
  마이그레이션 시험이 함수 소유자(마이그레이션 역할), `prosecdef`, `proconfig`의 `search_path`, `PUBLIC` 실행 권한 없음, `qk_query`의 `qk` 스키마 `CREATE` 권한 없음을 확인한다.
- 입력 `jsonb`는 알려진 키만 꺼내 열을 다시 만든다(모르는 키 무시). 중첩 객체(`stage_ms`, `calls`, `retrieval`, `generation`)는 키마다 허용 목록과 값 형식이 정해져 있다.
  `stage_ms`: `retrieve`·`generate` 정수 ≥ 0. `calls`: `retrieve`·`generate` 정수 ≥ 0. `retrieval`: `external_calls` 정수, `neurons`·`estimated_neurons` 수, `measured` 참·거짓.
  `generation`: `generation_calls`·`attempts` 정수, `neurons` 수, `measured` 참·거짓(지금 `query/jobs.py:35-46` `_numbers`의 이름과 같음). 목록 밖 키와 형식이 틀린 값은 버린다.
  `failure`·`index_version`·`model_id`·`prompt_version`은 길이 상한(64자)과 문자 집합(`[A-Za-z0-9@/._:+-]`)을 검사하고 맞지 않으면 NULL이다.
- 질의 역할에는 네 표의 어떤 권한도 주지 않는다. 관리 역할(소유자)은 표를 직접 읽고 지운다(집계·내보내기·지우기).
- 기존 객체(0001~0007)는 바꾸지 않는다.

### 3.3 지우기 (관리 연결, 한 트랜잭션)

- 사용자: `DELETE FROM qk.query_text USING qk.query_record r WHERE r.run_id = query_text.run_id AND r.questioner_id = $1` → `UPDATE qk.query_record SET questioner_id = NULL WHERE questioner_id = $1`
  → `UPDATE qk.query_feedback SET rater_id = NULL WHERE rater_id = $1` → `qk.query_erasure_run` 한 줄. 확인 인자가 없으면 같은 조건의 `count`만.
- 전체 원문: `DELETE FROM qk.query_text` → 실행 기록 한 줄.

## 4. 질의 서비스 상태

| 상태 | 위치 | 수명 | 담는 것 |
| --- | --- | --- | --- |
| 원문 대기(`PendingQuestions`) | 질의 서비스 메모리 | 1시간, 500건, 재시작 시 사라짐 | 질문자 식별자, 질문(선택 전까지), 선택 여부 |
| 기록기 연결 | 질의 서비스 | 프로세스 수명, 실패 시 다시 연결 | 길마다 저장소 연결 하나(질의 역할) |
| 중복 판정(기존) | 질의 서비스 메모리 | 15분 | 바꾸지 않음 |

원문 대기 넣기: 작업 결과가 `answered`·`cannot_confirm`이고, 기록 기능이 켜졌고, 보존 상한 날짜가 오늘 이후이고, 질문자 식별자가 있을 때(`_claim`에서).
상태 전이는 research R-07: `waiting`·`uncertain` → (질문자의 `keep`/`skip` 선점) `claimed` → `chosen`(결과 확정, 질문 지움) 또는 `uncertain`(저장·조회 결과 불명, 질문 유지). `chosen`·없음에서는 선점 없이 조회만 한다(contracts 2절 13행). 만료 정리는 접근 때와 감시 스레드 주기마다, 종료 때 전부.

| 상태 | 위치 | 비고 |
| --- | --- | --- |
| 기록기 앞 길 | 작업 스레드 1 + 연결 1 | 버튼·`/sources`. 기록 기능 꺼짐에서도 `/sources`용으로 만든다(조회만) |
| 기록기 뒤 길 | 작업 스레드 1 + 연결 1 | `/ask` 기록. 기록 기능이 꺼지면 만들지 않는다 |

## 5. 버튼·응답 꼴

contracts/discord-components.md에 있다.
