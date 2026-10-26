# Contract: `qk-query` 명령

기존 `qk-query`(`query/server.py`)에 하위 명령을 더한다. 기존 `serve`·설정 검사 동작은 유지한다.

## `qk-query serve --port <포트> --env-file <경로>`

- 기존 동작에 `POST /discord/interactions`(contracts/relay.md 2절)와 작업 실행기(작업자 `QK_QUERY_WORKERS`, 대기 `QK_QUERY_QUEUE_SIZE`)를 더한다.
- `127.0.0.1`에만 묶는다(기존).
- 시작할 때 설정 검사를 하고, 필수 설정이 없거나 교차 규칙(data-model 1절)을 어기면 종료 코드 2로 끝난다. 허용 채널 목록이 비면 경고를 내고 계속 돈다(모든 요청 거부).
- 운영에서는 systemd `qk-query.service`가 `--env-file /etc/qello-knowledge/query.env`로 띄운다.
- 질의마다 운영 로그 한 줄(JSON, data-model 5절 `QueryRunLog`)을 표준 오류로 쓴다. 원문·식별자·토큰을 쓰지 않는다.

## `qk-query register-commands --env-file <경로> [--dry-run]`

- 명령 등록(contracts/discord-outbound.md 2절). 필요 설정: `DISCORD_APPLICATION_ID`, `QK_DISCORD_GUILD_ID`, `DISCORD_BOT_TOKEN`.
- `--dry-run`은 보낼 JSON만 출력하고 호출하지 않는다(토큰 없이 실행 가능).
- 종료 코드: 0 성공, 2 설정 오류, 3 Discord 오류(상태 코드만 출력, 응답 본문과 토큰은 출력하지 않음).
