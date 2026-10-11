@AGENTS.md
@TASK.md

# Claude Code Entry Point

공통 정책은 `AGENTS.md`에서, 현재 작업의 범위와 상태는 `TASK.md`에서 가져온다.
이 파일은 Claude Code 전용 실행 규칙만 정의하며 `AGENTS.md`의 정책을 완화하지 않는다.

## 작업 시작 순서

1. `AGENTS.md`의 공통 정책을 확인한다.
2. `TASK.md`의 범위와 ClickUp 작업을 확인한다. 없으면 `templates/task-contract.md`로 초안을 만들고
   사람의 확인을 받는다.
3. 작업 유형에 맞는 Skill과 아래 문서 선택표의 해당 행만 읽는다.
4. 허용 범위와 금지 작업을 확인한 뒤 시작한다.

## 프로젝트 Skill

| Skill | 역할 |
| --- | --- |
| `/harness-commit` | 변경을 검토 목적 단위로 나눈 커밋 초안을 보여주고 승인 후 커밋 |
| `/harness-pr` | 로컬 검증, PR 초안, 승인 후 push와 PR 생성 |
| `/harness-review` | 범위, 증빙, 데이터·비용 위험 검토. 구현은 수정하지 않음 |
| `/roadmap-explain` | WBS 번호나 명세 ID로 로드맵 작업의 목적, 선행·후행, 완료 조건, 진행 이력, 이어받는 방법을 설명. 읽기 전용 |
| `/speckit-*` | GitHub Spec Kit 명세 흐름. 아래 "Spec Kit 규칙"을 따른다 |

## Spec Kit 규칙

- 명세 디렉터리는 `specs/<명세 ID>-<짧은 이름>/`이다. 예: `specs/QK-ING-002-github-repo-source/`.
  Spec Kit 기본값인 숫자 순번(`001-`)이나 타임스탬프 접두사를 쓰지 않는다.
- `/speckit-specify`는 명세 ID를 첫 단어로 받는다. 예: `/speckit-specify QK-ING-002 GitHub 저장소 파일을 수집한다`.
  직접 경로를 줄 때는 `SPECIFY_FEATURE_DIRECTORY=specs/<명세 ID>-<짧은 이름>`을 지정한다.
- 명세 ID는 `docs/sdd/roadmap.md` 4절 명세 백로그에서 가져온다. 백로그에 없는 기능이면 ID를 먼저 백로그에 추가한다.
- 위 규칙은 `.claude/hooks/speckit_spec_id.py` 훅이 강제한다. ID가 없거나, 백로그에 없거나, 같은 ID의
  디렉터리가 이미 있으면 실행을 막는다. 훅이 막으면 우회하지 말고 사용자에게 이유를 전한다.
- `.specify/memory/constitution.md`와 `AGENTS.md`가 다르면 `AGENTS.md`를 따른다.
  원칙 초안은 `docs/sdd/constitution.md`이며 `/speckit-constitution`의 입력으로 쓴다.
- 명세 디렉터리 이름과 git 브랜치 이름은 별개다. 브랜치는 `AGENTS.md` 1절 형식을 따른다.

## 문서 선택표

현재 작업에 해당하는 행만 읽는다.

| 작업 | 읽을 문서 |
| --- | --- |
| ClickUp·Issue·PR 연결 | `docs/github-workflow.md` |
| 하네스 구조와 출처 | `docs/harness/OVERVIEW.md` |
| 기술 선택·정책 결정 | `templates/decision-record.md` |
| 검색·생성 평가 | `templates/eval-report.md`, `AGENTS.md` 3.3~3.5 |
| 자료원 추가·외부 모델 변경 | `AGENTS.md` 3.1, `templates/decision-record.md` |
| 명세 작성·구현 순서 | `docs/sdd/roadmap.md`, `README.md`의 Spec Kit 사용법 |

## Claude Code 명령 제한

- `.env`, `.env.*`, `secrets/`를 읽지 않는다. `.claude/settings.json`에서 차단한다.
- 공유 DB에 `DROP`, `TRUNCATE`, 조건 없는 `DELETE`를 실행하지 않는다.
- ClickUp, Notion, GitHub, Figma 등 원본 자료원에 쓰는 MCP 도구는 사람이 요청한 경우에만 호출한다.
- 무료 한도를 넘길 수 있는 대량 임베딩·평가는 예상 사용량을 먼저 보고한다.
- `AGENTS.md`, `CLAUDE.md`, `.claude/**`는 사람의 승인 후에만 수정한다.

## 모델 선택

저장소는 특정 모델 ID를 강제하지 않는다. 생성 모델과 임베딩 모델의 선택은 결정 기록과
평가 보고서로 남기고, 바꿀 때는 `AGENTS.md` 3.3의 인덱스 버전 규칙을 따른다.
