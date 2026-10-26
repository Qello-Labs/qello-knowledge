# Contract: Discord → Worker → 질의 서비스

## 1. Discord → Worker

- 주소: `https://<worker 이름>.<계정 하위 도메인>.workers.dev/discord/interactions` (Discord 애플리케이션의 Interactions Endpoint URL). 실제 주소는 문서에 적지 않는다.
- 방법: `POST`, `Content-Type: application/json`. 헤더 `X-Signature-Ed25519`, `X-Signature-Timestamp`.
- 그 밖의 경로·방법: `404`·`405`, 본문 없음. `GET /healthz`는 Worker 설정 검사 결과만(질의 서비스는 부르지 않는다).

Worker 처리 순서:

1. 본문 크기가 64 KiB를 넘으면 `413`.
2. 서명 헤더가 없거나, 서명 시각이 현재와 5분 넘게 차이 나거나, `DISCORD_PUBLIC_KEY`로 `timestamp + body` 서명 검사에 실패하면 `401`, 본문 없음. 질의 서비스를 부르지 않는다.
3. VPC 바인딩 `QUERY_SERVICE`로 `POST http://127.0.0.1:<포트>/discord/interactions`를 보낸다. 본문은 원본 바이트 그대로, 서명 헤더 두 개를 그대로 붙인다. 제한 시간 `QK_RELAY_TIMEOUT_SECONDS`.
4. 질의 서비스가 `200`과 JSON을 돌려주면 그 본문을 그대로 `200`으로 돌려준다. 응답 헤더에 `X-QK-Run`이 있으면(처리 중 응답) 응답 뒤 처리(`waitUntil`)로 시작 확인(3절)을 보낸다.
5. 연결 실패, 제한 시간 초과, `200`이 아닌 응답이면 아래를 `200`으로 돌려준다.

```json
{"type": 4, "data": {"content": "지금은 답할 수 없습니다. 잠시 후 다시 질문해 주세요.", "flags": 64, "allowed_mentions": {"parse": []}}}
```

   단, 원본 본문의 `type`이 1(연결 확인)이면 질의 서비스 없이도 `{"type": 1}`을 돌려준다(Discord 수신 주소 확인이 질의 서비스 상태에 묶이지 않게).

Worker는 본문 내용을 로그에 남기지 않는다. 서명 검사에 실패한 요청은 아무것도 기록하지 않는다(spec FR-001). 중계한 요청만 결과 종류(`relayed`, `relay_failed`, `start_failed`)와 걸린 시간을
남긴다. 서명 실패 건수는 Cloudflare 대시보드의 응답 상태 코드(401) 지표로 본다.

## 2. Worker → 질의 서비스 `POST /discord/interactions`

- 질의 서비스는 `127.0.0.1`에서만 받는다.
- 서명을 다시 검사한다(Worker와 같은 규칙). 실패하면 `401`.
- 응답은 항상 `200`과 상호작용 응답 JSON이다(data-model 3절). 처리 중 응답(`type: 5`)을 돌려준 경우에만 `QueryJob`을 대기열에 넣는다.
- 응답을 돌려주기 전에 하는 일: 본문 해석, 연결 확인 처리, 허용 범위 판정, 질문의 전송 직전 검사(QK-SEC-001 `check_outgoing`, 질문만·출처 없이), 중복 판정, 대기열 자리 확인.
  DB·외부 호출은 하지 않는다.

| 입력 | 응답 |
| --- | --- |
| `type: 1` | `{"type": 1}` |
| 명령이 `ask`가 아니거나 `type`이 2가 아님 | 유형 4, 플래그 64, "지원하지 않는 요청입니다." |
| 허용 범위 밖(data-model 2절) | 유형 4, 플래그 64, "이 채널에서는 `/ask`를 쓸 수 없습니다." |
| 질문이 전송 직전 검사에 걸림 | 유형 4, 플래그 64, spec FR-006 문장 |
| 같은 상호작용 식별자(15분 안) | 유형 4, 플래그 64, "이미 처리 중인 요청입니다." |
| 수명 자리 없음(research R-05) | 유형 4, 플래그 64, "지금 요청이 많습니다. 잠시 후 다시 질문해 주세요." |
| 허용된 `/ask` | `{"type": 5}` 또는 "나만 보기"면 `{"type": 5, "data": {"flags": 64}}`. 응답 헤더 `X-QK-Run: <run_id>`. 작업은 시작 대기로 등록 |

즉시 안내의 모든 `data`에는 `"allowed_mentions": {"parse": []}`가 있다.

## 3. Worker → 질의 서비스 `POST /discord/interactions/start`

- Worker가 처리 중 응답을 Discord에 돌려준 뒤에만 보낸다. 질의 서비스 응답을 제한 시간 안에 받지 못해 Worker가 안내를 만든 경우에는 보내지 않는다.
- 본문: `{"run_id": "<X-QK-Run 값>"}`. 헤더: 원본 요청의 `X-Signature-Ed25519`, `X-Signature-Timestamp`.
- 질의 서비스는 `run_id`가 시작 대기 중이고 서명 두 값이 등록 때와 같으면 작업을 대기열에 올리고 `204`를 돌려준다. 그 밖(없는 `run_id`, 서명 불일치, 이미 시작함, 시작 대기 만료)은 `409`이고
  아무 일도 하지 않는다.
- 시작 대기(`QK_QUERY_START_WAIT_SECONDS`, 초기값 5초) 안에 시작 확인이 오지 않으면 질의 서비스는 검색·생성을 하지 않고, 첫 메시지(`PATCH @original`)를 "요청을 처리하지 못했습니다. 잠시 후
  다시 질문해 주세요."로 바꾼다(data-model 5절 `NOT_STARTED`). 이 안내는 원문·내부 값을 담지 않는다. 그래서 두 경우 모두 안전하다.
  - Worker가 처리 중 응답을 돌려줬지만 시작 확인이 실패한 경우: 처리 중 응답이 이 안내로 바뀌어 남지 않는다.
  - Worker가 제한 시간을 넘겨 질문자만 보는 안내를 돌려준 경우: 그 안내가 같은 뜻의 이 안내로 바뀐다(공개 범위는 그대로 질문자만).
  - Discord가 어떤 첫 응답도 받지 못한 경우: 갱신이 실패하고 운영 로그에 `UNDELIVERED`만 남는다.
- 제한 시간은 Worker 응답 뒤 처리 한도(30초) 안이다. 실패하면 Worker는 다시 보내지 않는다. 이 경우는 운영 로그 `not_started`와 Worker 로그 `start_failed`로 드러난다.

## 4. 다른 경로

- `GET /healthz`: 기존 동작(설정 검사 결과). 루프백 전용이므로 Worker는 부르지 않는다.
- 그 밖의 경로: 기존 동작(`404`·`405`).
