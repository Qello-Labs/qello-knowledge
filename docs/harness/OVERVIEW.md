# Harness Overview

## 목적

팀원이 Claude Code 같은 AI 에이전트로 RAG 시스템을 만들 때 ClickUp 작업 범위, 검증 증거,
데이터·비용 경계, 사람 승인이 사라지지 않게 하는 저장소 운영 체계다.

## 구성

하네스는 에이전트가 행동하기 전에 방향을 주는 **가이드**와 행동한 뒤 결과를 확인하는 **센서**로 나뉜다.

| 층 | 구성 | 종류 | 현재 상태 |
| --- | --- | --- | --- |
| 업무 게이트 | ClickUp 작업, 기능명세 ID, `TASK.md`, 작업 브랜치 | 가이드 | 문서 규칙 |
| 에이전트 계약 | `AGENTS.md`, `CLAUDE.md`, `.claude/skills/*` | 가이드 | 문서 규칙 |
| 증거 양식 | `templates/*`, PR 템플릿, Issue 폼 | 가이드 | 템플릿 |
| 기계 검사 | `scripts/preflight.py`, `.claude/settings.json` deny | 센서 | 로컬에서 수동 실행 |
| Claude Code 훅 | `.claude/hooks/speckit_spec_id.py` — Spec Kit 명세 디렉터리를 `specs/<명세 ID>-<이름>`으로 고정 | 센서 | `/speckit-specify` 실행 시 자동 |
| 강제 장치 | CI, 브랜치 보호 규칙 | 센서 | 없음 |

강제 장치가 없으므로 지금은 모든 규칙이 사람과 에이전트의 자발적 준수에 기댄다. 아래 "다음 단계"가 이 빈칸을 채운다.

## 출처

`dnd-side-project/dnd-15th-2-backend`의 `18b1adc`(2026-10-05) 하네스에서 가져와 이 저장소에 맞게 고쳤다.

| 이 저장소 | 원본 | 고친 점 |
| --- | --- | --- |
| `AGENTS.md` | `AGENTS.md` | GitHub Project를 ClickUp으로 바꿈. Terraform·Java 규칙 제거. 3절 RAG 규칙(자료원, 검색 자료 취급, 인덱스 버전, 평가, 비용) 추가. 결과 계약에 인덱스·평가 필드 추가. 약 600줄 → 164줄 |
| `CLAUDE.md` | `CLAUDE.md` | 인프라·Terraform 절 제거. 문서 선택표(`docs/harness/TASK_DOCUMENT_ROUTING.md`)를 합침 |
| `.claude/settings.json` | 같은 파일 | terraform·aws 차단 제거. `.env` 읽기 차단 유지 |
| `scripts/preflight.py` | 같은 파일 | `.venv` 등 제외 경로, 평가 세트 확장자(`.jsonl`, `.csv`) 추가. Anthropic, OpenAI, Notion, Figma 토큰과 비밀번호가 든 Postgres URL 규칙 추가. 코드의 설정 참조를 비밀값으로 오인하지 않도록 따옴표 값과 env 형식 줄만 검사 |
| `templates/task-contract.md` | 같은 파일 | ClickUp·명세 ID, 데이터·비용 영향, 결정 기록 절 추가 |
| `templates/decision-record.md` | 같은 파일 | ClickUp·명세 연결, 근거, 데이터·비용, 재검토 조건 절 추가 |
| `templates/eval-report.md` | `templates/performance-experiment-report.md` | PostGIS 성능 실험을 RAG 검색·생성 평가로 바꿈. Contract를 실행 전에 확정하는 규칙 유지 |
| `.claude/skills/harness-commit` | 같은 Skill | 브랜치-Issue 번호 필수 규칙 제거(Issue 번호는 있을 때만). RAG 파이프라인 단계 기준 분할. 평가 세트 분리 규칙 추가 |
| `.claude/skills/harness-pr` | 같은 Skill | `./harness` 명령 제거. ClickUp PR 템플릿 기준으로 본문 작성. ClickUp 역링크 단계 추가. 리뷰어 고정 제거 |
| `.claude/skills/harness-review` | `harness-review` + `agents/pm-reviewer.md` | 두 문서를 합치고 평가·데이터·비용 확인 항목 추가 |

## 가져오지 않은 것

| 원본 | 이유 |
| --- | --- |
| `harness-issue`, GitHub Project 필드 캐시 | 이 저장소는 ClickUp이 계획의 원본이다 |
| `harness-infra-*`, Terraform 규칙, apply 게이트 | 이 저장소에는 인프라 코드가 없다. 인프라 질문은 백엔드 저장소를 색인해서 답한다 |
| `harness-test-plan`, `harness-test-run`, 테스트 템플릿 | JUnit 5와 `@DisplayName`을 전제한다. 코드 작업을 다시 시작할 때 pytest 기준으로 새로 쓴다 |
| `harness-api-docs` | Spring OpenAPI 애노테이션을 전제한다 |
| `scripts/harness.py`, Husky, `validate-*.py` | Gradle과 "브랜치·커밋에 Issue 번호 필수" 규칙을 전제한다 |
| `scripts/repo-map` | Java 구문 인덱스다. 코드 청킹의 심볼 인덱스 설계에 개념만 참고한다 |
| `docs/experiments` | 백엔드 지침 구조 실험 원장이다 |

## 새로 정한 규칙

원본에도, 기존 `docs/github-workflow.md`에도 없던 규칙이다. 팀 확인이 필요하다.

- 브랜치 형식 `<type>/<short-slug>`, GitHub Issue가 있으면 `<type>/gh-<번호>-<short-slug>`
- `AGENTS.md` 3절 RAG 규칙. RAG 설계 문서(Step01~06)의 결정을 옮긴 것이므로, 설계 결정이 바뀌면 함께 고친다.
- PR 제목 `<type>: <summary>`. 백엔드 저장소 관행을 따랐고 검사기는 없다.

## 다음 단계

가이드를 늘리기보다 이미 있는 규칙을 센서로 바꾸는 순서다.

1. GitHub Actions에서 `python scripts/preflight.py` 실행, `main` 브랜치 보호 규칙 설정
2. `TASK.md` Ownership 경로와 실제 변경 파일을 비교하는 검사
3. pytest 기준 test-plan / test-run Skill
4. 평가 실행 Skill과 인덱스 버전 활성화 게이트(평가 통과 시에만 새 버전 활성화)
5. 에이전트가 규칙을 어긴 사례를 모으는 하네스 사고 기록과, 반복된 사례를 센서로 바꾸는 주기적 검토
