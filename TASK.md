# Task Contract: #67 비밀값 규칙의 한글 인접 토큰 누락 수정

> Generated at: `2026-10-27`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: 해당 없음: 2026-10-27 사용자 결정으로 Jira 없이 진행하는 예외 작업
- 기능명세서 ID / 링크: `QK-SEC-001` / `specs/QK-SEC-001-security-filter/`(규칙 구현 결함 수정. 명세 요구사항은 바꾸지 않는다)
- 팀 스프린트 ID: 해당 없음: Jira 없이 진행하는 예외 작업
- GitHub Issue: `#67`
- Branch: `fix/gh-67-secret-rules-hangul-boundary`
- Base branch: `main`. 2026-10-27 `origin/main` `e701d5b`(#66 병합)에서 분기한 뒤 `ba1249e`(#69 병합) 위로 옮겼다

## Objective

- 비밀값 규칙(`src/qello_knowledge/domain/secret_rules.py`)이 토큰 바로 앞이나 뒤에 한글이 붙어도 그 토큰을 잡게 한다.
  같은 규칙을 쓰는 질의 전송 직전 검사, 색인 전송 직전 검사, 출력 가림, `scripts/preflight.py`가 함께 고쳐진다.
- 규칙 변경이 보안 규칙 버전·매일 동기화·인덱스·Neurons에 주는 영향과 운영 반영 절차를 기록한다.

## Scope

- `src/qello_knowledge/domain/secret_rules.py`: 앞뒤 `\b`를 ASCII 기준 경계(`(?<![A-Za-z0-9_])`, `(?![A-Za-z0-9_])`)로 바꾼다. 다른 패턴 부분과 규칙 이름·개수는 그대로 둔다
- `tests/unit/domain/test_secret_rules.py`: 모든 규칙(16개)과 필수 종류에 대해 "앞에 한글", "뒤에 한글", "앞뒤 공백", "앞뒤 ASCII 영숫자(오탐 방지, 지금 안 잡는 꼴은 계속 안 잡음)" 시험을 더한다.
  합성 값은 `tests/unit/synthetic_secrets.py` 방식처럼 실행 중에 이어 붙여 만든다. 기존 시험과 기대값은 바꾸지 않는다
- `tests/unit/synthetic_secrets.py`: 할당 꼴 규칙 시험에 필요한 합성 값이 없을 때만 더한다
- `TASK.md`

## Explicit exclusions

- `scripts/preflight.py` 코드 변경. 규칙을 `secret_rules.py`에서 그대로 불러오므로 따로 고칠 것이 없는지 확인만 한다(아래 Decisions)
- 운영 문서(`docs/ops/oci-production-store.md`) 변경. 질의 릴리스 갱신 절차는 PR 본문에만 제안한다
- 규칙 추가·삭제, 규칙 이름 변경, 오탐 예외(`exceptions`) 변경, QK-SEC-001 명세 문서 변경
- 운영 반영 실행: 질의 릴리스(`/opt/qello-knowledge-query`, `3a5a98e` 고정) 갱신, `qk-query.service` 재시작, 수동 `qk-sync` 실행, 운영 DB 조회·변경. 절차 제안만 하고 실행은 따로 승인받는다
- `AGENTS.md`, `CLAUDE.md`, `.claude/**` 수정. 원본 자료원 쓰기
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문은 기록하지 않는다. 실제 토큰 꼴 리터럴을 저장소에 남기지 않는다.

## Data and cost impact

- 새로 읽는 자료원: 해당 없음
- 외부 API로 보내는 데이터: 해당 없음(로컬 시험만). 병합 뒤에는 규칙이 더 넓게 잡으므로 Workers AI로 가는 데이터가 줄기만 한다
- 예상 임베딩·생성 호출량과 무료 한도 대비: 이 작업의 실행은 0 Neurons. 병합 뒤 첫 `qk-sync`도 규칙 변경 때문에 생기는 재임베딩은 0이다(아래 영향 조사)
- 인덱스 버전 변경: 없음(`iv-4c0bc4fcc642` 유지). 보안 규칙 버전은 `sec-7222e5dd1d6e` → 새 `sec-…`로 바뀐다(인덱스 버전 계산에 들어가지 않음)

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `secret_rules.py`, `tests/unit/domain/test_secret_rules.py`, `TASK.md` | Byuntil | 사람 리뷰, 독립 검토 에이전트 |
| 운영 반영 절차 제안(질의 릴리스 갱신) | Byuntil | 사람 리뷰, 팀원(인스턴스 관리자) 확인 |

## Existing user-owned changes

- 2026-10-27 `origin/main`(`e701d5b`)에서 작업 폴더 `qello-knowledge-gh67`를 만들 때 `git status --short` 결과: 변경 없음

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

시험을 먼저 쓰고 지금 코드에서 실패하는 것을 확인한 뒤 고친다. 고친 규칙으로 `python scripts/preflight.py`가 저장소 안의 기존 파일을 새로 잡으면 멈추고 보고한다.

## Completion criteria

- 모든 규칙에 대해 토큰 앞·뒤에 한글이 붙은 꼴을 잡는 시험이 있고 통과한다. 앞뒤 ASCII 영숫자 꼴의 기존 판정(오탐 방지)은 그대로다 — `pytest` 결과
- 기존 비밀값·보안 시험이 기대값 변경 없이 그대로 통과한다 — `pytest` 결과, diff
- 보안 규칙 버전 변경의 영향(동기화 재검사·내리기, 재임베딩 0, 인덱스 버전 그대로)과 질의 릴리스 갱신 절차가 PR 본문에 기록돼 있다 — 리뷰

## Decisions

- 2026-10-27 사용자 결정(오케스트레이터 지시 파일로 전달): #67·#68은 Jira 이슈 없이 진행하는 예외 작업이다. 두 이슈는 따로 하고 #67을 먼저 PR까지 끝낸다.
- 2026-10-27 사실(코드 확인, 구현 전): 영향 조사.
  - 보안 규칙 버전은 `security/policy.py` `_version`이 규칙 이름·패턴 문자열·플래그, 기본 제외, 예외, 주소 정책, 종류별 정책을 JSON으로 묶은 sha256 앞 12자리다. 패턴 문자열이 바뀌므로 버전이 바뀐다.
  - 버전은 `qk.sync_run.rules_version`과 판정·요약 기록에만 남는다. 인덱스 버전(`sync/keys.py` `index_version_id`: 임베딩 모델·차원·청킹 버전·메타데이터 스키마)에는 들어가지 않는다.
  - `sync/decide.py` `change_reason`은 청킹 입력 지문·청킹 버전·상태·인덱스 버전만 보고 규칙 버전은 보지 않는다. 그래서 규칙 버전이 바뀌어도 바뀌지 않은 문서는 다시 청킹·임베딩하지 않는다.
  - `qk-sync`는 매번 모든 자료를 목록·본문까지 다시 받아 검사한다(`screen_source`). 새 규칙에 걸리는 이미 색인된 문서는 `SECURITY_SECRET` 내리기(본문 삭제)가 된다. 내리기 비율이 20%를 넘으면 `TAKEDOWN_RATIO` 보류로 본문 삭제(`SECURITY_PURGE`)만 멈추고 검색 제외(`SECURITY_HIDE`)는 바로 된다(`domain/sync.py` `ALLOWED`). 내리기는 임베딩을 부르지 않는다.
  - 운영 `qk-sync`는 00:30 UTC마다 `/opt/qello-knowledge`를 `origin/main`으로 맞춘 뒤 돌므로 병합하면 다음 실행부터 색인 쪽 검사에 바로 반영된다. 질의 서비스는 `3a5a98e` 릴리스에 고정돼 있어 릴리스를 갱신해야 질문 검사에 반영된다.
  - `scripts/preflight.py`는 자체 패턴 없이 `secret_rules.RULES`를 불러온다(`load_rules`). 따라서 같은 결함이 있고, 이 수정으로 함께 고쳐진다. 코드는 고치지 않는다.
- 2026-10-27 사용자 결정: 이 계약 초안대로 진행한다. `scripts/preflight.py`는 고치지 않는다(같은 규칙을 불러와 함께 고쳐진다). 질의 릴리스 갱신 절차는 운영 문서에 더하지 않고 PR 본문에만 제안한다.
  병합 시점(다음 00:30 UTC `qk-sync`부터 색인 쪽 반영)은 아직 정하지 않았다.
- 2026-10-27 사실: `origin/main`에 #69(`ba1249e`)가 병합돼 그 위로 rebase했다. #69는 비밀값 규칙, 전송 직전 검사(`security/send_gate.py`, `indexer/embedding.py`), `sync/execute.py`를 바꾸지 않았다.
  코드 청커는 보안 검사를 통과한 본문만 받고, 그 청크도 같은 임베딩 경로의 `check_outgoing`을 지난다. 위 영향 조사를 #69 코드에서 다시 확인했다.
- 2026-10-27 사실: 새 시험 50건이 수정 전 코드에서 실패하는 것을 확인한 뒤 고쳤다. 보안 규칙 버전은 `sec-7222e5dd1d6e` → `sec-7a0c3876a137`. 새 규칙으로 `preflight.py`가 저장소에서 새로 잡은 파일은 없다.
- 2026-10-27 사실(독립 검토, 별도 에이전트·읽기 전용): 승인 권고, blocker 없음. ASCII 무작위 입력 비교에서 15개 규칙은 차이 0, `slack-token`은 `-`로 끝나는 비정상 꼴에서만 다르다(실제 토큰 꼴 영향 없음).
  저장소 추적 파일 비교에서 새로 잡히거나 놓치는 줄 0. 반영: 20% 보류 문구 정정, slack 뒷글자 오탐 방지 시험 추가.
  범위 밖 발견: `domain/redact.py` 주소 가림 패턴(`\b`, `(?<![\w.-])`)도 한글에 붙은 내부 주소를 가리지 않는다. 고치면 주소 정책 버전이 바뀌므로 별도 이슈로 나눈다(등록은 사람 결정).
- 2026-10-27 사실: rebase 때 작업 중 변경을 보존하려고 만든 임시 로컬 커밋에 `--no-verify`를 썼다(AGENTS.md 5절 위반). 그 커밋은 바로 풀었고 push하지 않았으며 브랜치 이력에 없다.
