# Task Contract: 작업 연결 규칙을 ClickUp에서 Jira로 전환

> Generated at: `2026-10-18`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-91` / https://tkv123.atlassian.net/browse/SCRUM-91 (상위 `SCRUM-42` 팀 RAG 구축)
- 기능명세서 ID / 링크: 해당 없음: 도구·하네스 작업이라 명세 백로그 대상이 아님
- 팀 스프린트 ID: `QELLO-S2026-W42`
- GitHub Issue: `#22`
- Branch: `chore/SCRUM-91-gh-22-jira-integration`
- Base branch: `main`

## Objective

- 팀 작업 관리가 ClickUp에서 Jira(SCRUM 프로젝트)·Confluence로 이관됐다. 저장소의 작업 게이트, Issue·PR 템플릿,
  harness Skill이 ClickUp 작업 대신 Jira 이슈를 요구하게 바꿔, 브랜치·PR이 Jira 개발 패널에 연결되게 한다.

## Scope

- 정책·진입점: `AGENTS.md` 1·5·6·8·9절의 작업 연결 문구, `CLAUDE.md`, `CODEX.md`의 작업 시작 순서·문서 선택표·명령 제한.
- 템플릿: `.github/ISSUE_TEMPLATE/work.yml`, `.github/PULL_REQUEST_TEMPLATE.md`, `templates/task-contract.md`,
  `templates/decision-record.md`, `templates/eval-report.md`.
- 문서: `docs/github-workflow.md`(Jira·GitHub 연결 절차로 다시 쓴다), `docs/harness/OVERVIEW.md`의 업무 게이트 행,
  `README.md` 문서 표, `docs/sdd/roadmap.md`의 작업 관리 문구(1행, 원칙 4, 시작 순서 8, 운영 규칙).
- Skill: `.claude/skills/`와 `.agents/skills/`의 `harness-pr`, `harness-review`, `harness-commit`, `roadmap-explain`.
- `scripts/preflight.py`: Atlassian API 토큰 패턴을 비밀값 검사에 추가한다.
- 연결 규칙: Jira 이슈 키는 브랜치 이름에만 넣는다. GitHub Issue는 유지하고 Jira 이슈와 서로 링크한다.
  커밋 메시지 형식은 바꾸지 않는다.

## Explicit exclusions

- 색인 자료원 변경. `AGENTS.md` 3.1의 색인 대상, 로드맵 Phase 2·3의 ClickUp Docs·Tasks 수집 명세(QK-ING-003·004,
  QK-CHK-002, QK-SYN-004)는 Confluence·Jira로 바꾸려면 결정 기록이 필요한 별도 작업이다(AGENTS.md 3.1).
- 과거 기록 문서의 서술: `docs/sdd/research/*.md`, `docs/sdd/clickup-writing-rules.md`, `docs/sdd/decisions/*.md`,
  로드맵 0.x 완료 행. 작성 당시의 사실이므로 고치지 않는다.
- `scripts/roadmap_status.py`의 GitHub Issue 기반 상태 계산 방식. GitHub Issue를 유지하므로 그대로 둔다.
- GitHub for Jira 앱 설치와 `Qello-Labs` org 연결. 사이트 관리자가 직접 한다(2026-10-18 완료).
- Jira 이슈 상태 변경. 사람이 요청한 경우만 한다.
- 비밀값, 토큰, `.env` 값, 계정 ID, DB 연결 주소, 비공개 원문은 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: 해당 없음. 색인 대상을 바꾸지 않는다.
- 외부 API로 보내는 데이터: 해당 없음
- 예상 임베딩·생성 호출량과 무료 한도 대비: 0 Neurons
- 인덱스 버전 변경: 없음

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `AGENTS.md`, `CLAUDE.md`, `CODEX.md`, `.claude/skills/**`, `.agents/skills/**` | 확인 필요 | 사람 승인(AGENTS.md 4절). 2026-10-18 수정 승인, diff 확인 후 커밋 |
| `.github/`, `templates/`, `docs/`, `README.md`, `scripts/preflight.py` | 확인 필요 | 사람 리뷰 |
| `TASK.md` | 확인 필요 | 사람 리뷰 |

## Existing user-owned changes

- 2026-10-18 `origin/main`(`35d2415`)에서 브랜치 생성 시 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
git grep -n -i clickup -- AGENTS.md CLAUDE.md CODEX.md README.md .github templates docs/github-workflow.md docs/harness .claude .agents   # 남은 참조는 사유가 있어야 한다
```

## Completion criteria

- 작업 게이트, Issue 폼, PR 템플릿, 템플릿, harness Skill이 ClickUp 작업 대신 Jira 이슈 키와 URL을 요구한다. 위 grep과 사람 리뷰로 확인한다.
- 이 작업의 브랜치·PR이 SCRUM-91 개발 패널에 표시된다. GitHub for Jira 설치 후 Jira 화면에서 확인한다.
- 비밀값과 계정 식별자가 없다. `python scripts/preflight.py`로 확인한다.

## Decisions

- 2026-10-18 사용자 요청: ClickUp에서 Jira로 작업 관리를 이관했으니 이슈·PR을 Jira에서 관리하도록 연동한다.
- 2026-10-18 사용자 결정: GitHub Issue는 유지하고 Jira 이슈와 함께 쓴다. 브랜치는 `<type>/SCRUM-<번호>-gh-<번호>-<slug>`다.
- 2026-10-18 사용자 결정: 커밋 메시지에는 Jira 키를 넣지 않는다.
- 2026-10-18 사용자 결정: 이 작업을 추적할 Jira 하위 작업(SCRUM-91)을 SCRUM-42 아래에 만든다.
- 2026-10-18 사용자 승인: `AGENTS.md`·`CLAUDE.md`·`CODEX.md`·`.claude/**`·`.agents/**` 수정. diff를 확인하고 커밋을 승인했다.
- 2026-10-18 사용자 확인: GitHub for Jira 앱으로 `Qello-Labs` org 연결을 마쳤다.
- 2026-10-18 사용자 요청: Confluence `스프린트 작업 연결 규칙` 페이지를 Jira 기준으로 고친다. 버전 6으로 반영했다.
- 2026-10-18 사용자 결정: PR 제목에 Jira 키를 넣지 않는다. Jira 연결은 브랜치 이름으로만 한다.
