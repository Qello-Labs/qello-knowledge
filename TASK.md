# Task Contract: 로드맵 진행 상태 표시와 작업 설명 Skill

> Generated at: `2026-10-10`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- ClickUp 작업 ID / URL: 해당 없음: 하네스·문서 운영 작업이라 WBS 작업이 아님(#9 Codex 하네스와 같은 예외)
- 기능명세서 ID / 링크: 해당 없음: 명세 백로그 대상이 아닌 저장소 운영 도구
- 팀 스프린트 ID: `QELLO-S2026-W41`
- GitHub Issue: `#19`
- Branch: `chore/gh-19-roadmap-status-explain`
- Base branch: `main`

## Objective

- 로드맵에서 어떤 WBS 작업이 끝났고 진행 중인지 한눈에 보이게 한다.
- 다른 팀원이 WBS 번호나 명세 ID 하나로 그 작업의 목적, 선행·후행, 산출물, 완료 조건, 진행 이력, 시작 방법을
  자세히 설명받을 수 있게 한다.

## Scope

- `docs/sdd/roadmap.md`: 3절 단계 표에 `상태` 열, 2절 표에 `진행` 열, 상태 범례를 추가하고 1행의 상태 관리 문구를 고친다.
- `scripts/roadmap_status.py`: GitHub Issue 제목의 `(WBS x.y)`로 상태를 계산해 로드맵 표시를 확인·갱신한다. GitHub는 읽기만 한다.
- `.claude/skills/roadmap-explain/SKILL.md`, `.agents/skills/roadmap-explain/SKILL.md`: ID를 받아 작업을 설명하는 읽기 전용 Skill.
- `CLAUDE.md`, `CODEX.md`: 프로젝트 Skill 표에 `roadmap-explain`을 등록한다.
- `README.md`: 로드맵 진행 상태 보기와 `roadmap-explain` 사용법을 짧게 적는다.

## Explicit exclusions

- `AGENTS.md`, `.claude/settings.json`, 훅 수정.
- WBS 보드(claude.ai artifact), ClickUp 쓰기. GitHub 쓰기는 이 작업의 Issue 생성(사용자 요청)과 PR만 한다.
- 로드맵의 작업 정의(WBS 번호, 선행, 크기, 산출물) 변경. 상태 표시만 더한다.
- 0.9 작업 브랜치(`docs/gh-18-adr-decisions`)의 변경.
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문은 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: 해당 없음. GitHub Issue 목록은 `gh` CLI로 읽기만 한다. 색인 대상 추가가 아니다.
- 외부 API로 보내는 데이터: 해당 없음
- 예상 임베딩·생성 호출량과 무료 한도 대비: 0 Neurons
- 인덱스 버전 변경: 없음

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `docs/sdd/roadmap.md` | 확인 필요 | 사람 리뷰 |
| `scripts/roadmap_status.py` | 확인 필요 | 사람 리뷰 |
| `.claude/skills/roadmap-explain/`, `.agents/skills/roadmap-explain/`, `CLAUDE.md`, `CODEX.md` | 확인 필요 | 사람 승인(AGENTS.md 4절) |

## Existing user-owned changes

- 2026-10-10 `origin/main`(`a4c7be0`)에서 워크트리 생성 시 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
python scripts/roadmap_status.py          # 표시가 최신이면 종료 코드 0
python scripts/roadmap_status.py --write  # 두 번째 실행에서 변경 0건이어야 한다(멱등)
```

## Completion criteria

- 로드맵 3절 모든 WBS 행에 상태가 있고, `python scripts/roadmap_status.py`가 GitHub Issue 상태와 일치한다고 보고한다.
- `/roadmap-explain 1.5`와 `/roadmap-explain QK-ING-002`가 같은 작업을 출처가 붙은 설명으로 보여 준다. 사람이 실행해 확인한다.

## Decisions

- 2026-10-10 사용자 요청: 로드맵에 완료 체크 표시, ID로 작업을 자세히 설명하는 Skill. 별도 워크트리에서 작업한다.
- 2026-10-10 사용자 결정: 로드맵 `✅`는 관련 Issue가 완료로 닫히면 표시한다. ClickUp 완료 판정(AGENTS.md 5절)과는 별개라고 로드맵에 적는다.
- 2026-10-10 사용자 결정: Issue가 없는 0.1·0.7·0.8은 `⬜`로 둔다.
- 2026-10-10 사용자 결정: GitHub Issue를 만들고, `CLAUDE.md`·`CODEX.md` 프로젝트 Skill 표에 `roadmap-explain`을 등록한다.
