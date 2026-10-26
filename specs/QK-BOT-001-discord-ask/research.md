# Research: QK-BOT-001 Discord `/ask`

> 작성: 2026-10-25, 계획 단계. 공식 문서 조회일은 모두 2026-10-25다.
> 표시: `(추론)`은 근거를 엮어 낸 판단, `미확인`은 문서로 확인하지 못한 것이다. 미확인 항목은 M-01~M-04 실측으로 닫는다.

## R-01 검색·생성 실행 위치

- **Decision**: Cloudflare Worker는 Discord 요청의 서명 검사와 중계만 한다. 허용 범위·비밀값 검사, 검색·생성, 답변 갱신은 OCI 공유 인스턴스의 질의 서비스(`qk-query`)가 기존 코드로 한다
  (2026-10-25 사용자 결정, ADR-022 Proposed).
- **Rationale**:
  - 기존 검색·생성은 동기 코드다. 저장소는 `psycopg`(`adapters/postgres/`), Workers AI는 `urllib`(`adapters/workers_ai/rest.py`, `adapters/http.py`)를 쓴다. 인스턴스에서는 이 조립이
    `qk-index ask`로 이미 돈다(`indexer/ask_cli.py:44` `postgres_ask`).
  - Python Workers(Pyodide)에서 `psycopg`와 `urllib` 소켓은 쓸 수 없다 `(추론)`. 동기 코드에서 Workers의 비동기 `fetch`를 기다리는 방법(Pyodide JSPI `run_sync`)이 Workers에서
    되는지는 미확인이다(https://blog.pyodide.org/posts/jspi/). 안 되면 검색·생성 서비스를 비동기로 바꿔야 하고, 이는 TASK.md 제외 범위(QK-RET-001·QK-GEN-001 동작 변경)다.
  - Workers의 응답 뒤 계속 처리(`waitUntil`)는 30초까지다(https://developers.cloudflare.com/workers/platform/limits/). 생성은 재시도까지 기본 45초가 걸릴 수 있다(QK-GEN-001 research R-07).
    인스턴스는 이 제한이 없어 생성 기본값을 그대로 쓴다.
  - Workers Free CPU는 요청당 10 ms다(같은 문서). Python Worker 기동 CPU는 재지 않았다(QK-FND-001 research 남는 위험). Worker 일을 서명 검사와 중계로 줄이면 위험이 가장 작다.
  - Worker가 질의 서비스에 닿지 못해도 질문자만 보는 안내를 보낼 수 있다(spec FR-011 마지막 행).
- **Alternatives considered**:
  - 전부 Workers(ADR-008 원안): 비동기 어댑터(Workers AI 바인딩, DB는 Hyperdrive + `asyncpg` 또는 VPC → PostgREST), 서비스 비동기화나 JSPI, 30초를 넘기려면 Queue 소비자(Free 플랜에서
    하루 10,000 작업, 소비자 15분, https://developers.cloudflare.com/queues/platform/pricing/)가 필요하다. 공수와 미확인이 가장 크다.
  - 인스턴스 단독(Tunnel 공개 호스트명으로 Discord 직접 수신): 구성은 단순하지만 Cloudflare에 등록된 도메인이 필요하고(팀 보유 미확인), 공유 인스턴스가 공개 엔드포인트를 직접 받으며,
    인스턴스 장애 때 안내를 보낼 수 없다.

## R-02 Worker ↔ 질의 서비스 연결

- **Decision**: Workers VPC Service 바인딩(HTTP)으로 인스턴스의 `cloudflared`(원격 관리 터널)를 거쳐 `127.0.0.1:<질의 서비스 포트>`에 닿는다. 공개 호스트명·DNS 레코드·인바운드 포트를 만들지 않는다.
- **Rationale**:
  - Workers VPC는 Free·Paid 플랜에서 쓸 수 있고 베타 동안 무료다(https://developers.cloudflare.com/workers-vpc/). VPC Service는 호스트·포트 하나에 묶이고 HTTP를 지원한다. 설정 예시가
    `"ipv4": "127.0.0.1"`과 `tunnel_id`를 쓴다(https://developers.cloudflare.com/workers-vpc/configuration/vpc-services/).
  - 터널은 Cloudflare로 나가는 연결만 유지하고 인바운드 방화벽 규칙과 공인 IP가 필요 없으며, Workers VPC에는 ingress 설정이 필요 없다. QUIC용 바깥 방향 UDP 7844를 허용해야 하고
    `cloudflared` 2025.7.0 이상이어야 한다(https://developers.cloudflare.com/workers-vpc/configuration/tunnel/).
  - 바인딩은 특정 Worker에만 붙으므로 질의 서비스 앞에 따로 인증 토큰을 두지 않아도 외부에서 닿을 수 없다 `(추론)`. 그래도 질의 서비스가 Discord 서명을 다시 검사한다(R-04).
- **Alternatives considered**: Tunnel 공개 호스트명 + Cloudflare Access 서비스 토큰(도메인 필요), Queues HTTP 끌어오기 소비자(인스턴스가 주기적으로 끌어오면 하루 작업 한도를 넘을 수 있고 지연이
  끌어오기 주기만큼 늘어난다 `(추론)`), PostgREST·Hyperdrive로 DB만 연결(R-01에서 Workers 실행을 버려 필요 없음).
- **남는 위험**: 베타라 정식 출시 뒤 가격·API가 바뀔 수 있다(ADR-022 Revisit). Python Worker에서 VPC 바인딩 `fetch`가 되는지는 미확인(M-01).
- **운영 전제**: Workers VPC 터널은 QUIC(`auto` 또는 `quic`)와 바깥 방향 UDP 7844를 요구한다(같은 문서). `http2`로 바꾸는 대안은 없다(2026-10-25 독립 검토 지적). 인스턴스(OCI 보안 목록
  egress, 호스트 방화벽)에서 바깥 방향 UDP 7844가 막혀 있고 열 수 없으면 이 결정을 다시 본다(ADR-022 Revisit: Tunnel 공개 호스트명 + Access 서비스 토큰).

## R-03 첫 응답 경로와 시간

- **Decision**: 두 단계로 한다.
  1. **중계**: Worker는 서명을 검사하고 원본 본문과 서명 헤더를 그대로 질의 서비스 `POST /discord/interactions`로 보낸다. 질의 서비스는 첫 응답을 정하는 일(연결 확인, 허용 범위, 비밀값 검사,
     중복 판정, 대기열 자리 예약)만 동기로 하고, 처리 중 응답을 정했으면 작업을 **시작 대기**(`AWAITING_START`)로 등록하고 응답 헤더 `X-QK-Run`에 질의 실행 식별자를 실어 돌려준다.
  2. **시작 확인**: Worker는 질의 서비스의 응답을 제한 시간 안에 받았을 때만 그 JSON을 Discord에 돌려주고, 응답 뒤 처리(`waitUntil`)로 `POST /discord/interactions/start`(본문: 실행 식별자,
     헤더: 원본 서명 두 개)를 보낸다. 질의 서비스는 실행 식별자와 원본 서명이 등록 때와 같을 때만 작업을 대기열에 올린다.
  - 시작 확인이 시작 대기 제한(초기값 5초) 안에 오지 않으면 검색·생성을 하지 않고, 첫 메시지를 "요청을 처리하지 못했습니다. 잠시 후 다시 질문해 주세요."로 바꾼다(운영 로그 `not_started`,
    대기열 자리 반환). Worker가 제한 시간을 넘겨 질문자만 보는 안내를 보낸 경우와 Worker가 처리 중 응답을 보냈지만 시작 확인이 실패한 경우가 여기에 든다. 앞의 경우는 Worker 안내가 같은 뜻의
    안내로 바뀌고(질문자만 보기 유지), 뒤의 경우는 처리 중 응답이 남지 않는다. 검색·생성 답변이 Worker 안내 자리에 들어가는 일은 없다(2026-10-25 독립 검토 H1).
  - 시작 확인 뒤에도 Discord가 처리 중 응답을 아직 반영하지 않았을 수 있다. 첫 `PATCH @original`이 `404`면 1초 뒤 한 번 더 보낸다(FR-009의 다시 시도 1회 안).
  - Worker의 질의 서비스 호출은 최대 2회다(spec FR-016).
- **시간 예산**: Discord 3초(https://docs.discord.com/developers/interactions/receiving-and-responding). Worker의 질의 서비스 호출 제한 시간 초기값 2.5초(`QK_RELAY_TIMEOUT_SECONDS`).
  넘기면 Worker가 질문자만 보는 안내를 만든다. 질의 서비스의 첫 응답 결정은 DB·외부 호출 없이 정규식 검사와 메모리 조회만 하므로 수십 ms 안이라고 본다 `(추론, M-03에서 잰다)`.
- **응답 꼴**: 처리 중 응답은 유형 5(`DEFERRED_CHANNEL_MESSAGE_WITH_SOURCE`), "나만 보기"면 `flags: 64`. 지연 응답에 쓸 수 있는 플래그는 `EPHEMERAL`뿐이다. 즉시 안내(허용 범위·비밀값·미지원)는
  유형 4에 `flags: 64`다(같은 문서).
- **Alternatives considered**: Worker가 허용 범위·비밀값 검사까지 하기(Worker에 QK-SEC-001 규칙과 허용 범위 설정을 실어야 하고 Python CPU 위험이 커진다), Worker가 늘 지연 응답을 먼저 보내고
  질의 서비스에 작업만 넘기기(비밀값 질문도 공개 처리 중 응답이 나가 spec FR-006을 어긴다).

## R-04 서명 검사

- **Decision**: 두 곳에서 검사한다. Worker는 Web Crypto Ed25519 `verify`로 검사하고 틀리면 401을 돌려준다. 질의 서비스는 같은 헤더(`X-Signature-Ed25519`, `X-Signature-Timestamp`)와 원본
  본문으로 다시 검사한다.
- **Rationale**: Discord는 서명이 틀린 요청에 401을 돌려주는지로 수신 주소를 확인한다 `(일반 설명, M-01 등록 때 확인)`. Workers Web Crypto는 Ed25519 `sign`·`verify`를 지원한다
  (https://developers.cloudflare.com/workers/runtime-apis/web-crypto/). 질의 서비스의 재검사는 네트워크 경로를 믿지 않으려는 이중 방어다. 서명은 서명 시각과 원본 본문을 이어 붙인 값으로
  검사한다(https://docs.discord.com/developers/interactions/overview). 서명 시각 허용 차이는 5분이다(spec FR-001).
- **의존성**: 표준 라이브러리에는 Ed25519가 없다. 질의 서비스에만 `cryptography`를 선택 의존성 묶음 `query`로 더한다. 런타임 기본 의존성은 비워 둔다(pyproject 주석, QK-FND-001 R-03).
- **Alternatives considered**: PyNaCl(같은 일을 하지만 저장소에 다른 쓰임이 없다), 순수 Python Ed25519 구현(검증되지 않은 암호 코드를 들이지 않는다), 질의 서비스에서 재검사 생략(R-02의 격리만 믿게 된다).

## R-05 질의 서비스 실행 모델

- **Decision**: 기존 `qk-query` 서버(`query/server.py`, `ThreadingHTTPServer`, 루프백 전용)를 확장한다. systemd 서비스 `qk-query.service`로 상주한다. 작업 실행은 다음 규칙을 따른다
  (2026-10-25 독립 검토 H2).
  - **실행 자리**: 실행 자리는 `QK_QUERY_WORKERS`(초기값 2)개다. 작업은 자리를 잡은 뒤 검색·생성을 돌리고, **검색·생성 호출이 실제로 끝날 때까지** 자리를 놓지 않는다. 질의 마감으로 결과를
    버린 작업도 호출이 끝날 때까지 자리를 쥔다. 그래서 실제로 동시에 도는 검색·생성은 자리 수를 넘지 않는다.
  - **대기 크기**: `QK_QUERY_QUEUE_SIZE`(초기값 4)는 수명 자리 `C`를 셈하는 추가분이다. 따로 예약하는 자리는 수명 자리 하나뿐이다. 실제로 실행 자리를 기다리는 작업은 대개 4개 이하지만,
    안내를 마친 늦은 실행이 실행 자리 2개를 쥐고 있으면 새로 받은 작업 `C`개(기본 6)가 모두 기다릴 수 있다. 이때 보유 작업 전체는 최대 `C + WORKERS`(기본 8)다. 늦은 실행은 전달 권한을 이미 썼으므로
    전달 풀 상한을 깨지 않는다(2026-10-25 독립 재검토 L4).
  - **마감 감시**: 별도 감시 스레드 하나가 모든 작업(시작 대기, 대기 중, 실행 중)의 시작 대기 만료와 질의 마감을 본다. 감시 스레드는 **상태 전이와 전달 예약만** 하고 Discord에 직접 보내지
    않는다(2026-10-25 독립 재검토 M9). 대기 중인 작업이 실행 자리를 잡을 때 남은 시간이 최소 시작 시간(초기값 15초: 검색 약 5초 + 생성 마감 하한 7초 + 여유) 아래면 실행하지 않고 시간 초과로
    전이한다.
  - **수명 자리(2026-10-25 독립 재검토 H5)**: 질의 서비스가 동시에 맡는 작업 수는 수명 자리 `C = QK_QUERY_WORKERS + QK_QUERY_QUEUE_SIZE`(기본 6)개를 넘지 않는다. 처리 중 응답을 정할 때
    수명 자리를 예약하고, 작업이 끝 상태(`DONE`, `UNDELIVERED`)에 갈 때 반환한다. 전달 중인 작업도 자리를 쥔다. 자리가 없으면 처리 중 응답 대신 질문자만 보는 "요청이 많습니다" 안내다.
  - **실행 자리**: 수명 자리 안에서 검색·생성을 동시에 돌리는 수는 `QK_QUERY_WORKERS`(기본 2)다. `RETRIEVING`에서 잡고 검색·생성 호출이 실제로 끝날 때 반환한다(결과를 버린 작업 포함).
  - **전달 실행기**: Discord 전송은 별도 전달 스레드 풀이 한다. 풀 크기는 수명 자리 수 `C`와 같다. 전달 중인 작업은 모두 수명 자리를 쥐고 있으므로 전달 요청 수는 풀 크기를 넘지 않고, 전송이
    서로를 기다리지 않는다. 전달 대기열은 둘 필요가 없다(넘치면 설계 위반으로 보고 시험이 잡는다).
  - **전달 시간(2026-10-25 독립 재검토 M10)**: 호출마다 HTTP 시간 제한 = min(3초, 안내 전달 마감까지 남은 시간)이다. 다시 시도는 (대기 시간 + 최소 호출 시간 1초)가 남은 시간 안일 때만 한다.
    남은 시간이 1초보다 짧으면 호출하지 않고 `UNDELIVERED`로 끝낸다. `urllib`의 `timeout`은 막히는 작업 하나의 제한이지 요청 전체 경과 시간의 제한이 아니다
    (https://docs.python.org/3.13/library/urllib.request.html#urllib.request.urlopen). 그래서 전달 실행기는 호출 전체 경과 시간도 안내 전달 마감과 비교하고, 마감 때 연결된 소켓을
    `shutdown`·`close`해 헤더·본문 대기를 끝낸다. urllib가 DNS·TLS 연결 중이거나 시험용 주입 opener에 소켓을 드러내지 않는 경우에는 Python 스레드를 강제로 끝낼 수 없다. 이때
    전송 스레드는 실제 반환까지 자리를 쥔다. 운영 질의 서비스는 검사를 통과한 설정의 `C = QK_QUERY_WORKERS + QK_QUERY_QUEUE_SIZE`를 웹훅 전송부에 주입한다(기본 6, 설정 최대 24).
    HTTP 전송 자리와 소켓이 없는 잔여 스레드의 상한은 이 `C`다. `C`개가 동시에 진행 중이어도 고정 상한 8 때문에 시간이 남은 전송이 거부되지 않으며, 더 들어온 호출은 자리가 비기 전까지
    즉시 실패한다. 시험은 연결된 소켓의 마감 중단, 설정 `C=24`에서 24번째 전송 허용과 25번째 잔여 작업 제한을 각각 본다. DNS/TLS 단계의 실제 완료 시각은 보장하지 못한다.
  - **전달 한 번**: 작업마다 "전달 권한"을 원자적으로 한 번만 넘긴다. 결과 전달, 시간 초과 안내, `NOT_STARTED` 안내 가운데 먼저 권한을 얻은 쪽만 전달 실행기에 맡긴다. 시작 확인과 시작 대기 만료도
    같은 잠금 안에서 원자적으로 처리한다.
  - 시험: 동시 만료 6개, 느린 전송(시간 제한 근처), `429` 대기, 늦게 끝나는 실행 작업, 앞 전송이 느린 동안 새 요청이 계속 들어오는 경우를 조합한다. 모든 작업의 전송이 안내 전달 마감 안에
    끝나거나 멈추는지(완료·중단 시각), 수명 자리가 없을 때 새 요청이 "요청이 많습니다"로 바로 거절되는지, 전달 풀이 기다리는 일이 없는지 본다.
- **Rationale**: 하루 50건 규모라 동시 처리 2개로 충분하다 `(추론)`. 검색·생성 코드가 동기이므로 스레드가 가장 작은 변경이다. 자리 상한으로 공유 인스턴스(회의 봇과 같이 씀, ADR-008)의
  메모리·CPU 사용을 묶는다. 가장 나쁜 경우 대기 4개 작업은 앞 작업이 끝날 때까지 기다리다 마감 감시가 시간 초과 안내를 보낸다. 대기 자리를 작게 둔 이유다.
- **Alternatives considered**: asyncio로 다시 쓰기(동기 코드 전체 변경), DB 작업 대기열과 별도 작업자 프로세스(지금 규모에 과함), 요청마다 프로세스 띄우기(기동 비용).

## R-06 질의 마감 구현

- **Decision**: 질의 서비스가 요청을 받은 시각(단조 시계)부터 잰다. 질의 마감 초기값 55초, 안내 전달 마감 60초(spec FR-008).
  - **검색(질의별 주입, 2026-10-25 독립 검토 H3)**: 기존 기본값은 임베딩 HTTP 시간 제한 60초(`adapters/workers_ai/rest.py:27`), DB 연결 10초(`adapters/postgres/connection.py:54`), SQL 문장
    제한 없음이다. 질의 서비스는 작업마다 다음을 주입해 검색 부품을 새로 만든다. 임베딩 쪽은 기존 생성자 인자만 쓰고, DB 쪽만 검색 저장소 어댑터에 선택 인자를 더한다(아래, plan
    Scope 승인 목록).
    - 임베딩 HTTP 시간 제한: `UrllibTransport(timeout=min(10, 남은 시간 − 여유))`(`rest.py:48`)를 `WorkersAiRestProvider(transport=…)`(`rest.py:133`)에 넘긴다.
    - 임베딩 재시도: `EmbeddingService(retry_policy=…, sleep=…)`(`embedding/service.py:112–124`). 재시도 정책은 1회(기존 `search_cli`와 같음)이고, 주입한 `sleep`은 대기 뒤 남은 시간이 시간
      제한보다 짧으면 대기하지 않고 `DeadlineReached`를 일으킨다. 작업은 이를 시간 초과로 처리한다(재시도 시작 차단).
    - DB(2026-10-25 독립 재검토 H3): 연결 문자열의 `statement_timeout`은 문장마다 적용되어 질의 전체 마감을 지키지 못한다
      (https://www.postgresql.org/docs/current/runtime-config-client.html#GUC-STATEMENT-TIMEOUT). 그래서 **검색 저장소 어댑터를 바꾼다**: `PostgresStore`에 선택 인자 `deadline`(남은 시간을 돌려주는
      함수)을 더한다. 검색·문맥 호출마다 실행 직전에 남은 시간을 보고(DB 호출 없음) 모자라면 호출하지 않고 시간 초과 오류를 낸다. 충분하면 그 질의 동안만 남은 시간 뒤에 연결 취소를
      보내는 타이머를 걸고 실행한 뒤 타이머를 푼다. 취소되면 시간 초과 오류로 바꾼다. 문장 제한을 거는 `SET` 문장을 따로 보내지 않으므로 저장소 질의 수와 QK-RET-001 FR-026의 외부 호출 계수(상한 7)는
      바뀌지 않는다(2026-10-25 독립 재검토 M11). 취소 요청은 마감에 닿았을 때만 나가는 제어 신호이고 저장소 질의가 아니다. 동기 연결의 `Connection.cancel_safe()`는 psycopg 3.2부터 있다
      (https://www.psycopg.org/psycopg3/docs/api/connections.html#psycopg.Connection.cancel_safe, 2026-10-25 독립 재검토 확인). 다만 libpq 17 미만에서는 시간 제한 인자가 효과 없이 기존 막는
      방식 `cancel()`로 돌아가고, 취소 요청이 성공해도 서버 실행 종료를 보장하지 않는다. 그래서 취소는 타이머 스레드에서 보내고, 실행 자리는 질의가 실제로 끝날 때까지 쥔다(R-05). 구현 시험은
      취소 실패·늦은 취소, 질의 완료와 타이머 해제의 경합, 연결 정리를 포함한다. 인자가 없으면 지금 동작 그대로다(색인·CLI 영향 없음). 연결 제한 10초보다 남은 시간이 짧으면 새 연결을 맺지 않는다. 이 변경은 plan Scope 승인 목록에 필요한 변경으로 올린다.
    - 사용량 기록(임베딩·생성 장부)은 마감과 상관없이 쓴다. 늦게 끝난 호출의 사용량도 남겨야 하기 때문이다(QK-GEN-001 FR-020). 마감은 새 검색 호출만 막는다.
  - **생성(2026-10-25 독립 검토 M1)**: 설정된 기본 생성 설정(`config.check.generation_settings`, `QK_GEN_TIMEOUT_SECONDS` 반영)을 복제하고 남은 시간으로 줄인다. 시간 제한 =
    min(설정 시간 제한, ⌊(남은 시간 − 5) ÷ 2⌋), 생성 마감 = min(설정 생성 마감, 남은 시간). 그래서 설정이 질의 마감보다 짧으면 설정이 그대로 쓰이고, 생성 설정 허용 범위
    (`domain/generation.py:81`, `:95–96`)를 넘지 않는다. 남은 시간이 7초보다 짧으면 생성을 시작하지 않는다. 질의 마감 설정 범위는 15~120초로 둔다(data-model 1절).
  - **"기다리지 않음"과 늦게 끝난 작업**: 작업 스레드는 검색·생성을 내부 실행기에 넘기고 질의 마감까지만 기다린다. 마감 감시(R-05)가 시간 초과 안내를 보낸다. Python 스레드는 강제로 끝낼 수
    없으므로 늦게 끝난 결과는 버린다. 그 호출은 위 시간 제한까지 갈 수 있고, 그동안 실행 자리를 쥐고 있다(R-05). 사용량 기록은 기존 장부가 그대로 남기고(QK-GEN-001 FR-020), DB 연결은
    작업의 `finally`에서 닫는다.
- **Alternatives considered**: 생성 경계에 취소 신호 더하기(QK-GEN-001 계약 변경), 프로세스 단위 실행과 강제 종료(과함).

## R-07 운영 저장소 연결과 권한

- **Decision**: 질의 서비스는 `localhost`로 붙고, 새 DB 역할 `qk_query`를 쓴다. 마이그레이션 `0007_query_role.sql`이 `NOLOGIN` 역할과 권한(스키마 `qk` 사용, 검색·문맥 함수 실행, 사용량
  기록·오늘 합계 함수 실행과 그 함수가 쓰는 표의 필요한 권한)과 `qk.embedding_usage`의 RLS 정책(`purpose = 'query'` 행만 INSERT)을 만든다. 로그인과 암호는 운영 담당자가 서버에서 숨김 입력으로
  정하고 저장소에 남기지 않는다. 권한 목록과 RLS 전제는 data-model 4절에 있다.
- **Rationale**: spec FR-019(검색 읽기·사용량 기록 쓰기로 한정). 마이그레이션으로 두면 로컬 DB 시험(SC-010)과 운영이 같은 권한을 쓴다. 정확한 권한 목록은 함수마다 `SECURITY INVOKER`가 쓰는 표를
  따라가 data-model 4절에서 정하고, 구현 때 시험으로 확인한다.
- **Alternatives considered**: 기존 소유자 역할 재사용(색인 데이터 변경 권한까지 갖는다), 운영 문서 SQL로만 만들기(로컬 시험과 운영이 어긋날 수 있다).

## R-08 Workers AI 호출과 토큰

- **Decision**: 기존 Workers AI REST 제공자(생성 `adapters/workers_ai/generation.py`, 임베딩 `adapters/workers_ai/rest.py`)를 쓴다. 토큰은 질의 서비스 전용으로 새로 발급하고(Workers AI 권한만),
  `/etc/qello-knowledge/query.env`(root:qkquery, 0640)에 둔다.
- **Rationale**: 소비 Neurons를 응답 헤더로 받는 경로가 이미 확인됐다(spike-workers-ai 3.2, QK-GEN-001 Assumptions). 색인용 토큰(`sync.env`, `qksync`)과 나누면 한쪽 유출이 다른 쪽에 번지지 않는다
  (ADR-021과 같은 원칙). 토큰 발급과 입력은 사람이 한다.
- **Alternatives considered**: 색인 토큰 재사용(유출 범위가 겹친다), Worker 바인딩으로 부르고 결과만 넘기기(R-01에서 버림).

## R-09 메시지 표시 꼴

- **Decision**: 임베드 없이 본문(`content`, 2,000자)으로 보낸다. 모든 메시지에 `allowed_mentions: {"parse": []}`를 둔다. 링크는 `<URL>` 꼴로 감싸 미리보기 카드를 막는다.
- **Rationale**: 본문 꼴은 글자 수 계산이 단순하고(spec FR-012 산식), 복사가 쉽고, 마크다운 서식을 그대로 쓴다. 지연 응답에는 `SUPPRESS_EMBEDS`를 줄 수 없으므로(R-03) 링크를 꺾쇠로 감싼다.
  응답에 사용자 자료가 들어가면 `allowed_mentions`로 알림을 막으라고 Discord가 권고한다(https://docs.discord.com/developers/interactions/receiving-and-responding).
- **Alternatives considered**: 임베드(설명 4,096자 등 한도가 크지만 필드별 한도 계산이 복잡하고 멘션·서식 동작이 다르다 `(일반 설명)`).

## R-10 중복 판정 상태

- **Decision**: 질의 서비스 메모리 안의 만료 사전(상호작용 식별자 → 처리 단계, 만료 15분)으로 둔다.
- **Rationale**: 질의 서비스는 프로세스 하나다(R-05). DB 쓰기와 마이그레이션이 늘지 않는다. 같은 상호작용의 재전송은 드물다 `(추론)`.
- **받아들이는 위험**: 질의 서비스가 다시 시작되면 상태를 잃는다. 다시 시작 직후 15분 안에 재전송이 오면 한 번 더 처리될 수 있다. 운영 로그의 재시작 기록으로 확인할 수 있다.
- **Alternatives considered**: DB 표(요청마다 쓰기, 새 표와 권한), Workers KV(최종 일관성이라 동시 중복을 못 막는다 `(일반 설명)`).

## R-11 검색·생성 조립과 생성 포트

- **Decision**: 질의 서비스 조립 코드(`query/pipeline.py`)가 `ask_cli`와 같은 부품(`postgres_search`, `PostgresGenerationLedger`, `WorkersAiGenerationProvider`)으로 검색과 생성을 잇고,
  생성은 `generate(request, deps, settings)`를 직접 부른다. 생성 포트(`ports/generator.py` `Generator.generate(request)`) 어댑터는 만들지 않는다.
- **Rationale**: 질의별 설정을 넘겨야 하는데 포트에는 설정 인자가 없다(독립 검토 확인). 직접 호출이 계약 변경 없이 가장 작다. 질의 실행 식별자는 `GenerationRequest.run_id`로 넘긴다(spec FR-011).
- **Alternatives considered**: 질의별 설정을 가진 포트 어댑터(같은 일을 감싸기만 한다), 포트에 설정 인자 더하기(QK-GEN-001 계약 변경).

## R-12 봇 토큰과 명령 등록

- **Decision**: 질의 경로(Worker, 질의 서비스)에는 봇 토큰을 두지 않는다. 답변 갱신과 이어지는 메시지는 상호작용 토큰으로 `PATCH /webhooks/<app_id>/<token>/messages/@original`,
  `POST /webhooks/<app_id>/<token>`를 쓴다. 명령 등록은 운영 담당자가 로컬에서 `qk-query register-commands`로 하고, 이때만 로컬 `.env`의 `DISCORD_BOT_TOKEN`을 쓴다
  (`PUT /applications/<app_id>/guilds/<guild_id>/commands`, 통째 덮어쓰기라 다시 실행해도 같다).
- **Rationale**: 상호작용 웹후크 경로는 애플리케이션 ID와 상호작용 토큰으로 부르며 문서에 인증 헤더 요구가 없다(R-03 문서). 서버에 봇 토큰이 없으면 유출 범위가 줄어든다. tokens.md T-03의 답이다.
- **Alternatives considered**: client credentials 토큰(클라이언트 비밀값이라는 다른 비밀값이 필요하다), 서버에 봇 토큰 두기(필요 없는 권한).
- **주의**: 통째 덮어쓰기는 이 애플리케이션의 다른 서버 명령을 지운다. 지금은 `/ask`뿐이다. QK-SYN-002가 `/reindex`를 더할 때 같은 명령 목록에 넣는다.

## R-13 Worker 구현 언어와 설정

- **Decision**: 기존 Python Worker 겉껍질(`query/worker.py`)을 중계로 바꾼다. Worker 설정은 `DISCORD_PUBLIC_KEY`, `QK_RELAY_TIMEOUT_SECONDS`, VPC 바인딩 `QUERY_SERVICE`뿐이다.
  설정 진입점을 Worker용 `relay`와 질의 서비스용 `query`로 나눈다(data-model 1절).
- **Rationale**: QK-FND-001이 Python Workers와 `pywrangler`로 정했다. 중계는 패키지 의존성이 없고 일이 작다.
- **대안 발동 조건**: M-02에서 Worker CPU가 Free 한도(10 ms)를 자주 넘으면 중계만 TypeScript Worker로 옮긴다. 도메인 코드는 Worker에 없으므로 옮길 것이 중계뿐이다.

## R-14 운영 구성

- **Decision**: 인스턴스에 다음을 둔다(팀원 동의 뒤, 사람이 명령마다 승인).
  - 전용 시스템 사용자 `qkquery`(로그인 없음, sudo·docker 그룹 없음). `qk-query.service`(`User=qkquery`, `EnvironmentFile=/etc/qello-knowledge/query.env`, 루프백 포트, 격리 설정은
    `qk-sync-notify@.service`와 같은 수준).
  - `cloudflared`(원격 관리 터널, systemd 서비스). 터널 토큰은 서버에만 둔다.
  - 운영 절차는 `docs/ops/oci-production-store.md`에 새 절로 쓴다.
- **Rationale**: ADR-020·ADR-021에서 쓴 서버 구성 방식(전용 사용자, 비밀값 파일 분리, systemd)과 맞춘다.

## R-15 실측 계획

| ID | 확인할 것 | 방법 | 비용 |
| --- | --- | --- | --- |
| M-01 | Python Worker에서 VPC 바인딩 `fetch`가 되고, 인스턴스 바깥 방향 UDP 7844(QUIC)로 터널이 붙는다. Discord 수신 주소 등록 때 서명 검사(401) 확인을 통과한다 | 시험 질의 서비스(연결 확인만 응답)로 배포·등록 | 0 Neurons |
| M-02 | Worker 요청당 CPU 시간이 Free 한도 안이다 | Cloudflare 대시보드 Worker 지표, 연결 확인·명령 요청 각 10회 이상 | 0 Neurons |
| M-03 | Discord → Worker → 질의 서비스 첫 응답 시간 p50·p95가 3초보다 충분히 짧다 | 운영 로그 단계별 시간, 허용 밖 채널 요청(검색·생성 없음) 10회 이상 | 0 Neurons |
| M-04 | spec SC-001·SC-002·SC-012·SC-013 | 질문 세트 10~12개 실측 | 약 500~610 Neurons. 실행 전 예상량 보고와 사람 확인(AGENTS.md 3.5) |

## 독립 검토가 넘긴 플랫폼 사실 (spec Assumptions와 같음)

- 3초 첫 응답, 상호작용 토큰 15분, 응답 공개 범위 변경 불가, 본문 2,000자, Ed25519 서명: 확인됨.
- 질문자만 보는 첫 응답이면 명령 실행 사실·인자까지 숨겨지는지: 미확인. spec SC-005 사람 단계로 확인한다.
