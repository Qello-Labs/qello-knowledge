# Task Contract: WBS 0.10 AGENTS.md 자료원 목록 수정

> Generated at: `2026-10-07`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- ClickUp 작업 ID / URL: 해당 없음: 초기 세팅 단계 예외. 진행 상태는 WBS 보드 0.10에서 관리
- 기능명세서 ID / 링크: 해당 없음: Phase 0 준비 작업(WBS 0.10)이라 명세 백로그 대상이 아님. 작업 정의는 `docs/sdd/roadmap.md` 3절
- 팀 스프린트 ID: `QELLO-S2026-W41`
- GitHub Issue: `#5`
- Branch: `docs/gh-5-agents-source-list`
- Base branch: `main`

## Objective

- 텍스트 자료원을 Notion에서 ClickUp으로, 대화 창구를 Discord 봇으로 옮긴 결정을 `AGENTS.md`와 `CLAUDE.md`에 반영한다.

## Scope

- `AGENTS.md` 3.1 색인 대상: Notion을 빼고 ClickUp Docs·Tasks를 넣는다. Notion 문서는 색인하지 않는다고 명시한다.
- `AGENTS.md` 6절 민감정보: 토큰 예시에 ClickUp 토큰과 Discord 봇 토큰을 추가한다.
- `AGENTS.md` 9절 금지 행위: 원본 자료원 목록에 ClickUp을 추가한다.
- `CLAUDE.md` Claude Code 명령 제한: MCP 쓰기 제한 대상 자료원에 ClickUp을 추가한다.

## Explicit exclusions

- `.claude/**` 수정(Skill 예시 문구 포함)
- ClickUp 자료원의 데이터 처리 정책 결정 기록 작성(AGENTS.md 3.1)
- 수집·색인 코드 작성, 원본 자료원(ClickUp, Notion, GitHub, Figma)에 쓰기
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
| `AGENTS.md` | 확인 필요 | 사람 리뷰(AGENTS.md 4절 승인 필요) |
| `CLAUDE.md` | 확인 필요 | 사람 리뷰(AGENTS.md 4절 승인 필요) |
| `TASK.md` | 확인 필요 | 사람 리뷰 |

## Existing user-owned changes

- 2026-10-07 워크트리 생성 시 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
```

## Completion criteria

- `AGENTS.md` 3.1 색인 대상에 Notion이 없고 ClickUp Docs·Tasks가 있다. diff로 확인한다.
- 6절 토큰 예시에 ClickUp 토큰과 Discord 봇 토큰이, 9절 원본 자료원 목록과 `CLAUDE.md` MCP 쓰기 제한에 ClickUp이 있다. diff로 확인한다.
- 변경 범위와 문구를 사람이 승인했다(AGENTS.md 4절). PR 리뷰 승인으로 확인한다.

## Decisions

- 2026-10-07 사용자 확인: 선행 작업 WBS 0.1 완료.
- 2026-10-07 사용자 결정: 0.2(#3)처럼 초기 세팅 단계 예외로 ClickUp 작업 없이 진행한다. 진행 상태는 WBS 보드 0.10에서 관리한다.
- 2026-10-07 사용자 결정: Issue #5를 새로 만들고 별도 워크트리에서 작업한다.
- 2026-10-07 사용자 승인: `AGENTS.md` 3.1·6절·9절 세 곳의 변경 문구를 승인했다. Notion 원본은 아직 남아 있으므로 6절 토큰 예시와 9절 쓰기 금지 목록에서는 빼지 않는다.
- 2026-10-07 사용자 승인: `CLAUDE.md` 56행 MCP 쓰기 제한 문구에 ClickUp을 추가한다. `.claude/skills/harness-commit/references/splitting-rules.md`의 자료원 예시는 바꾸지 않는다.
- 2026-10-07 사용자 요청: PR #4 병합 뒤 생긴 `TASK.md` 충돌을 이 브랜치의 0.10 계약으로 대체해 해결한다. 0.2 계약은 `main` 이력(`90d883d`)에 남는다.
