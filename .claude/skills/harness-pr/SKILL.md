---
name: harness-pr
description: 로컬 검증, PR 옵션 질문, 본문 초안 승인, push와 PR 생성까지 진행한다. 본문은 PR 템플릿 섹션을 유지하고 표로 짧게 쓴다. "PR 올려줘", "PR 만들어줘", "풀리퀘 생성" 요청에 사용한다.
---

# Pull Request

검증 → 초안 → push → PR 생성 → ClickUp 연결 확인 순서로 진행한다.
근거 규칙은 `AGENTS.md` 5·7절과 `docs/github-workflow.md`, 본문 문체는 `references/writing-style.md`다.

## 0. 컨텍스트

`<base>`는 보통 `origin/main`이다. 아직 merge되지 않은 브랜치 위에 쌓은 stacked PR이면 그 브랜치다.

```bash
git branch --show-current
git status --short
git fetch origin
git log <base>..HEAD --oneline
git diff <base>...HEAD --stat
gh pr status
```

| 상황 | 처리 |
| --- | --- |
| `main` 브랜치 | 중단 |
| 이미 열린 PR | 새로 만들지 않고 push로 갱신할지 묻는다 |
| 미커밋 변경 | `/harness-commit`을 먼저 할지 묻는다 |
| 커밋 없음 | 중단 |

본문에 넣을 값은 아래 순서로 찾는다. 어디에도 없으면 추측하지 않고 묻는다.

1. 브랜치에 `gh-<번호>`가 있으면 `gh issue view <번호> --json title,body,url`
   - `### 기능명세서`의 첫 단어가 명세 ID다. 예: `QK-ING-002 (WBS 1.5) …`. `해당 없음`이면 `### 명세가 없는 사유`도 읽는다.
   - `### ClickUp 작업 URL`의 마지막 경로가 ClickUp task ID다.
2. `TASK.md`

## 0.5 rebase

```bash
git rebase <base>
```

충돌이 나면 멈추고 파일 목록을 보고한다. 사용자 지시 없이 충돌을 해결하거나 `git rebase --continue`를 실행하지 않는다.

## 1. 로컬 검증

```bash
python scripts/preflight.py
python scripts/sync_issue_form.py --check
python scripts/roadmap.py <명세 ID>   # 명세 ID가 있을 때
git diff --check <base>...HEAD
```

- `pyproject.toml`에 테스트 명령이 있으면 같이 실행한다.
- index version이 바뀌었거나 retrieval·generation 코드가 바뀌었으면 `templates/eval-report.md` 형식의 보고서가 있는지 확인한다.
- 실패하면 PR을 만들지 않고 로그를 보고한다. 사용자가 건너뛰기로 하면 본문에 `미실행`과 이유를 남긴다.

## 2. 옵션 질문

`AskUserQuestion`으로 한 번에 묻는다.

- PR 상태: Ready for review(기본) / Draft
- 리뷰어: 협업자 중 선택 / 지정 안 함

## 3. 초안

제목과 본문 전체를 보여 주고 승인을 받는다.

**제목**: `<type>: <summary>`. type은 브랜치 prefix와 같고 scope는 쓰지 않는다. summary는 한국어 명사형이며
기술 용어는 영어 그대로 쓴다. 예: `feat: GitHub repo loader 추가`

**본문**: `.github/PULL_REQUEST_TEMPLATE.md`의 섹션 제목·순서와 리뷰 확인 체크박스는 그대로 두고,
섹션 안은 표로 쓴다.

````markdown
## ClickUp·기능명세서 연결

| 항목 | 값 |
| --- | --- |
| ClickUp | `CU-86c1ab2xy` · [task](https://app.clickup.com/t/86c1ab2xy) |
| 기능명세서 | `QK-ING-002` · `specs/QK-ING-002-github-repo-source/spec.md` |
| Sprint | `QELLO-S2026-W41` |
| 이번 주 산출물 | GitHub repo loader |
| 관련 Android·Backend 작업 | 해당 없음 |
| Figma | 해당 없음 |

## GitHub Issue

Closes #12

## 변경 내용

| 변경 | 이유 |
| --- | --- |
| tree SHA 비교로 바뀐 파일만 수집 | 전체 재수집 시 GitHub API rate limit 초과 |
| include/exclude glob 설정 추가 | `.env`, `build/`를 색인에서 제외 |

외부 호출·비용: GitHub REST API 시간당 1회

```diff
- def sync(self): return self.fetch_all()
+ def sync(self): return self.fetch_changed(since=self.last_tree_sha)
```

## 완료 조건·검증 증빙

| 완료 조건 | 검증 | 결과 |
| --- | --- | --- |
| 변경 없는 재동기화에서 embedding 호출 0건 | `pytest tests/test_sync.py::test_noop` | 통과 |
| 실제 repo 색인 | 백엔드 repo 대상 수동 실행 | 미실행: token 미발급 |

## 검증 실행

| 명령 | 결과 |
| --- | --- |
| `python scripts/preflight.py` | 통과 |
| `pytest` | 통과(42 passed) |

## 위험·복구

| 위험 | 대응 |
| --- | --- |
| GitHub token 만료 시 sync 중단 | 실패 로그 알림, 이전 index 유지 |

복구: 이 PR의 merge commit revert
````

- ClickUp task ID는 `CU-<task-id>`로 쓴다. `#<id>`는 숫자만으로 된 ID일 때 GitHub Issue 링크로 바뀐다.
- 기능명세서에는 `specs/<명세 ID>-…/spec.md`가 있으면 그 경로를, 없으면 `docs/sdd/roadmap.md`를 코드로 쓴다.
  PR 본문의 상대 경로 링크는 PR 주소 기준으로 해석돼 깨진다. 명세가 없으면 `해당 없음`과 짧은 사유를 쓴다.
- Issue가 없으면 `GitHub Issue` 섹션에 `해당 없음`만 쓴다.
- 변경 내용은 커밋 단위로 묶되 사소한 커밋은 합친다. 자료원, 모델, 스키마, 외부 호출 비용에 영향이 있으면 표 아래에 한 줄로 쓰고, 없으면 그 줄을 뺀다.
- 코드 블록은 선택이다. 넣는 기준은 `references/writing-style.md` 5절이다.
- 검증 실행 표에는 완료 조건 표에 없는 검사만 쓴다. 실행 환경이 결과에 영향을 주면 표 아래에 한 줄로 쓴다.
- index version을 바꿨다면 위험·복구에 이전 버전으로 돌리는 방법을 쓴다.
- 체크박스는 실제로 한 것만 체크한다. ClickUp 연결 항목은 5단계 뒤에 체크한다.

보여 주기 전에 `references/writing-style.md` 7절 점검을 통과시킨다.

## 4. push와 생성

```bash
git push -u origin <브랜치>
gh pr create --base <base 브랜치> --title "<제목>" --body-file <초안 파일>
# Draft면 --draft, 리뷰어가 있으면 --reviewer <id>
```

- 0.5단계에서 이미 push된 브랜치를 rebase했다면 `git push --force-with-lease -u origin <브랜치>`만 쓴다.
  `main`이나 다른 사람과 같이 쓰는 브랜치에는 쓰지 않는다.
- 그 밖의 이유로 push가 거부되면 원인을 확인하고 보고한다.
- 초안 파일은 scratchpad에 두고 저장소에 남기지 않는다.
- stacked PR은 부모 PR이 merge된 뒤 base를 `main`으로 바꿔야 한다고 본문 `GitHub Issue` 섹션 아래에 한 줄 남긴다.

## 5. ClickUp 연결 확인

ClickUp GitHub 연동을 쓰고 있으면 `gh pr view --comments`로 ClickUp 댓글이 달렸는지 본다.
연동을 쓰지 않거나 댓글이 없으면 PR URL을 보여 주고 ClickUp task 설명에 붙여 달라고 요청한다. 이 Skill은 ClickUp에 쓰지 않는다.

## 6. 완료 보고

PR URL, 제목, Draft 여부, 리뷰어, 실행한 검증과 결과, CI 상태, ClickUp 연결 여부를 보고한다.
미실행 검증은 이유와 남은 위험을 같이 쓴다. 리뷰가 필요하면 `/harness-review`를 제안한다. merge와 ClickUp 완료 처리는 사람이 한다.

## 금지

- 승인 없이 push하거나 PR을 만들지 않는다.
- 검증 실패를 숨기거나 미실행 검증을 통과로 쓰지 않는다.
- 일반 force push, `main` 직접 push, PR 자동 merge를 하지 않는다.
- PR merge를 ClickUp 완료로 처리하지 않는다.
- 본문에 `.env` 값, token, DB 연결 정보, 비공개 원문, 민감한 query 원문을 쓰지 않는다.
