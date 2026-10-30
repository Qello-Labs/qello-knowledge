# Contract: Discord 버튼·`/sources`·중계 변경

**Spec**: FR-006~FR-011, FR-016~FR-017 | **Research**: R-01~R-03, R-08, R-09

## 1. 답변 메시지의 평가 버튼

`/ask` 결과 상태가 `answered`·`cannot_confirm`이고 기록 기능이 켜졌을 때, 마지막 메시지 전송 본문(`@original` PATCH 또는 마지막 후속 POST)에 다음을 더한다.

```json
"components": [
  {"type": 1, "components": [
    {"type": 2, "style": 2, "label": "👍", "custom_id": "qk1:up:<run_id>"},
    {"type": 2, "style": 2, "label": "👎", "custom_id": "qk1:down:<run_id>"}
  ]}
]
```

- 다른 메시지와 실패·안내 메시지에는 넣지 않는다. 본문 `content`, `allowed_mentions`, `flags`는 지금과 같다.
- `custom_id` 정규식 `^qk1:(up|down|keep|skip):q-[0-9]{8}T[0-9]{6}-[0-9a-f]{8}$`.

## 2. 버튼 상호작용 처리 (질의 서비스 `POST /discord/interactions`)

입력: 상호작용 종류 3, `data.component_type = 2`, `data.custom_id`, `member.user.id`, `channel`, `guild_id`, `member.roles`. 서명 검사·크기 제한은 `/ask`와 같다.

| 순서 | 조건 | 응답 |
| --- | --- | --- |
| 1 | 허용 범위 밖(QK-BOT-001 `AccessPolicy`) | 콜백 4, `flags: 64`, "여기서는 이 버튼을 쓸 수 없습니다." |
| 2 | `custom_id` 형식 틀림, `member.user.id` 없음, 기록 기능 꺼짐 | 콜백 4, 질문자만, "평가를 남기지 못했습니다." |
| 3 | `up`/`down`: `query_feedback_set` 결과 `missing` | 같은 안내 |
| 3a | `up`/`down`: 실패, 첫 응답 상한 초과, 버린 작업(결과 불명) | 콜백 4, 질문자만, "저장 여부를 확인하지 못했습니다. 다시 눌러 주세요." |
| 4 | `up`/`down`: `stored`이고 아래 5가 아님 | 콜백 4, 질문자만, "평가를 남겼습니다." |
| 5 | `down`: `stored`, 원문 대기에 그 질의가 있고 질문자 = 누른 사람, 미선택, 보존 상한 날짜 ≥ 오늘 | 콜백 4, 질문자만, 동의 문구 + 버튼 `keep`·`skip`(3절) |
| 6 | `keep`/`skip`: 대기가 있고 누른 사람 ≠ 대기의 질문자 | "평가를 남기지 못했습니다." |
| 7 | `keep`/`skip`: 대기 상태 `claimed`(다른 누름 처리 중) | 콜백 4, 질문자만, "저장 여부를 확인하지 못했습니다. 다시 눌러 주세요." |
| 8 | `keep`: 대기 `waiting`·`uncertain`, 저장 직전 비밀값 검사에 걸림 | `query_text_skip` 호출, 콜백 7 "비밀값으로 보이는 내용이 있어 저장하지 않았습니다." → `chosen` |
| 9 | `keep`: 대기 `waiting`·`uncertain`, `query_text_store` → `stored`/`exists` | 콜백 7 "질문을 저장했습니다. 지우려면 운영 담당자에게 삭제를 요청해 주세요."(버튼 없음) → `chosen` |
| 10 | `keep`: 대기 `waiting`·`uncertain`, `missing`/`not_questioner` | 콜백 4 "저장하지 못했습니다. 평가는 남았습니다." → `chosen` |
| 11 | `keep`: 대기 `waiting`·`uncertain`, 실패·상한 초과·버린 작업(결과 불명) | 콜백 4 "저장 여부를 확인하지 못했습니다. 다시 눌러 주세요." → `uncertain`(질문 유지) |
| 12 | `skip`: 대기 `waiting` | 콜백 7 "저장하지 않았습니다."(버튼 없음) → `chosen` |
| 13 | `skip`: 대기 `uncertain`, 또는 `keep`/`skip`: 대기 `chosen`·없음(만료, 재시작, 보존 상한 날짜 지남) | `query_text_status(run_id, 누른 사람)` 호출. `stored` → "이미 저장된 질문입니다. 지우려면 운영 담당자에게 삭제를 요청해 주세요."(대기가 있으면 `chosen`). `not_questioner`·`missing` → "평가를 남기지 못했습니다." `none` → 대기 `chosen`이면 "이미 선택했습니다.", 그 밖은 `skip`이면 "저장하지 않았습니다."(대기 `uncertain`이면 `chosen`), `keep`이면 "질문이 남아 있지 않아 저장하지 못했습니다. 평가는 남았습니다." 결과 불명 → "저장 여부를 확인하지 못했습니다. 다시 눌러 주세요."(상태 그대로) |

- 모든 응답에 `allowed_mentions: {"parse": []}`.
- **6~13행 평가 순서**: 행 번호순으로 처음 맞는 행 하나만 적용한다. 6행(질문자 검사)을 먼저 본다. 표의 대기 상태는 누르기 직전(선점 전) 상태다.
- **선점**: 대기 `waiting`·`uncertain`에서 질문자가 누르면 잠금 안에서 `claimed`로 선점한 뒤 8~13행을 처리한다. `chosen`·없음은 선점 없이 13행 조회만 한다. `claimed`는 7행으로 끝난다.
- **선점 뒤 상태**: 결과가 확정되면 `chosen`(질문 지움). 저장 결과 불명(11행)이나 13행 조회 결과 불명이면 선점 전 질문을 유지한 채 `uncertain`으로 돌린다. 처리 중 만료·정리된 대기는 다시 만들지 않는다.
- 조합: 질문자 아님 → 6(대기 있음) 또는 13(대기 `chosen`·없음, 함수가 `not_questioner`를 돌려줘 "질문이 남아 있지 않아…"/"저장하지 않았습니다."가 아니라 "평가를 남기지 못했습니다."로 답한다).
  질문자 → `claimed` 7, `waiting`+`keep` 8~11, `waiting`+`skip` 12, `uncertain`+`keep` 8~11, `uncertain`+`skip` 13, `chosen`·없음 13.
- `query_text_status`는 질문자 본인 질의의 원문 기록 유무만 돌려준다(data-model 3.2). 질문 원문이나 다른 질의 정보는 돌려주지 않는다.
- 저장소 호출은 기록기 앞 길에서 절대 마감까지만 기다린다(research R-04). 늦게 시작할 작업은 버리고, 마감 − 여유 시점에 취소를 요청한다. 서버 취소 완료 시각은 보장하지 않으며, 함수 한 문장이라 부분 저장은 없고, 마감까지 결과가 없으면 결과 불명 안내다(research R-04).
- 검색·생성·Workers AI·Discord 후속 호출은 없다. 운영 로그 한 줄: `{"kind":"component","action":"down","result":"stored","elapsed_ms":12}`(식별자 없음).

## 3. 동의 질문 메시지 (2절 5행)

```text
👎 평가를 남겼습니다.
이 질문을 답변 개선용으로 저장할까요?
- 저장하는 것: 이 질문 하나(답변은 저장하지 않습니다)
- 보관 기간: Phase 2 파일럿 검토까지, 늦어도 <QK_QUERY_TEXT_RETAIN_UNTIL>
- 보는 사람: 운영 담당자(파일럿 분석). 평가 세트로 옮기는 사본은 개인 정보를 지운 별도 사본입니다
- 지우기: 운영 담당자에게 삭제를 요청하면 지웁니다
```

버튼: `{"type":2,"style":1,"label":"저장 동의","custom_id":"qk1:keep:<run_id>"}`, `{"type":2,"style":2,"label":"저장 안 함","custom_id":"qk1:skip:<run_id>"}`. 문구는 계획 단계 초안이며 구분(저장 대상, 기간, 보는 사람, 지우기)은 바꾸지 않는다.

## 4. `/sources`

명령 등록(QK-BOT-001 `register-commands`)에 더한다: `{"name":"sources","type":1,"description":"봇이 검색하는 자료와 기준 시각을 봅니다","contexts":[0]}`. 인자 없음.

응답(콜백 4, `flags: 64`):

```text
자료 기준: 인덱스 <index_version> (활성화 YYYY-MM-DD HH:MM KST)
- <자료원 이름> · <종류 표시> · 문서 <N>개 · 마지막 확인 YYYY-MM-DD HH:MM KST
...
```

- 종류 표시: `github_repo_files` → "저장소 파일", `confluence_pages` → "Confluence 페이지", 그 밖은 종류 값 그대로.
- 활성 인덱스 없음: QK-BOT-001 `no_active_index` 안내 문구(확인 번호 없이).
- 허용 범위 밖: "여기서는 `/sources`를 쓸 수 없습니다."
- 저장소 실패·상한 초과: "지금은 자료 목록을 볼 수 없습니다. 잠시 후 다시 시도해 주세요."
- 2,000자를 넘으면 앞에서부터 줄 단위로 자르고 "(자료원 N개 더 있음)"을 붙인다(R-11).
- 자료원 이름은 `config/sources.toml`의 이름(예: `dnd-backend-docs`)이고 Discord 서식 글자는 QK-BOT-001 `neutralize`로 바꾼다.

## 5. 중계 Worker (`workers/relay/relay.ts`)

- 질의 서비스 응답 허용 콜백: 원본이 종류 3이면 4·7, 그 밖은 지금처럼 1·4·5. `X-QK-Run` 헤더와 시작 확인은 콜백 5에만(지금과 같음).
- 대체 응답 문구: 원본이 종류 3이거나 종류 2이면서 `data.name == "sources"`면 "지금은 처리할 수 없습니다. 잠시 후 다시 시도해 주세요." 그 밖(이름 없는 종류 2 포함)은 지금 문구. 둘 다 `flags: 64`, 알림 없음.
- 기존 시험(`relay.test.ts:61`, `:224-241`)은 바꾸지 않고 통과해야 한다. 새 사례(종류 3 + 콜백 7 통과, 종류 3·`sources` 대체 문구, 종류 2 + 콜백 7 거부 유지)를 더한다.
- 서명 검사, 크기 제한(64 KiB), 제한 시간, 호출 수(최대 2)는 바꾸지 않는다.
