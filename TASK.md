# Task Contract: #70 출력 가림 주소 패턴의 한글 인접 주소 누락 수정

> Generated at: `2026-10-27`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: 해당 없음: 2026-10-27 사용자 결정으로 Jira 없이 진행하는 예외 작업
- 기능명세서 ID / 링크: `QK-SEC-001` / `specs/QK-SEC-001-security-filter/`(주소 가림 구현 결함 수정. 명세 요구사항은 바꾸지 않는다)
- 팀 스프린트 ID: 해당 없음: Jira 없이 진행하는 예외 작업
- GitHub Issue: `#70`
- Branch: `fix/gh-70-redact-hangul-boundary`
- Base branch: `main`. 2026-10-27 `origin/main` `5567346`(#75 병합, #71 포함)에서 분기했다

## Objective

- 출력 가림의 주소 패턴(`src/qello_knowledge/domain/redact.py`)이 한글 바로 앞·뒤에 붙은 주소도 가리게 한다.
- 주소 정책 버전 변경이 보안 규칙 버전·매일 동기화·색인 제외에 주는 영향을 기록한다.

## Scope

- `src/qello_knowledge/domain/redact.py`: `SCHEME_URL`·`HOST_PORT`·`DOTTED_NAME`의 경계에서 `\b`·`\w`를 ASCII 단어 문자(`[A-Za-z0-9_]`) 기준으로 바꾼다. 점·하이픈 조건과 나머지 패턴은 그대로 둔다.
  `ADDRESS_POLICY_VERSION`을 `address-v4` → `address-v5`로 올린다
- `tests/unit/security/test_redact.py`: 패턴마다 앞·뒤·앞뒤 한글, 앞뒤 공백, 앞뒤 ASCII 영숫자(오탐 방지) 시험을 해당 필드 종류(TEXT, PATH, LINK)별로 더한다. `IP_RUN`·`IPV4_DIGITS`도 같은 꼴로 시험한다.
  합성 주소는 시험 안에서 이어 붙여 만들고 내부 주소·도메인 꼴 리터럴을 남기지 않는다. 기존 시험과 기대값은 바꾸지 않는다
- `TASK.md`

## Explicit exclusions

- 비밀값 규칙(`secret_rules.py`) 변경, 파일 확장자 예외·공개 링크 호스트·필드 종류 판정 변경, QK-SEC-001 명세 문서 변경
- 운영 반영 실행(동기화 수동 실행, 운영 DB 조회·변경). 운영 색인 비교가 필요하면 방법과 명령을 제안만 하고 승인받는다
- `AGENTS.md`, `CLAUDE.md`, `.claude/**` 수정. 원본 자료원 쓰기
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문, 실제 주소·도메인은 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: 해당 없음
- 외부 API로 보내는 데이터: 해당 없음(로컬 시험만). 가림 함수는 외부 전송 경로가 아니라 기록·로그 출력에 쓰인다(아래 영향 조사)
- 예상 임베딩·생성 호출량과 무료 한도 대비: 0 Neurons. 병합 뒤 동기화도 재임베딩 0(아래 영향 조사)
- 인덱스 버전 변경: 없음(`iv-4c0bc4fcc642` 유지). 보안 규칙 버전은 `sec-7a0c3876a137` → `sec-6cbef40bf5f2`

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `redact.py`, `tests/unit/security/test_redact.py`, `TASK.md` | Byuntil | 사람 리뷰, 독립 검토 에이전트, 오케스트레이터 diff 검토(PR 전) |

## Existing user-owned changes

- 2026-10-27 `origin/main`(`5567346`)에서 작업 폴더 `qello-knowledge-gh70`를 만들 때 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
uv run qk-dev db up
QK_REQUIRE_LOCALDB=1 uv run pytest
node --test workers/relay/relay.test.ts
```

시험을 먼저 쓰고 지금 코드에서 실패하는 것을 확인한 뒤 고친다.

## Completion criteria

- 경계 정규식을 쓰는 세 패턴이 해당 필드 종류에서 앞·뒤·앞뒤에 한글이 붙은 주소를 가리고, 앞뒤 ASCII 영숫자 꼴의 기존 판정(오탐 방지)은 그대로다. IP 패턴은 한글 인접에서도 이미 가린다 — `pytest`
- 기존 가림·보안 시험이 기대값 변경 없이 통과하고, 주소 정책 버전이 `address-v5`다 — `pytest`, diff
- 보안 규칙 버전 변경 영향(재임베딩 0, 인덱스 버전 그대로)과 색인 제외(`identifier-address`) 영향이 PR 본문에 기록돼 있다 — 리뷰

## Decisions

- 2026-10-27 사용자 결정(오케스트레이터 지시 파일로 전달): #70은 Jira 없는 예외 작업이고 구현은 이 패널이 한다. PR 전에 오케스트레이터가 diff를 검토한다.
- 2026-10-27 사실(코드 확인, 구현 전): 영향 조사.
  - 대상: `SCHEME_URL` 앞 `\b`, `HOST_PORT` 앞 `(?<![\w.-])`와 끝 `\d{1,5}\b`, `DOTTED_NAME` 앞 `(?<![\w.-])`·뒤 `(?![\w-])`. `\w`·`\b`가 한글을 단어 문자로 본다. `IP_RUN`·`IPV4_DIGITS`는 경계가 없는 문자 집합이다.
  - 버전: `security/policy.py` `_version`의 재료에 주소 패턴 문자열·확장자·`address_policy.version`이 들어간다. 패턴이 바뀌면 `address-v5`로 올리지 않아도 보안 규칙 버전이 바뀐다. 이전 버전 올림(v2~v4)은 QK-SEC-001 tasks T069~T076에 남아 있다.
  - 동기화: #67과 같다. 규칙 버전은 인덱스 버전(`sync/keys.py`)과 `sync/decide.py` `change_reason`에 들어가지 않아 재임베딩 0이다. 매번 모든 자료를 다시 검사한다.
  - 색인 제외: `security/screen.py` `_item_secret`은 `source_id`에 주소가 있으면 `identifier-address`로 `SECRET_BLOCKED` 판정해 색인에서 내린다(본문 삭제, 20% 초과 시 본문 삭제만 보류). `github_repo_files`의 `source_id`는 경로(PATH)다.
    후보 패턴으로 이 저장소 추적 파일 868개와 대상 백엔드 로컬 복제본(2026-10-16 `main`) 추적 파일 1,681개의 경로를 PATH·TEXT로 판정해 보니 전후 차이가 0건이었다. 한글이 든 경로는 두 저장소 모두 0개다.
    안드로이드 저장소는 로컬 복제본이 없고, 그 자료원은 현재 비활성이다.
  - 사용 경로: `safe_text`·`has_unsafe`는 보안 판정 기록(`domain/security.py` `to_dict`), 색인 계획 표시(`sync/plan.py`), 동기화 보고(`sync/report.py`, `indexer/sync_cli.py`), 측정 도구(`devtools/measure.py`), `source_id` 판정(`security/screen.py`)에서만 쓰인다.
    질의 서비스·생성·Discord 답변 경로는 이 함수를 쓰지 않는다. Issue의 "답변" 영향은 맞지 않고, "로그"는 색인·동기화 쪽 기록과 로그에 해당한다. 그래서 질의 릴리스 갱신 대상이 아니다.
- 2026-10-27 사실(시험 먼저): 새 한글 인접 시험이 수정 전 코드에서 30건 실패했다(스킴 주소 앞 한글, `host:port` 앞·뒤 한글, 점 이름 앞·뒤 한글, 공개 링크의 쿼리·조각·경로).
  점 이름 뒤에 한글이 붙으면 앞부분만 가리고 마지막 이름 조각이 남았다. IP 시험은 수정 전에도 통과했다(경계 정규식이 아님).
- 2026-10-27 결정: #67의 `START`/`END`를 가져오지 않고 `redact.py`에 경계 문자 집합 `WORD`를 둔다. `HOST_PORT`·`DOTTED_NAME`의 앞 경계는 점·하이픈도 포함해 같은 상수로 쓸 수 없다.
- 2026-10-27 독립 검토(별도 에이전트, 읽기 전용): 승인 권고, blocker 없음.
  - ASCII 입력 약 33만 개를 TEXT·PATH·LINK로 비교해 옛·새 결과 차이 0. 한글 외 비ASCII(가나·한자·악센트 라틴·전각 등)도 한글과 같이 바뀐다.
  - 새로 가리는 꼴은 비ASCII 바로 뒤의 점 이름(`v1.2.3`, 파일 이름 꼴)과 `name:1`이다. 공백으로 떨어진 ASCII에서는 이미 주소로 보던 꼴이라 정책과 같다. 숫자만 있는 버전과 시각은 그대로 둔다.
  - PATH에서 확장자 뒤에 비ASCII가 붙은 파일 이름은 이제 `identifier-address`로 색인에서 빠질 수 있다. 이 저장소 경로에는 비ASCII 경로가 없다.
  - 반영: 주석을 비ASCII 전반으로 고치고 가나·한자 인접 시험을 더했다(수정 전 6건 중 5건 실패).
  - 범위 밖 발견(기존 성질, 옛·새 같음): `SCHEME_URL`이 점·하이픈 반복 긴 입력에서 길이의 제곱으로 느려진다(10만 자 약 3~4초). 가림을 두 번 적용하면 결과가 또 바뀌는 입력이 있다.
- 2026-10-27 사실(운영 비교, 사용자 승인, 읽기 전용, 0 Neurons): Bastion 세션(확인 뒤 삭제)에서 `qksync` 환경으로 `qk.artifact`의 `source_id`를 읽기 전용 세션으로 읽어 옛 패턴과 이 변경의 패턴으로 판정했다.
  서버 체크아웃은 `3a5a98e`이고 그와 `origin/main` 사이에 `redact.py`·`security/` 변경이 없어 옛 판정은 `address-v4`다. 결과: `github_repo_files` active 79개, 비ASCII(한글) 포함 0, 주소 판정 옛·새 모두 0, 추가·제거 0. 개수만 출력했다.
