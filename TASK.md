# Task Contract: Codex PR 초안 요약 Skill(pr-draft-summary) 추가

> Generated at: `2026-10-19`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-42` / https://tkv123.atlassian.net/browse/SCRUM-42
- 기능명세서 ID / 링크: 해당 없음: 하네스(에이전트 작업 규칙) 문서 작업이고 제품 기능이 아니다
- 팀 스프린트 ID: `QELLO-S2026-W43`
- GitHub Issue: 해당 없음
- Branch: `docs/SCRUM-42-pr-draft-summary`
- Base branch: `main`

## Objective

- PR 제목·본문을 실제 diff에서 간결하고 정확하게 쓰는 Codex Skill `pr-draft-summary`를 추가하고, 구현·검증 뒤
  이 Skill을 반드시 쓰도록 `CODEX.md`에 규칙을 넣는다.

## Scope

- `.agents/skills/pr-draft-summary/SKILL.md` 새로 작성. 사용자가 준 원문(PR Draft Summary)을 이 저장소 규칙에 맞춘다.
  - 한국어 합쇼체로 쓴다. 첫 문단은 "이 PR은 ~합니다"로 목적과 동작 변화를 쓴다.
  - `AGENTS.md` 5·7·8절과 PR 템플릿이 요구하는 완료 조건 표와 체크박스는 유지하되 간결하게 쓴다. 테스트 파일은 나열하지 않는다.
  - 본문 상한 3,000자는 유지하고, 기본은 필요한 만큼만 쓴다.
- `CODEX.md`: 프로젝트 Skill 표에 `$pr-draft-summary` 행 추가, "Skill 의무 사용" 절 추가.
- `.claude/skills/pr-draft-summary/SKILL.md` 새로 작성. Codex판과 같은 절차로, 호출 문법(`/harness-pr`)과 PR 작성 규칙 참조 경로만 바꾼다.
- `CLAUDE.md`: 프로젝트 Skill 표에 `/pr-draft-summary` 행 추가, "Skill 의무 사용" 절 추가.
- `CODEX.md`의 두 벌 동기화 안내, `docs/harness/OVERVIEW.md` 대응표에 `pr-draft-summary` 행 추가.
- `TASK.md`(이 파일).

## Explicit exclusions

- `AGENTS.md`, `.github/PULL_REQUEST_TEMPLATE.md` 수정. `CLAUDE.md`와 `.claude/**`는 위 범위의 `pr-draft-summary` 추가만 한다.
- `.agents/skills/harness-pr/**`와 `.claude/skills/harness-pr/**` 수정(두 벌 동기화 대상이라 이번에 건드리지 않는다).
- 사용자 개인 Skill 저장소 수정.
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문은 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: 해당 없음
- 외부 API로 보내는 데이터: 해당 없음
- 예상 임베딩·생성 호출량과 무료 한도 대비: 해당 없음
- 인덱스 버전 변경: 없음

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `.agents/skills/pr-draft-summary/` | 확인 필요 | 사람 리뷰 |
| `CODEX.md` | 확인 필요 | 사람 리뷰 |
| `.claude/skills/pr-draft-summary/`, `CLAUDE.md`, `docs/harness/OVERVIEW.md` | 확인 필요 | 사람 리뷰 |
| `TASK.md` | 확인 필요 | 사람 리뷰 |

## Existing user-owned changes

- 2026-10-19 `origin/main`에서 브랜치 생성 시 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
```

## Completion criteria

- `.agents/skills/pr-draft-summary/SKILL.md`가 frontmatter(`name`, `description`)를 갖고, 원문의 목적·수집·분석·작성 제약·최종 점검을
  저장소 규칙(합쇼체, 완료 조건 표·체크박스, 3,000자 상한)과 충돌 없이 담는다 — 문서 리뷰
- `CODEX.md`가 `$pr-draft-summary`를 프로젝트 Skill 표와 의무 사용 규칙에 올리고, 초안 생성이 브랜치·커밋·push·PR 생성 권한을 주지 않는다고 적는다 — 문서 리뷰
- `.claude/skills/pr-draft-summary/SKILL.md`가 Codex판과 호출 문법·참조 경로만 다르고, `CLAUDE.md`가 `/pr-draft-summary`를 Skill 표와 의무 사용 규칙에 올린다 — 문서 리뷰

## Decisions

- 2026-10-19 사용자 결정: PR 작성 원칙은 qello 저장소 `.agents/skills`(Codex)에 `pr-draft-summary`로 둔다. 사용자 개인 Skill과 `.claude` 쪽은 고치지 않는다.
- 2026-10-19 사용자 결정: 한국어 합쇼체 유지, 완료 조건 표·템플릿 체크박스 유지(간결하게), 3,000자 상한 유지.
- 2026-10-19 사용자 결정: Jira 이슈는 `SCRUM-42`(팀 RAG 구축 상위 이슈)를 쓴다. GitHub Issue는 없다.
- 2026-10-19 사실: `CODEX.md`는 공통 규칙을 바꾸면 `CLAUDE.md`와 함께 고치라고 한다. 이번 의무 규칙은 Codex 전용 Skill을 가리키므로
  `CLAUDE.md`에는 넣지 않는다. Claude Code의 PR 작성은 계속 `.claude/skills/harness-pr`을 따른다.
- 2026-10-20 사용자 결정: `pr-draft-summary`를 Claude Code에도 적용한다. `.claude/skills/pr-draft-summary`를 추가하고 `CLAUDE.md`에 의무 사용 규칙을 넣는다.
  위 2026-10-19 "`.claude` 쪽은 고치지 않는다"와 "`CLAUDE.md`에는 넣지 않는다" 결정을 대체한다. `harness-pr` 두 벌은 계속 고치지 않는다.
