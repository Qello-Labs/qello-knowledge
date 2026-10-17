# Task Contract: GitHub Issue 생성 시 Jira 하위 작업 자동 생성

> Generated at: `2026-10-18`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-93` / https://tkv123.atlassian.net/browse/SCRUM-93 (상위 `SCRUM-42` 팀 RAG 구축)
- 기능명세서 ID / 링크: 해당 없음: 도구·하네스 작업이라 명세 백로그 대상이 아님
- 팀 스프린트 ID: `QELLO-S2026-W42`
- GitHub Issue: `#25`
- Branch: `ci/SCRUM-93-gh-25-jira-subtask-sync`
- Base branch: `main`

## Objective

- Issue 폼으로 GitHub Issue를 열면 Jira SCRUM 프로젝트에 하위 작업이 자동으로 생기게 해, GitHub Issue와 Jira 작업을
  손으로 두 번 만들지 않게 한다. 하위 작업은 상위 이슈의 스프린트를 따르므로 상위 이슈가 활성 스프린트에 있으면 그 스프린트에 들어간다.

## Scope

- `.github/workflows/jira-subtask.yml`: Issue `opened`와 수동 실행(`workflow_dispatch`, Issue 번호 입력)에서 실행한다.
  저장소 소유자·멤버·협업자가 연 Issue에서만 실행한다.
- `scripts/jira_subtask.py`: 표준 라이브러리만 쓴다. Issue 폼 본문을 읽어 상위 이슈 아래 하위 작업을 만들고 GitHub Issue에 댓글을 남긴다.
  `--dry-run`은 Jira·GitHub에 쓰지 않고 만들 내용만 출력한다.
- `tests/test_jira_subtask.py`: `python -m unittest`로 도는 단위 테스트.
- `.github/ISSUE_TEMPLATE/work.yml`: "Jira 이슈 키·URL" 필수 입력을 "Jira 상위 이슈 키"(기본 `SCRUM-42`)와
  선택 입력 "기존 Jira 이슈 키"로 바꾼다.
- `docs/github-workflow.md`: 자동 생성 흐름, 필요한 Secret, 실패했을 때 할 일.

## Behavior

- 하위 작업: 요약은 GitHub Issue 제목, 레이블은 작업 종류와 파트 레이블(저장소 변수 `JIRA_PART_LABEL`, 기본 `team-backend`),
  설명에는 GitHub Issue URL, 기능명세서 ID·링크, 팀 스프린트 ID, 산출물, 완료 조건을 넣는다. 담당자는 지정하지 않는다.
- 상위 이슈가 활성 스프린트에 없으면 하위 작업은 만들고, GitHub Issue 댓글로 상위 이슈를 활성 스프린트로 옮겨 달라고 알린다. 스프린트를 옮기지 않는다.
- 상위 키가 형식에 맞지 않거나, 상위 이슈가 없거나, 하위 작업이면 만들지 않고 실패 댓글을 남긴다.
- 중복 방지: 이 워크플로가 남긴 댓글의 표식(`<!-- jira-subtask: SCRUM-<번호> -->`)이 있거나 "기존 Jira 이슈 키"가 채워져 있으면 만들지 않는다.
- 생성 댓글에 Jira 키·URL과 권장 브랜치 이름 `<type>/SCRUM-<번호>-gh-<Issue 번호>-<short-slug>`를 남긴다.

## Explicit exclusions

- Atlassian API 토큰 발급과 GitHub Secret 등록. 사람이 한다(AGENTS.md 6절, 토큰을 에이전트가 다루지 않는다).
- 담당자 자동 지정, Issue 수정·닫기·재오픈 동기화, Jira → GitHub 방향 동기화.
- 이미 열린 Issue 소급 처리. 필요하면 수동 실행으로 한 건씩 한다.
- 색인 자료원 변경, `AGENTS.md`·`CLAUDE.md`·`CODEX.md`·`.claude/**`·`.agents/**` 수정.
- 다른 세션이 쓰는 기본 작업 폴더(`docs/SCRUM-92-gh-24-phase1-first-specs` 브랜치)의 변경.

## Data and cost impact

- 새로 읽는 자료원: 해당 없음. 색인 대상이 아니다. 워크플로가 Jira 상위 이슈 한 건과 GitHub Issue 댓글을 읽는다.
- 외부 API로 보내는 데이터: GitHub Issue 제목과 폼 본문 일부를 같은 팀의 Jira SCRUM 프로젝트로 보낸다. 사람이 요청한 쓰기 자동화다.
- 예상 임베딩·생성 호출량과 무료 한도 대비: 0 Neurons. Issue 하나당 Jira API 2회(상위 조회, 생성), GitHub API 2~3회, Actions 실행 1회.
- 인덱스 버전 변경: 없음

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `.github/workflows/jira-subtask.yml`, `scripts/jira_subtask.py`, `tests/` | 확인 필요 | 사람 리뷰 |
| `.github/ISSUE_TEMPLATE/work.yml`, `docs/github-workflow.md`, `TASK.md` | 확인 필요 | 사람 리뷰 |

## Existing user-owned changes

- 2026-10-18 `origin/main`(`0abe4b4`)에서 별도 작업 폴더(`../qello-knowledge-scrum-93`)를 만들 때 `git status --short` 결과: 변경 없음.
  기본 작업 폴더에는 다른 세션의 `TASK.md` 수정과 `specs/`가 있어 건드리지 않았다.

## Validation

```bash
python scripts/preflight.py
git diff --check
python -m unittest discover -s tests -v
python scripts/jira_subtask.py --dry-run --event tests/fixtures/issue_opened.json
```

## Completion criteria

- 단위 테스트와 `--dry-run` 실행이 통과한다.
- Secret 등록 후 테스트 Issue 하나로 하위 작업이 상위 이슈 아래에 생기고 스프린트·레이블·댓글이 맞다. Jira·GitHub 화면으로 확인한다.
- 비밀값이 저장소에 없다. `python scripts/preflight.py`로 확인한다.

## Decisions

- 2026-10-18 사용자 요청: GitHub에서 Issue를 만들면 Jira에 하위 이슈로, 알맞은 스프린트에 등록되게 한다.
- 2026-10-18 사용자 결정: 상위 이슈는 폼에서 입력받고 기본값은 `SCRUM-42`다.
- 2026-10-18 사용자 결정: 상위 이슈가 활성 스프린트에 없으면 하위 작업은 만들고 경고 댓글을 남긴다.
- 2026-10-18 사용자 결정: #23 병합 후 `main`에서 시작한다(확인 시 이미 병합됨).
- 2026-10-18 사용자 결정: 이 작업용 Jira 하위 작업(SCRUM-93)과 GitHub Issue(#25)를 만든다.
- 2026-10-18 에이전트 판단: 저장소에 `pyproject.toml`이 없어 테스트 명령을 `TASK.md` Validation에만 적는다. `pyproject.toml` 도입은 QK-FND-001 범위다.
