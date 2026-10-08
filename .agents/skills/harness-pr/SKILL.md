---
name: harness-pr
description: 로컬 검증을 실행하고 PR 옵션을 질문으로 정한 뒤, ClickUp 연결 PR 템플릿을 채운 초안을 보여주고 승인 후 push와 PR 생성까지 수행한다. "PR 올려줘", "PR 만들어줘", "풀리퀘 생성" 요청에 사용한다.
---

# Pull Request

Claude Code판(`.claude/skills/harness-pr`)과 절차가 같고 Codex 도구에 맞춘 부분만 다르다. 절차를 바꾸면 두 Skill을 함께 고친다.

브랜치 작업을 검증 → 초안 → push → PR 생성 → ClickUp 역링크 안내 순으로 마무리한다.
`AGENTS.md` 5절(커밋과 PR)과 7절(완료 전 검증), `docs/github-workflow.md`의 실행 절차다.

참조: `references/writing-style.md` — PR 본문 문체 규칙과 금지 표현

Codex 샌드박스는 네트워크를 막고 `.git`을 읽기 전용으로 둔다. `git fetch`, `gh pr status`, `gh issue view`,
`git rebase`, `git push`, `gh pr create`는 샌드박스 밖 실행 승인이 필요하다. 승인 요청에 나온 명령이 이 절차와
같은지 확인한다. 초안 승인과 명령 실행 승인은 별개다.

## 0. 컨텍스트 수집

```bash
git branch --show-current
git status --short
git fetch origin main
git log origin/main..HEAD --oneline
git diff origin/main...HEAD --stat
gh pr status
```

- `main`에서는 PR을 만들지 않는다.
- 이미 열린 PR이 있으면 새로 만들지 않고 "push만 하고 기존 PR 갱신"을 제안한다.
- 미커밋 변경이 있으면 알리고 `$harness-commit`으로 먼저 커밋할지 묻는다. 임의로 커밋하지 않는다.
- 커밋이 하나도 없으면 중단한다.
- `TASK.md`에서 ClickUp 작업 URL, 기능명세서 ID, 팀 스프린트 ID, 완료 조건을 읽는다.
  비어 있으면 추측하지 않고 사용자에게 묻는다.
- 브랜치에 `gh-<번호>`가 있으면 `gh issue view <번호> --json title,body,url`로 Issue를 함께 읽는다.

## 0.5 최신화

```bash
git rebase origin/main
```

- 충돌이 나면 **여기서 멈춘다.** 충돌 파일 목록을 보고하고 사용자에게 해결을 요청한다.
  사용자 지시 없이 충돌을 해결하거나 `git rebase --continue`를 대신 실행하지 않는다.
- 판단이 서지 않으면 `git rebase --abort`를 제안한다.

## 1. 로컬 검증

PR을 만들기 전에 반드시 실행한다.

```bash
python scripts/preflight.py
git diff --check origin/main...HEAD
```

`pyproject.toml`에 테스트 명령이 있으면 함께 실행한다. `TASK.md`의 인덱스 버전 변경이 "없음"이 아니거나
검색·생성 코드가 바뀌었으면 평가 보고서(`templates/eval-report.md`)가 있는지 확인한다.

실패하면 **PR을 만들지 않고 멈춘다.** 실패 로그를 보고하고 지시를 받는다. 사용자가 검증을 건너뛰기로
결정하면 그 사실과 남은 위험을 PR 본문 "검증 실행"에 적는다. 실행하지 않은 검증을 통과로 쓰지 않는다.

## 2. 옵션 질문

한 메시지로 한 번에 묻고 답을 받을 때까지 진행하지 않는다.

1. **PR 상태** — Ready for review(기본) / Draft
2. **리뷰어** — 저장소 협업자 중 선택 / 지정 안 함. 리뷰어를 저장소에 고정하지 않는다.

## 3. 초안 제시

생성 전에 제목과 본문 전체를 보여주고 승인을 받는다.

**제목** — `<type>: <summary>`

- `type`은 브랜치 prefix와 같게 쓴다. 제목에는 scope를 쓰지 않는다.
- summary는 한국어 명사형으로 브랜치 전체 작업을 한 줄로 요약한다.
- 이 저장소에는 제목 형식 검사기가 없다. 형식은 리뷰에서 확인한다.

**본문** — `.github/PULL_REQUEST_TEMPLATE.md`의 구조를 그대로 채운다.

- ClickUp·기능명세서 연결: `TASK.md`의 값을 옮긴다. 명세가 없으면 `해당 없음: 사유`를 쓴다.
- GitHub Issue: 있으면 `Closes #<번호>`, 없으면 그 행을 지우고 해당 없음으로 쓴다.
- 변경 내용: 커밋 단위로 무엇을 왜 했는지 쓴다. 자료원, 모델, 데이터 스키마, 외부 호출 비용 영향을 빠뜨리지 않는다.
- 완료 조건·검증 증빙: `TASK.md` 완료 조건 1~3개를 옮기고 결과를 통과 / 실패 / 미실행으로 구분한다.
- 검증 실행: 1단계에서 실행한 명령과 결과를 그대로 쓴다. 품질·시간·비용 수치는 데이터 버전, 질문 세트, 모델,
  표본 수, 측정 조건과 함께 쓴다.
- 위험·복구: 인덱스 버전을 바꿨다면 이전 버전으로 되돌리는 방법을 쓴다.
- 리뷰 확인 체크박스는 **실제로 한 것만** 체크한다. ClickUp 역링크 항목은 5단계 이후에만 체크할 수 있으므로
  초안에서는 비워 둔다.

본문을 쓰기 전에 `references/writing-style.md`를 읽고, 사용자에게 보여주기 전에 그 문서의 점검 목록을 통과시킨다.

## 4. push와 생성

```bash
git push -u origin <브랜치>
```

0.5 단계에서 이미 push된 브랜치를 rebase했다면 non-fast-forward 거부가 정상이다. 그 경우에만 다음을 쓴다.

```bash
git push --force-with-lease -u origin <브랜치>
```

`main`이나 다른 사람과 공유하는 브랜치에는 쓰지 않는다. 그 밖의 이유로 push가 거부되면 원인을 확인하고 보고한다.

```bash
gh pr create --base main --title "<제목>" --body-file <초안파일>
# Draft이면 --draft, 리뷰어를 정했으면 --reviewer <id>
```

초안 파일은 저장소 밖 임시 디렉터리(`mktemp -d`로 만든 곳)에 쓰고 저장소에 남기지 않는다.

## 5. ClickUp 역링크

`docs/github-workflow.md` 5단계에 따라 ClickUp 작업 설명에 PR URL을 붙여야 한다. 이 Skill은 ClickUp에 쓰지 않는다.
PR URL을 보여주고 사용자에게 붙여 달라고 요청한다. 사용자가 확인하면 PR 본문의 해당 체크박스를 갱신할지 묻는다.

## 6. 완료 보고

PR URL, 제목, Draft 여부, 리뷰어, 실행한 검증과 결과, CI 상태, ClickUp 역링크 여부를 보고한다.
실행하지 못한 검증은 이유와 남은 위험을 함께 적는다. 리뷰가 필요하면 `$harness-review`를 제안한다.
머지와 ClickUp 완료 처리는 사람이 한다.

## 금지

- 승인 없이 push하거나 PR을 만들지 않는다.
- 검증 실패를 숨기거나 실행하지 않은 검증을 통과로 쓰지 않는다.
- 일반 force push, `main` 직접 push, PR 자동 머지를 하지 않는다.
- PR 병합을 ClickUp 완료로 처리하지 않는다.
- PR 본문에 `.env` 값, 토큰, DB 연결 정보, 비공개 원문, 민감한 질의 원문을 쓰지 않는다.
