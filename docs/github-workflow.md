# Jira와 GitHub 작업 연결

기능명세서는 요구 동작을, Jira 스프린트 이슈는 이번 주에 검증할 산출물을 관리한다. GitHub Issue·PR은 구현 범위와 코드·검증 증거를 연결한다.

팀 작업은 Jira `SCRUM`(Qello) 프로젝트에서, 팀 문서는 Confluence `SCRUM` 스페이스에서 관리한다. 2026-10-17에 ClickUp에서 이관했다(Confluence `Qello 마이그레이션 검증 기록`). 이관된 이슈에는 `clickup-migrated` 레이블과 원본 ClickUp ID 레이블이 붙어 있다.

## 계획과 Issue

- 주간 계획에서 합의한 작업만 파트별 Jira 스프린트(`Backend·Sprint N`, `Android·Sprint N`)에 넣는다. 담당자·기한·우선순위·상태는 Jira 기본 필드로 관리한다.
- 제목은 `[기능명세서 ID] 이번 주에 끝낼 산출물`로 쓴다. 명세가 없는 도구·기술부채 작업은 명세 입력에 해당 없음과 사유를 남긴다.
- GitHub Issue가 필요하면 Qello Knowledge 작업 폼을 사용한다. Jira 상위 이슈 키(기본 `SCRUM-42`), 명세 ID·링크, 팀 주기 `QELLO-SYYYY-Www`를 입력한다. Issue를 열면 Jira 하위 작업이 자동으로 생긴다(아래 "Issue를 열면 생기는 Jira 하위 작업").
- 팀 주기 ID는 사람이 읽는 표기다. Jira 이슈 키와 스프린트를 대신하지 않는다.
- `feature`, `bug`, `tech-debt`, `research`는 작업 종류이고 Jira 레이블로 붙인다. 파트는 `team-backend`·`team-android` 레이블로 구분한다. 상태·우선순위 레이블은 만들지 않는다. 이 폼은 GitHub 라벨을 자동 생성하거나 동기화하지 않는다.
- Android·Backend는 별도 이슈로 만들고 같은 명세 ID를 연결한다. 보드에는 복제하지 않고 스프린트·레이블 필터로 조회한다.
- 하위 작업(Subtask)은 담당자 또는 완료 조건이 다른 독립 산출물에만 만든다. 구현·리뷰·테스트 순서는 체크리스트로 관리한다.

## Issue를 열면 생기는 Jira 하위 작업

`.github/workflows/jira-subtask.yml`이 작업 폼으로 연 Issue마다 `scripts/jira_subtask.py`를 실행한다. 저장소 소유자·멤버·협업자가 연 Issue만 처리한다.

- 폼의 Jira 상위 이슈 아래에 하위 작업을 만든다. 요약은 Issue 제목, 레이블은 작업 종류와 파트(`team-backend`), 설명은 GitHub Issue URL과 폼의 명세·스프린트·산출물·완료 조건이다. 담당자는 사람이 정한다.
- 하위 작업은 상위 이슈의 스프린트를 따른다. 상위 이슈가 활성 스프린트에 없으면 하위 작업은 만들고 Issue 댓글로 알린다. 스프린트는 자동으로 옮기지 않는다. 주간 계획에서 상위 이슈를 활성 스프린트로 옮기면 하위 작업도 함께 옮겨진다.
- 만든 뒤 Issue에 Jira 키와 권장 브랜치 이름을 댓글로 남긴다. 그 댓글이 있거나 폼의 "기존 Jira 이슈 키"를 채웠으면 다시 만들지 않는다.
- 상위 키가 틀렸거나 API 호출이 실패하면 실패 댓글을 남긴다. 고친 뒤 Actions의 `Jira subtask` 워크플로를 Issue 번호로 수동 실행한다. Issue 본문을 고치는 것만으로는 다시 실행되지 않는다.

필요한 저장소 Secret은 `JIRA_BASE_URL`(Jira 사이트 주소), `JIRA_USER_EMAIL`, `JIRA_API_TOKEN`(그 계정의 Atlassian API 토큰)이다. 토큰 발급과 등록은 사람이 하고 값은 저장소·Issue·대화에 남기지 않는다. 선택 저장소 변수 `JIRA_PROJECT_KEY`(기본 `SCRUM`)와 `JIRA_PART_LABEL`(기본 `team-backend`)로 기본값을 바꿀 수 있다. 하위 작업의 보고자는 토큰 계정이 된다.

실제 호출 없이 만들 내용을 보려면 `python scripts/jira_subtask.py --dry-run --event tests/fixtures/issue_opened.json`을 실행한다. 단위 테스트는 `python -m unittest discover -s tests -v`다.

## 브랜치·PR과 Jira 연결

2026-10-18에 GitHub for Jira 앱으로 `Qello-Labs` org를 Jira에 연결했다. 브랜치 이름에 Jira 이슈 키가 있으면 그 브랜치와 브랜치에서 연 PR이 이슈의 개발 패널에 표시된다. 앱 설정과 연결할 저장소 범위는 Jira 사이트 관리자가 바꾼다.

| 대상 | 형식 | 예 |
| --- | --- | --- |
| 브랜치 | `<type>/SCRUM-<번호>-gh-<번호>-<short-slug>`. GitHub Issue가 없으면 `<type>/SCRUM-<번호>-<short-slug>` | `chore/SCRUM-91-gh-22-jira-integration` |
| PR 제목 | `<type>: <한국어 요약>`. Jira 키는 넣지 않는다 | `chore: 작업 연결 규칙을 ClickUp에서 Jira로 전환` |
| 커밋 | `<type>(<scope>): <summary> (#<GitHub Issue 번호>)`. Jira 키와 스프린트 ID는 넣지 않는다 | `docs(harness): rewrite work linkage for Jira (#22)` |

Jira 이슈 키는 대문자로 쓴다. 키가 소문자이거나 다른 글자와 붙어 있으면 연결되지 않는다.

## PR과 검증

1. 저장소의 커밋 규칙을 따른다. 커밋은 Conventional Commits 형태를 사용하며, GitHub Issue가 있으면 번호를 연결한다.
2. PR에 Jira 이슈 URL과 명세 ID·링크를 입력한다. GitHub Issue가 있으면 `Closes #번호`로 연결하고 없으면 해당 행을 제거한다.
3. 관찰할 완료 조건 1~3개를 `확인한 것 | 결과` 표로 적고 증빙 링크는 결과 칸에 붙인다. 테스트나 측정을 하지 않았다면 미실행과 이유를 적는다. 본문 작성 규칙은 `.claude/skills/harness-pr/references/writing-style.md`를 따른다.
4. 품질·시간·비용 수치를 적을 때 데이터·모델·질문 세트·표본 수 등 조건을 함께 남긴다. 후보 생성·측정 결과·사람의 검토·실제 반영을 구분한다.
5. Jira 이슈 개발 패널에 PR이 보이는지 확인한다. 보이지 않으면(앱 미연결, 키 누락) Jira 이슈 설명에 PR URL을 붙인다. 리뷰어가 양쪽 링크를 확인한다.
6. 데일리에는 상태·막힘을 갱신한다. 주간 리뷰에서 완료 조건과 증빙을 확인한 뒤 Jira 이슈를 완료로 바꾼다. PR 병합 자체는 완료 판정이 아니다. 병합으로 이슈 상태가 자동으로 바뀌는 Jira 자동화는 쓰지 않는다.

새 팀 주기를 시작하면 파트별 Jira 스프린트를 만들고 합의한 이슈만 옮긴다. RAG 작업은 상위 이슈 `SCRUM-42`(팀 RAG 구축)의 하위 작업으로 만든다. 다른 상위 이슈가 필요하면 팀이 합의해 정하며, 이 문서가 임의로 정하지 않는다.

## 템플릿 적용

템플릿은 기본 브랜치에 반영된 뒤 신규 Issue·PR 작성에 사용된다. 기존 본문은 자동으로 변경되지 않는다. Issue Form의 필수 입력은 빈 값 누락을 줄일 뿐 키 형식·ID 일치·증빙의 정확성을 강제하지 않으므로 리뷰에서 확인한다.
