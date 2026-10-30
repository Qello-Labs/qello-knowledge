# Contract: `qk-index queries` 운영 명령

**Spec**: FR-013~FR-015, FR-018~FR-019 | **Research**: R-12, R-13

모두 색인 진입점 설정의 `DATABASE_URL`(관리 연결)을 쓴다. 질의 역할(`qk_query`)로는 실행할 수 없다. 출력과 오류에 질문 원문(`export` 파일 제외), 사용자 식별자, 연결 주소를 쓰지 않는다.
종료 코드: 0 성공, 2 설정·인자 오류, 4 저장소 사용 불가.

## `qk-index queries report --since YYYY-MM-DD --until YYYY-MM-DD [--json]`

- 기간은 UTC 날짜, `until` 포함. 사람용 표 또는 한 줄 JSON.
- 항목(spec FR-018): `records`, `by_status`, `by_failure`, `first_response_ms {p50,p95}`, `total_ms {p50,p95}`, `private_ratio`, `feedback {up,down,anonymous}`, `rated_ratio`, `consented`,
  `neurons {measured, estimated}`, `answer_usage_by_day`(기간의 `qk.generation_usage_today` 값), `index_versions {id: n}`, `models {id: n}`, `prompt_versions {id: n}`.
- 조건: `period`, `sample_size`, `measurement_boundary` = "질의 서비스가 요청을 받은 때부터. Worker 서명 검사·중계 구간 제외", `relay_failures_note` = "Worker 대체 응답은 Workers 로그의 relay_failed 줄로 센다".
- `QK_QUERY_TEXT_RETAIN_UNTIL`이 지났고 원문 기록이 1건 이상이면 `warnings`에 삭제 필요를 넣는다.

## `qk-index queries export --out <파일> [--all]`

- 기본은 👎가 1건 이상인 질의의 원문 기록만, `--all`은 원문 기록 전부.
- JSON Lines, 한 줄: `run_id`, `received_date`, `question`, `context_chunk_ids`, `context_block_sizes`, `cited_blocks`, `index_version`, `feedback {up, down}`. 식별자·답변·출처 제목·링크 없음.
- `--out`이 저장소 작업 트리 안(현재 디렉터리에서 `git rev-parse --show-toplevel`로 찾은 경로 아래)이면 종료 코드 2. 파일이 있으면 덮어쓰지 않고 2. 파일 권한 `0600`.
- 표준 출력에는 건수와 안내만: "저장소에 커밋하지 마세요. 평가 세트로 옮길 때 개인 정보와 비공개 문서 원문을 지우세요. 원문 기록을 지울 때 이 파일도 지우세요."

## `qk-index queries erase-user [--confirm]`

- Discord 사용자 식별자를 표준 입력 한 줄로 받는다(17~20자리 숫자가 아니면 2). 인자나 환경 변수로 받지 않는다.
- `--confirm` 없으면 지울 원문 수, 비울 질의 기록 수, 비울 평가 수만 출력하고 바꾸지 않는다.
- `--confirm`이면 data-model 3.3을 한 트랜잭션으로 실행하고 같은 세 수를 출력한다. 다시 실행하면 세 수가 0이다.
- 안내: "질의 서비스 메모리의 원문 대기(최대 1시간)는 이 명령이 지우지 못합니다. 1시간 뒤 다시 실행하거나 질의 서비스를 다시 시작하세요."

## `qk-index queries erase-texts [--confirm]`

- 원문 기록 전체. `--confirm` 없으면 건수만. 질의 기록·평가는 남는다. 실행 기록에 `kind = all_texts`.
- 안내에 내보낸 파일도 지우라는 문장을 붙인다.

## `qk-query register-commands` (기존, 변경)

- 등록 목록에 `/sources`(contracts/discord-components.md 4절)를 더한다. 전체 덮어쓰기라 다시 실행해도 결과가 같다.
