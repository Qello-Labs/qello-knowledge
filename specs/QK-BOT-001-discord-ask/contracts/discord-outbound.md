# Contract: 질의 서비스 → Discord, 명령 등록

모든 호출은 `https://discord.com/api/v10` 아래다. 질의 경로 호출에는 인증 헤더가 없다(상호작용 토큰이 경로에 있다). `User-Agent: DiscordBot (https://github.com/Qello-Labs/qello-knowledge, <버전>)`.

## 1. 답변 갱신

1. 첫 메시지: `PATCH /webhooks/{application_id}/{interaction_token}/messages/@original`
2. 이어지는 메시지(분할 둘째부터): `POST /webhooks/{application_id}/{interaction_token}`, 순서대로 하나씩 보낸다. "나만 보기"면 `flags: 64`를 붙인다.

본문:

```json
{"content": "<2,000자 이하>", "allowed_mentions": {"parse": []}}
```

- 링크는 `<URL>` 꼴(미리보기 없음). 출처 제목 등 자료 유래 글의 서식 글자는 바꾼다(spec FR-014).
- 다시 시도: 메시지마다 최대 2회 시도(처음 1회 + 다시 1회)다. 다시 시도하는 경우는 `429`(응답의 `retry_after`), `5xx`, 연결 오류, 그리고 **첫 메시지(`@original`)의 첫 시도가 `404`일 때**다
  (Discord가 처리 중 응답을 아직 반영하지 않았을 수 있다. 삭제·토큰 만료와 구분할 수 없으므로 첫 메시지의 `404`에는 늘 1초 뒤 한 번만 다시 보낸다). 대기 시간이 안내 전달 마감까지 남은
  시간보다 길면 다시 시도하지 않는다(spec FR-009). 그 밖의 `4xx`와 두 번째 시도의 `404`는 다시 시도하지 않고 `UNDELIVERED`로 운영 로그에만 남긴다. 이어지는 메시지의 `404`는 다시 시도하지 않는다.
- 각 호출의 HTTP 시간 제한은 min(3초, 안내 전달 마감까지 남은 시간)이다. 다시 시도는 (대기 시간 + 1초)가 남은 시간 안일 때만 하고, 남은 시간이 1초보다 짧으면 호출하지 않는다(research R-05).
- 한 질의의 전송 순서: 첫 메시지가 성공해야 이어지는 메시지를 보낸다. 첫 메시지가 끝내 실패하면 이어지는 메시지를 보내지 않는다.

## 2. 명령 등록 (운영 담당자, 로컬)

`PUT /applications/{application_id}/guilds/{guild_id}/commands`, 헤더 `Authorization: Bot <DISCORD_BOT_TOKEN>`.

```json
[
  {
    "name": "ask",
    "type": 1,
    "description": "팀 자료에서 찾아 출처와 함께 답합니다",
    "contexts": [0],
    "options": [
      {"type": 3, "name": "질문", "description": "물어볼 내용", "required": true, "min_length": 1, "max_length": 2000},
      {"type": 5, "name": "나만_보기", "description": "켜면 답변을 나만 봅니다", "required": false}
    ]
  }
]
```

- 옵션 이름 `질문`, `나만_보기`는 Discord 이름 규칙(유니코드 문자와 밑줄 허용)에 맞는다(2026-10-25 독립 검토 확인, https://docs.discord.com/developers/interactions/application-commands).
- 서버 한정은 서버(guild) 등록 경로로 보장한다. `contexts: [0]`(GUILD)은 값은 맞지만 문서가 이 필드를 전역 명령용으로 설명하므로 서버 등록에서의 수락·효과는 M-01 때 확인한다. 거부되면 필드를 뺀다.
- 통째 덮어쓰기라 다시 실행해도 결과가 같다. 이 애플리케이션의 그 서버 명령은 이 목록만 남는다(research R-12).
- `max_length`는 검색 질문 길이 상한(`RetrievalSettings.question_max_chars`, 기본 2,000)과 같은 값을 쓴다(spec FR-003).
