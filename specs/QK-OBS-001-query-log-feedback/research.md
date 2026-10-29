# Research: QK-OBS-001 질의 로그, 👍/👎 피드백, `/sources`, 질의 원문 저장 옵션

**Date**: 2026-10-29 | **Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

조사 방법: 이 저장소 코드 읽기(줄 번호는 `origin/main` `81b974c` 기준), Discord 공식 개발자 문서 두 쪽 조회(2026-10-29). 실제 Discord·Workers AI·운영 저장소 호출은 0건이다.
"확인"은 문서나 코드로 본 것, "추론"은 확인하지 않은 판단이다.

## R-01 Discord 버튼 상호작용의 꼴

- **Decision**: 버튼은 상호작용 종류 3(`MESSAGE_COMPONENT`)으로 받는다. 응답은 질문자만 보는 새 메시지(콜백 4 + `flags: 64`)와, 동의 질문 메시지를 고치는 콜백 7(`UPDATE_MESSAGE`)만 쓴다.
  누른 사람 식별자는 `member.user.id`(서버 안 상호작용)에서 읽는다. 버튼은 액션 줄(종류 1) 하나에 버튼(종류 2) 둘이다.
- **Rationale**:
  - 확인(https://docs.discord.com/developers/interactions/receiving-and-responding, 2026-10-29): 상호작용 종류 1 PING, 2 APPLICATION_COMMAND, 3 MESSAGE_COMPONENT. 콜백 4·5·6·7이 있고
    6(`DEFERRED_UPDATE_MESSAGE`)·7(`UPDATE_MESSAGE`)은 컴포넌트·모달 상호작용에만 쓸 수 있다. `member`는 서버 안 상호작용에, `user`는 DM에만 온다. 컴포넌트 상호작용에는 버튼이 붙은
    `message`가 실려 온다. 첫 응답은 3초 안, 토큰은 15분 유효.
  - 확인(https://docs.discord.com/developers/components/reference, 2026-10-29): 액션 줄 1, 버튼 2, 스타일 Secondary 2. `custom_id`는 1~100자이고 같은 메시지 안에서 겹치면 안 된다.
    클릭 상호작용의 `data`에 `component_type`·`custom_id`가 온다. 컴포넌트는 "메시지를 만들거나 상호작용에 응답할 때" 쓸 수 있다.
  - 확인(코드): 지금 해석기는 종류 2의 `ask`만 받고 나머지는 `OTHER`로 둔다(`discord/interactions.py:30-38`). `Interaction`에 사용자 식별자가 없다(`domain/discord.py:56-66`).
  - 버튼 응답 안에서 저장소를 부르므로 지연 응답(콜백 5·6)을 쓰면 3초 안 처리를 미루고 후속 요청이 필요해진다. 저장소 호출은 수십 ms라(추론) 콜백 4·7 안에서 끝낸다(spec FR-008).
- **미확인**: 질문자만 보는 메시지에 버튼을 달고 그 메시지를 콜백 7로 고칠 수 있는지는 문서에 없다. 일반 설명으로는 된다(추론). 안 되면 두 번째 누름은 "이미 선택했습니다."로 끝나므로
  기능은 유지된다(spec FR-011 마지막 항목). 사람 단계 M-02에서 화면으로 확인한다.
- **Alternatives considered**: 콜백 6 + 후속 메시지(저장소가 느려도 3초를 넘지 않음. 하지만 Worker 시작 확인 경로를 버튼에도 만들어야 하고 호출이 늘어난다), `user` 필드에서 식별자 읽기(서버 안에서는 오지 않음).

## R-02 버튼 값(`custom_id`) 형식

- **Decision**: `qk1:<동작>:<질의 실행 식별자>`. 동작은 `up`(👍), `down`(👎), `keep`(저장 동의), `skip`(저장 안 함). 질의 실행 식별자는 지금 형식 `q-YYYYMMDDTHHMMSS-<16진 8자>`
  (`query/jobs.py:184`)만 받는다. 전체 정규식 `^qk1:(up|down|keep|skip):q-[0-9]{8}T[0-9]{6}-[0-9a-f]{8}$`(최대 35자). 맞지 않으면 spec FR-009 안내.
- **Rationale**: spec FR-009(질의 실행 식별자와 동작만). 접두사 `qk1`은 형식이 바뀔 때 옛 버튼을 가려내는 버전이다. 평가자·질문자는 `custom_id`가 아니라 `member.user.id`로 판정해
  버튼 값을 조작해도 남의 이름으로 저장되지 않는다(spec 독립 검토 3절 확인 사항).
- **Alternatives considered**: 서명된 토큰(HMAC)을 값에 넣기(위조 방지. 하지만 값은 Discord가 서명한 요청 안에서만 오고, 바꿔도 남의 평가자 식별자를 만들 수 없어 얻는 것이 없다).

## R-03 답변 메시지에 버튼 달기

- **Decision**: `RenderedReply`에 선택 항목 `components`(마지막 메시지에 붙일 액션 줄 목록, 기본 빈 값)를 더한다. 질의 작업이 결과 상태 `answered`·`cannot_confirm`이고 기록 기능이 켜졌을 때만
  채운다. `DiscordWebhook.deliver`는 마지막 메시지 본문에 `components`를 넣는다(`adapters/discord/webhook.py:224`의 `body`). 메시지가 하나면 `@original` PATCH에 넣는다.
- **Rationale**: 컴포넌트는 본문 글자 수(2,000자)에 들어가지 않아 FR-012 분할 계산이 그대로다(spec FR-006). `render`(`discord/render.py:211`)는 바꾸지 않고, 작업 경계(`query/jobs.py` `_claim`)가
  결과 상태를 보고 붙인다. 그래서 QK-BOT-001 렌더링 시험 기대값이 바뀌지 않는다.
- **Alternatives considered**: `render`에 버튼 인자 추가(렌더링 시험 기대값과 서명이 바뀜), 버튼만 따로 후속 메시지로 보내기(메시지 수 상한 계산이 바뀜).

## R-04 질의 기록을 언제 어떻게 넣나

- **Decision**: 질의 서비스에 기록기(`QueryRecorder`)를 하나 둔다. 길(lane) 둘을 가지며 길마다 작업 스레드 하나와 저장소 연결 하나다.
  - **뒤 길**(`/ask` 기록): `_send`(`query/jobs.py:277`)가 전달 전에 `insert(record)`를 내고 최대 `QK_QUERY_RECORD_TIMEOUT_MS`(기본 1,000 ms)만 기다린다. 넘거나 실패하면 기다리지 않고 보낸다.
    전달이 끝나면 `delivered(…)`를 기다리지 않고 낸다(spec FR-004). 첫 응답에서 끝나는 `/ask`(비밀값 차단, 대기열 가득, 예상 밖 실패. `query/app.py:73-91`)도 기다리지 않고 낸다.
    뒤 길의 넣기는 같은 `run_id`가 있으면 아무것도 하지 않으므로, 늦게 실행돼도 중복이 없다.
  - **앞 길**(버튼·`/sources`): 요청마다 절대 마감(받은 때 + `QK_DISCORD_COMPONENT_TIMEOUT_MS`, 기본 1,500 ms)을 함께 넣는다. 작업 스레드는 꺼낸 작업의 남은 시간이 여유(200 ms) + 최소 실행 예산(100 ms)
    이하면 실행하지 않고 버린다(대기열 적체로 늦게 시작하지 않음, 문장 제한이 0 이하가 되지 않음). 실행할 때는 설정 왕복 뒤 남은 시간으로 그 문장의 `statement_timeout`(남은 시간 − 여유, ≥ 100 ms)을 다시 맞추고, 자동 커밋 모드에서 함수 호출 한 문장으로 실행한다. 마감 − 여유 시점에
    클라이언트가 취소를 **요청**하고, 호출자는 마감까지만 기다린다. 취소 요청은 서버 쪽 취소 완료 시각을 보장하지 않으므로(psycopg `cancel_safe` 설명), 보장하는 것은 "함수 한 문장이라 부분 저장이 없고,
    마감까지 결과가 오지 않으면 결과 불명으로 답한다"뿐이다. 문장이 결국 커밋됐는지는 다음 누름의 함수 결과(`exists`, 같은 값 갱신)나 `question_status`로 확인한다(2026-10-29 사용자 결정, 구현 재검토 M1).
    취소가 발동한 연결은 버리고 다음 작업에서 새로 연결한다. 뒤 길이 막혀도 버튼이 기다리지 않는다.
  - 결과 불명: 버린 작업, 상한 초과, 연결 실패는 저장 여부를 모르는 것으로 보고 "저장 여부를 확인하지 못했습니다. 다시 눌러 주세요."로 답한다(spec FR-008·SC-004, 2026-10-29 변경). 문장이 마감 − 여유 직전에 커밋되고 반환만 늦은
    경우도 여기에 든다. 평가 함수는 같은 값으로 다시 갱신하고 동의 함수는 `exists`를 돌려주므로, 다시 누르면 결과에 맞는 안내가 나오고 행은 하나다. 동의 결과가 불명이면 원문 대기의 질문을 지우지 않고
    상태를 `uncertain`으로 두어 다시 누를 수 있게 한다(R-07). 시험: 지연 주입(취소 요청이 마감 − 여유 시각에 나감, 호출자가 마감 안에 결과 불명을 받음, 롤백되어 저장 0건, 다음 요청이 새 연결로 성공), 커밋 뒤 반환 지연 주입(저장 1건 + 불명 안내 → 다시 누름 → 맞는 안내, 행 하나).
  - 연결은 `connect_timeout`을 걸고, 실패하면 다음 작업에서 다시 연결한다. 연결 실패·제약 위반 예외는 종류 이름(`unavailable`, `timeout`, `rejected`)으로만 바꿔 올리고 예외 문구를 버린다(R-14).
- **Rationale**:
  - 확인(코드): 지금 실행 기록(`QueryRunLog`)은 전달이 끝난 뒤 만들어진다(`query/jobs.py:295-316`). 그대로 저장하면 답을 받자마자 누른 버튼이 기록을 못 찾는다(spec 독립 검토 M1).
  - 질의 파이프라인의 저장소 연결은 작업마다 열고 닫는다(`query/pipeline.py:139-178, 297-306`). 기록은 작업 수명 밖(버튼은 몇 시간 뒤)에도 필요해 따로 둔다.
  - 기록 넣기는 수 ms이고 1초 상한은 안내 전달 마감(60초)에 비해 작다(추론, 로컬 시험으로 확인).
- **Alternatives considered**: 작업마다 새 연결(버튼 경로의 연결 비용이 첫 응답 상한을 잡아먹음), 파일에 쌓았다가 일괄 넣기(버튼 즉시 조회와 맞지 않음, 원문이 파일로 나갈 위험).

## R-05 저장 구조와 권한

- **Decision**: 마이그레이션 `0008_query_log.sql`로 표 넷과 함수를 더한다(data-model 3절).
  - 표: `qk.query_record`, `qk.query_feedback`, `qk.query_text`, `qk.query_erasure_run`. 색인 표를 참조하지 않는다(외래 키 없음. 청크 식별자는 숫자 배열로만 둔다).
  - 질의 역할 `qk_query`에는 네 표의 직접 권한을 주지 않는다. `SECURITY DEFINER` 함수(소유자 = 마이그레이션 역할, `SET search_path = qk, pg_temp`, `PUBLIC` 실행 권한 회수)
    여섯 개의 실행 권한만 준다: 기록 넣기, 전달 결과 갱신, 평가 넣기·바꾸기, 동의 원문 넣기, 원문 저장 생략 표시, 질문자 본인 질의의 원문 유무 확인. `/sources` 조회 함수는 `SECURITY INVOKER`(질의 역할이 이미 `artifact`·
    `index_version`을 읽을 수 있다, `0007_query_role.sql:11`).
  - 동의 원문 넣기 함수는 질의 기록의 질문자 식별자와 넘겨받은 식별자가 같을 때만 넣는다(질의 서비스 판정과 이중 확인).
  - 지우기·집계·내보내기는 관리 연결(마이그레이션·색인 역할)로 표를 직접 읽고 쓴다. 질의 역할에는 그 권한이 없다(spec FR-005·FR-015).
- **Rationale**:
  - 확인(코드): `qk_query`는 지금 사용량 표 넣기와 검색 표 읽기만 있다(`0007_query_role.sql:11-15`). 평가 바꾸기(`ON CONFLICT DO UPDATE`)는 대상 열 읽기 권한을 요구하므로, 표 권한으로 주면
    질의 기록 전체(질문자 식별자 목록)를 읽을 수 있게 된다. 함수로 감싸면 spec FR-005의 "좁은 함수로만 조회"를 지킨다.
  - 이 저장소에서 `SECURITY DEFINER`는 처음이다(`grep` 확인, 0001~0007에 없음). PostgreSQL 공식 권고(`search_path` 고정, `PUBLIC` 실행 회수)를 따른다(추론: 문서는 이번에 조회하지 않았다.
    plan 승인 전 사람 확인 대상).
- **Alternatives considered**: 표 권한 + RLS(질의 역할의 SELECT 정책을 "자기 행"으로 좁힐 기준이 없다), 질의 서비스가 관리 연결을 쓰기(BOT-001 FR-019 최소 권한 위반).

## R-06 근거 청크와 인용 기록

- **Decision**: 질의 기록에 (1) 검색 Context 묶음 순서대로의 청크 식별자 배열, (2) 묶음 경계(묶음마다 청크 수), (3) 답변이 인용한 묶음 순번(1부터) 배열, (4) 검색 요약의 인덱스 버전,
  (5) 생성 요약의 모델·프롬프트 버전·입출력 토큰을 넣는다. 출처 식별자(`Citation.source_id`, 경로 꼴)와 제목·링크는 넣지 않는다.
- **Rationale**: 확인(코드): `ContextBlock.chunks[].chunk_id`(`domain/retrieval.py:146-160`), `RetrievalSummary.index_version`(`:208`), `GenerationSummary.model_id·prompt_version·input_tokens·output_tokens`
  (`domain/generation.py:225-250`), `GenerationResult.citations`(`Citation.source_id`, `:195-201`). 저장소 경로(`docs/...md`)는 사실상 문서 제목이라 spec FR-002의 "출처 제목"에 가깝다.
  인용은 Context 묶음 순번으로 바꿔 경로를 남기지 않는다. 생성 단계에서 빠진 묶음 수는 생성 요약(`dropped`)에 이미 있다.
- **Alternatives considered**: 문서(artifact) 식별자만 남기기(청크 단위 실패 분석이 안 됨), 인용 경로 그대로(제목 노출).

## R-07 원문 대기

- **Decision**: 질의 서비스 메모리의 `PendingQuestions`(질의 실행 식별자 → 질문자 식별자, 질문, 상태, 만료 시각). 잠금 하나, 상한을 넘으면 만료가 가장 이른 것부터 버린다.
  - 만료 정리는 접근할 때와, 기존 감시 스레드(`QueryJobs._watch`)의 주기 실행에서 한다(요청이 없어도 만료 뒤 감시 주기 안에 질문 참조를 지운다). 종료(`QueryJobs.close`) 때 전부 지운다.
  - 상태: `waiting`(질문 있음, 미선택) → `claimed`(선택 처리 중, 잠금 안에서 한 요청만 선점) → `chosen`(결과 확정, 질문 `None`) 또는 `uncertain`(저장 결과 불명, 질문 유지).
    `claim`은 누른 사람 = 질문자, 상태 `waiting`·`uncertain`, 만료 전, 보존 상한 날짜 ≥ 오늘(UTC)일 때만 선점한다. `claimed` 중 다른 누름은 결과 불명 안내로 끝난다(경합에서 하나만 처리).
    `uncertain`에서 `keep`은 저장을 다시 시도하고(함수가 `exists`를 돌려주므로 행은 하나), `skip`과, 대기가 `chosen`이거나 없을 때의 누름은 좁은 함수 `qk.query_text_status`로 질문자 본인 질의의
    원문 기록 유무를 확인해 안내한다(contracts 2절 13행). 그래서 결과 불명 뒤 어떤 경로에서도 "저장하지 않았습니다"를 단정하지 않는다. 날짜가 지난 뒤 누른 `keep`은 대기 없음과 같다.
  질문은 `repr=False`로 두고 어떤 로그·예외 문구에도 넣지 않는다. 운영 단위 파일에 `LimitCORE=0`을 더하고, 인스턴스 스왑 여부를 운영 문서에 확인 항목으로 둔다.
- **Rationale**: spec FR-011(1시간, 500건, 질문만). 확인(코드): 질의 작업은 이미 질문을 메모리에 들고 있다(`Interaction.question`, `domain/discord.py:61`). 중복 판정 상태도 메모리다
  (`query/jobs.py:124`, QK-BOT-001 R-10). 1시간·500건 × 질문 최대 2,000자 ≈ 최대 약 3 MB(추론).
- **Alternatives considered**: 저장소에 짧게 두기(동의 없는 저장, spec 결정과 다름), 질문을 버튼 상호작용의 `message`에서 다시 얻기(답변 메시지에 질문이 없다. 슬래시 명령 인자는 메시지 본문이 아니다. 추론).

## R-08 버튼·`/sources` 처리 흐름과 첫 응답 상한

- **Decision**: `DiscordApp.respond`(`query/app.py:48`)에 종류 분기를 더한다. 서명 검사 → 해석 → 허용 범위(같은 `AccessPolicy`) → 처리. 버튼: 값 검사 → 기록기 호출(상한 안 대기) → 응답.
  `/sources`: 기록기 연결로 조회 함수 호출(상한 안 대기) → 응답. 상한은 `QK_DISCORD_COMPONENT_TIMEOUT_MS`(기본 1,500, 범위 500~2,000)이고 설정 검사가 `QK_RELAY_TIMEOUT_SECONDS`×1000보다 작은지
  본다. 그래서 질의 설정에도 `QK_RELAY_TIMEOUT_SECONDS`(선택, 기본 2.5)를 읽게 한다.
- **Rationale**: spec FR-008. 확인(코드): 중계 Worker의 첫 응답 제한은 2.5초(`workers/relay/index.ts:8`, `wrangler.toml` `QK_RELAY_TIMEOUT_SECONDS`). 시작 확인 경로(`/start`)는 `/ask` 작업에만 쓰고
  버튼·`/sources`는 쓰지 않는다(콜백 5를 돌려주지 않으므로 Worker가 시작 확인을 보내지 않는다, `relay.ts:68-71`).
- **Alternatives considered**: `/sources`를 미리 계산해 캐시(동기화 직후 값이 늦음. 하루 수십 건이라 이득 없음).

## R-09 중계 Worker 변경

- **Decision**: (1) 콜백 7은 원본 상호작용이 종류 3(컴포넌트)일 때만 허용한다(`relay.ts:68`). `/ask`(종류 2)에는 지금처럼 1·4·5만. (2) 대체 응답 문구는 원본이 종류 3이거나 종류 2이면서
  `data.name == "sources"`일 때만 "지금은 처리할 수 없습니다. 잠시 후 다시 시도해 주세요."이고, 그 밖(이름 없는 종류 2 포함)은 지금 문구다(`relay.ts:45-53`). 서명 검사·크기 제한·호출 수는 그대로다.
  확인(코드): 기존 시험은 종류 2 원본에 콜백 7이면 대체 응답(`relay.test.ts:61`), 이름 없는 종류 2의 실패·시간 초과에 지금 문구(`:224-241`)를 기대한다. 위 규칙이면 두 시험은 그대로 통과하고
  새 사례만 더한다.
- **Rationale**: spec FR-010. 확인(코드): Worker는 PING이 아닌 요청을 모두 넘긴다(`relay.ts:60-62`). 콜백 7은 지금 허용 목록 밖이라 대체 응답으로 바뀐다(spec 독립 검토 M2).
- **Alternatives considered**: 모든 콜백 종류 허용(질의 서비스 버그가 그대로 Discord로 나감. 목록은 좁게 둔다).

## R-10 기록 기능 켜짐과 보존 상한 날짜

- **Decision**: 질의 설정에 `QK_QUERY_LOG_ENABLED`(`true`/`false`, 기본 `false`), `QK_QUERY_TEXT_RETAIN_UNTIL`(`YYYY-MM-DD`, 선택), `QK_QUERY_PENDING_SECONDS`(60~3,600, 기본 3,600),
  `QK_QUERY_PENDING_MAX`(10~2,000, 기본 500), `QK_QUERY_RECORD_TIMEOUT_MS`(100~1,500, 기본 1,000), `QK_DISCORD_COMPONENT_TIMEOUT_MS`(500~2,000, 기본 1,500. 하한 500은 여유 200 + 최소 실행 예산 100에 해석·응답 시간을 더한 값)를 더한다.
  교차 검사: 켜짐인데 날짜가 비면 오류, 날짜가 오늘(UTC)보다 이르면 경고, 첫 응답 상한 ≥ 중계 제한이면 오류. 색인 설정에도 `QK_QUERY_TEXT_RETAIN_UNTIL`을 읽게 해 집계 보고가 경고한다.
- **Rationale**: spec FR-013·FR-023·FR-024. 확인(코드): 설정은 `config/registry.py`의 `SettingSpec`과 진입점 집합으로 등록하고(`:16-23`, `:238-249`), `.env.example`은 생성기로 다시 만든다.
  날짜는 사람이 읽기 쉬운 날 단위다. 시간대는 UTC로 판정한다(사용량 하루 경계와 같음, `0006_generation_usage.sql:8`).
- **Alternatives considered**: 기본 켜짐(공지 전에 식별자가 쌓임, spec FR-024 위반), 기능별 개별 스위치(파일럿에 필요 없음).

## R-11 `/sources` 조회

- **Decision**: 함수 `qk.sources_summary()`가 활성 인덱스 버전(식별자, 활성화 시각)과, 그 버전의 보이는 청크(`qk.is_visible`)가 있는 문서를 자료원(`artifact.source_name`, 없으면 `source_kind`)별로
  묶어 (종류, 보이는 문서 수, 마지막 수집 시각 = `max(coalesce(last_seen_at, collected_at))`)를 돌려준다. 자료원 이름순. 동기화 기록 표는 읽지 않는다.
- **Rationale**: spec FR-016은 "마지막 수집 시각" 출처를 계획 단계에 맡겼다. 확인(코드): `last_seen_at`은 동기화가 목록에서 문서를 다시 볼 때마다 갱신된다(`adapters/postgres/sync_store.py:204`).
  `collected_at`은 본문을 다시 받을 때 바뀐다. 바뀌지 않은 문서도 "언제 기준으로 확인했나"를 보이려면 `last_seen_at`이 맞다. 동기화 기록(`qk.sync_run`)을 읽으면 질의 역할 권한이 늘어난다.
  응답 한 줄은 약 120자(추론)라 2,000자 메시지에 자료원 약 15개가 들어간다. 지금 등록 자료원은 4개(활성 1)다(`qk-index sources check`, TASK.md 2026-10-28 기록). 설정 검사는 등록 자료원 수 × 줄 상한이
  메시지 한도를 넘으면 경고하고, 넘는 경우 응답은 앞에서부터 자르고 "(N개 더 있음)" 줄을 붙인다(spec FR-017, 2026-10-29 plan 검토 M1에서 사용자가 spec을 이 규칙으로 바꿈).
- **Alternatives considered**: 마지막 성공 동기화 시각(권한 추가, 자료원 단위 성공 판정이 부분 성공에서 모호), 후속 메시지로 나누기(첫 응답 뒤 토큰 전송 경로가 필요).

## R-12 운영 명령

- **Decision**: `qk-index queries` 하위 명령 넷. 모두 관리 연결(`DATABASE_URL`, 색인 진입점)을 쓴다(contracts/cli.md).
  - `report --since --until [--json]`: 집계 보고(spec FR-018).
  - `export --out <파일> [--all]`: 기본은 👎가 있는 원문 기록만. 출력 경로가 저장소 작업 트리 안이면 거부한다. 파일 권한 `0600`, JSON Lines.
  - `erase-user [--confirm]`: Discord 사용자 식별자를 표준 입력으로 받는다(셸 이력·프로세스 목록에 남지 않게). 확인 인자 없으면 건수만.
  - `erase-texts [--confirm]`: 원문 기록 전체 삭제(spec FR-013).
- **Rationale**: 확인(코드): 운영 조회 명령은 `qk-index` 아래에 있다(`indexer/cli.py:51-66`, `runs list`, `usage`). 질의 서비스(`qk-query`)는 질의 역할만 가진다.
- **Alternatives considered**: `qk-query` 아래(질의 역할로는 읽을 수 없다), Discord 명령으로 삭제(권한 판정이 필요해 범위가 커짐).

## R-13 지연 측정 경계

- **Decision**: 질의 기록의 시간은 질의 서비스 단조 시계로 잰다. `first_response_ms`(요청 받음 → 첫 응답 결정, `query/app.py:49, 116`), `total_ms`(요청 받음 → 전달 끝). 집계 보고는 두 값의
  p50·p95(`percentile_cont`)를 내고 측정 경계를 문구로 붙인다. Worker 대체 응답 건수는 Workers 로그의 `relay_failed` 줄로 센다고 안내한다.
- **Rationale**: spec FR-018, 독립 검토 M7. 확인(코드): Worker는 `relayed`·`relay_failed`와 경과 시간만 남긴다(`workers/relay/index.ts:127-130`).

## R-14 실행 기록(운영 로그) 변경

- **Decision**: `QueryRunLog`에 `record` 항목(`stored`, `failed`, `timeout`, `off`) 하나를 더한다. 기록기·어댑터의 예외는 종류 이름으로만 바꾸고(R-04), 저장소 오류 문구(제약 위반 문구에는 입력 값이
  들어갈 수 있다)를 운영 로그·CLI 오류로 내보내지 않는다. 실패 주입 시험으로 확인한다. 버튼·`/sources`는 운영 로그 한 줄(종류, 동작, 결과, 경과 ms)만 남기고 식별자는 남기지 않는다.
- **Rationale**: spec FR-004("운영 로그에 실패 종류만"). QK-BOT-001 FR-021 허용 항목의 범위 안(상태 이름)이다. 확인(코드): `QueryRunLog.to_json`(`domain/discord.py:151-157`), 시험 `tests/unit/query/test_bot_no_raw_logs.py`.

## R-15 기록 기능 꺼짐에서의 불변

- **Decision**: 꺼짐이면 기록기 뒤 길을 만들지 않고(앞 길은 `/sources` 조회용으로만 만든다), 버튼을 달지 않고, 원문 대기에 넣지 않는다. 버튼 상호작용이 오면(켰다가 끈 경우) "평가를 남기지 못했습니다"로 답한다. `/sources`는 꺼짐과 관계없이 동작한다.
  QK-BOT-001 시험은 기본 설정(꺼짐)으로 돌아 기대값이 그대로다.
- **Rationale**: spec FR-003·FR-024·SC-011.

## R-16 시험 전략

- **Decision**: 단위 시험(가짜 기록기·가짜 시계): 해석, 버튼 값, 원문 대기, 버튼·동의 흐름, `/sources` 렌더링, 운영 로그 비노출, 설정 검사. 로컬 DB 시험: 함수 결과, 질의 역할 권한 거부(SC-007), 삭제 멱등,
  집계 수치(SC-009), 질문자 불일치 거부. Worker 시험(`node --test workers/relay/relay.test.ts`, CI `ci.yml:68`): 콜백 7 통과, 종류별 대체 문구. 실제 Discord는 사람 단계(M-01~M-03).
- **Rationale**: C-12, spec FR-022. 기존 질의 시험 묶음(`tests/unit/query/`, `tests/localdb/query/`)과 이름 규칙(`test_bot_*`)을 따라 `test_obs_*`로 둔다.

## 남는 위험

- `SECURITY DEFINER` 함수는 저장소 처음이다(R-05). 소유자 역할과 `search_path` 고정이 틀리면 권한 상승 통로가 된다. 로컬 DB 시험으로 역할 거부를 확인하고, 운영 적용 전 함수 소유자를 사람이 확인한다.
- 콜백 7의 질문자만 보는 메시지 적용(R-01 미확인)은 운영 화면으로만 확인된다.
- 공유 인스턴스 메모리의 원문 대기(R-07)는 스왑·덤프 설정에 기댄다.
- 앞 길의 결과 불명(R-04): 커밋 직후 반환이 늦으면 저장됐어도 "저장 여부를 확인하지 못했습니다. 다시 눌러 주세요."가 나간다(2026-10-29 승인된 spec SC-004·FR-008). 다시 누르거나 [저장 안 함]을
  누르면 결과에 맞는 안내가 나온다(R-07, contracts 2절 11·13행). 남는 것은 결과 불명 안내 뒤 아무도 다시 누르지 않는 경우이고, 이때도 평가·원문은 실제 저장 상태 그대로 하나 이하다.
