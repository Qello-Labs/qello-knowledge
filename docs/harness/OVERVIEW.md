# Harness Overview

## 목적

팀원이 Claude Code나 Codex 같은 AI 에이전트로 RAG 시스템을 만들 때 ClickUp 작업 범위, 검증 증거,
데이터·비용 경계, 사람 승인이 사라지지 않게 하는 저장소 운영 체계다.

## 구성

하네스는 에이전트가 행동하기 전에 방향을 주는 **가이드**와 행동한 뒤 결과를 확인하는 **센서**로 나뉜다.

| 층 | 구성 | 종류 | 현재 상태 |
| --- | --- | --- | --- |
| 업무 게이트 | ClickUp 작업, 기능명세 ID, `TASK.md`, 작업 브랜치 | 가이드 | 문서 규칙 |
| 에이전트 계약 | `AGENTS.md`, `CLAUDE.md`, `CODEX.md`, `.claude/skills/*`, `.agents/skills/*` | 가이드 | 문서 규칙 |
| 증거 양식 | `templates/*`, PR 템플릿, Issue 폼 | 가이드 | 템플릿 |
| 기계 검사 | `scripts/preflight.py`, `.claude/settings.json` deny, `.codex/config.toml` 권한 프로필 | 센서 | preflight는 로컬에서 수동 실행, 읽기 차단은 각 도구가 자동 적용 |
| Claude Code 훅 | `.claude/hooks/speckit_spec_id.py` — Spec Kit 명세 디렉터리를 `specs/<명세 ID>-<이름>`으로 고정 | 센서 | `/speckit-specify` 실행 시 자동 |
| Codex 훅 | `.codex/hooks.json` — 세션 시작 시 `CODEX.md`·`TASK.md` 주입, `$speckit-specify` 명세 ID 검사(Claude 훅과 같은 판정) | 가이드·센서 | 신뢰한 프로젝트에서 `/hooks` 검토 후 자동 |
| 강제 장치 | CI, 브랜치 보호 규칙 | 센서 | 없음 |

강제 장치가 없으므로 지금은 모든 규칙이 사람과 에이전트의 자발적 준수에 기댄다. 아래 "다음 단계"가 이 빈칸을 채운다.

## Codex 대응

Codex도 같은 계약을 따르도록 Claude Code 하네스의 각 장치를 Codex 기능에 대응시켰다. 공통 계약 `AGENTS.md`는
Codex가 직접 읽으므로 그대로 쓴다. 근거는 Codex 공식 문서, Codex 소스(`openai/codex` main, 2026-10-08),
Spec Kit 1.1.0 소스이고, 동작은 Codex CLI 0.160.0에서 확인했다(2026-10-09).

| Claude Code | Codex | 차이 |
| --- | --- | --- |
| `CLAUDE.md`(`@AGENTS.md`, `@TASK.md` import) | `CODEX.md` + `.codex/hooks/session_context.py`(SessionStart) | Codex는 import 문법이 없다. 훅이 세션 시작·재개·압축 때 `CODEX.md`와 `TASK.md`를 주입한다 |
| `.claude/settings.json` deny `Read(./.env)` 등 | `.codex/config.toml` 권한 프로필 `qello`(deny) | Claude는 Read 도구를, Codex는 샌드박스 명령을 막는다. Beta 기능이다. `sandbox_mode` 설정이 있거나 샌드박스를 끄면 적용되지 않는다 |
| `.claude/hooks/speckit_spec_id.py`(UserPromptSubmit, PreToolUse `Skill`) | `.codex/hooks/speckit_spec_id.py`(UserPromptSubmit) | 판정은 Claude 훅의 `resolve()`를 불러 쓴다. Codex에는 Skill 도구가 없어 모델의 스킬 호출을 가로챌 수 없으므로 `speckit-specify`의 암묵 호출을 막았다(`agents/openai.yaml`) |
| `.claude/skills/harness-*` | `.agents/skills/harness-*` | 전체 복사 후 호출 문법(`$harness-pr`), 질문 방식, 임시 파일 위치, 샌드박스 승인 안내만 고쳤다. 절차를 바꾸면 두 벌을 함께 고친다 |
| `.claude/skills/speckit-*`(Spec Kit `claude` 통합) | `.agents/skills/speckit-*`(Spec Kit `codex` 통합) | `specify integration install codex --script py`로 생성했다. 기본 통합은 `claude`로 남는다 |
| 하네스 파일 수정 승인(`AGENTS.md` 4절) | 같은 규칙 + Codex 샌드박스 보호 경로 | Codex 기본 샌드박스는 `.codex/`, `.agents/`, `.git`을 읽기 전용으로 둔다. 커밋·push에도 샌드박스 밖 실행 승인이 필요하다 |

### Codex 쪽 한계

- 저장소의 `.codex/` 설정·훅은 Codex가 이 저장소를 신뢰한 프로젝트로 열 때만 로드된다. 훅은 `/hooks`에서
  검토해 신뢰해야 실행되고, 훅 파일이 바뀌면 다시 검토해야 한다. 팀원마다 한 번씩 필요하다.
- 링크된 git 워크트리에서는 Codex가 훅 선언을 워크트리가 아니라 루트 체크아웃의 `.codex/`에서 읽는다(나머지 설정은
  워크트리 것을 쓴다). 루트 체크아웃에 `.codex/hooks.json`이 있는 커밋이 있어야 워크트리에서도 훅이 동작한다.
  훅 명령은 실행 위치의 `git rev-parse --show-toplevel` 기준이라 스크립트와 `TASK.md`는 워크트리 것을 쓴다.
- 명세 ID 훅은 사용자가 입력한 `$speckit-specify`만 본다. 모델이 SKILL.md를 직접 읽어 같은 절차를 수행하는 경로는 막지 못한다.
- `.env` 차단은 샌드박스 안 명령에만 적용된다. 사용자가 승인한 샌드박스 밖 실행, MCP·커넥터, 브라우저에는 적용되지 않는다.
- 훅 명령은 `sh`와 `git`을 쓴다. Windows 네이티브 Codex에서는 확인하지 않았다.
- `specify integration install codex`가 쓰지 않는 `.specify/scripts/bash/`도 공용 인프라로 함께 설치했다. Spec Kit manifest가
  관리하므로 지우지 않았다.

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
