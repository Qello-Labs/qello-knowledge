# Qello Knowledge

팀의 코드, ClickUp 문서·작업, GitHub 기록을 근거로 질문에 답하는 RAG 지식 검색 시스템이다.
지금은 구현 전 단계이며, 구축 순서와 명세 백로그는 [로드맵](docs/sdd/roadmap.md)에 있다.

| 문서 | 내용 |
| --- | --- |
| [AGENTS.md](AGENTS.md) | 사람과 AI 에이전트의 공통 작업 계약 |
| [CLAUDE.md](CLAUDE.md) | Claude Code 진입점, Spec Kit 규칙 |
| [CODEX.md](CODEX.md) | Codex 진입점, Spec Kit 규칙. 설정은 아래 "Codex 설정" |
| [docs/sdd/roadmap.md](docs/sdd/roadmap.md) | 단계별 구축 순서, 명세 백로그(명세 ID), 작업별 진행 상태(✅·🔄·⬜) |
| [구축 WBS](https://claude.ai/artifact/HoKb7gf9wXkZ8nxDcgRZAa) | 로드맵 기준 단계별 작업·담당·진행 상태, 선후관계와 크리티컬 패스, 변경 기록. WBS 번호는 로드맵 백로그의 `WBS` 열과 같다(예: `1.5` = `QK-ING-002`) |
| [docs/sdd/constitution.md](docs/sdd/constitution.md) | 원칙 초안. `/speckit-constitution`의 입력 |
| [docs/github-workflow.md](docs/github-workflow.md) | Jira·GitHub Issue·PR 연결 |

## 로드맵 진행 상황 보기

- 진행 상태는 [로드맵](docs/sdd/roadmap.md) 표의 `상태` 열에 있다. ✅ 완료(Issue 닫힘), 🔄 진행 중(Issue 열림), ⬜ 시작 전.
- 상태는 제목에 `(WBS x.y)`가 붙은 GitHub Issue에서 계산한다. WBS 작업 Issue를 만들 때 제목 끝에 붙인다. 예: `... (WBS 0.9)`
- Issue를 열거나 닫은 뒤 갱신한다(`gh` 로그인 필요).

  ```bash
  python scripts/roadmap_status.py          # 바뀔 내용만 보기
  python scripts/roadmap_status.py --write  # 로드맵에 반영
  ```

- 작업 하나를 이어받기 전에 설명을 본다. Claude Code는 `/roadmap-explain 1.5`, Codex는 `$roadmap-explain 1.5`.
  WBS 번호 대신 명세 ID(`QK-ING-002`)를 넣어도 된다. 목적, 선행 작업, 완료 조건, 진행 이력, 시작 방법을 출처와 함께 보여 준다.

## GitHub Spec Kit 사용법

명세를 먼저 쓰고 승인된 명세대로 구현한다(Spec-Driven Development).
[GitHub Spec Kit](https://github.com/github/spec-kit) 1.1.0을 Claude Code와 Codex 스킬로 쓴다.
Claude Code는 `/speckit-specify`, Codex는 `$speckit-specify`처럼 앞 기호만 다르고 인자는 같다.

### 1. 설치(팀원마다 한 번)

```bash
# uv가 없으면 먼저 설치한다: https://docs.astral.sh/uv/
uv tool install specify-cli --from git+https://github.com/github/spec-kit.git@v1.1.0
uv tool update-shell   # 새 터미널을 연다
specify version
```

- `python` 명령이 Python 3.11 이상을 실행해야 한다. Spec Kit 스크립트가 `python`으로 호출된다.
  macOS에 `python3`만 있으면 `ln -s "$(command -v python3)" ~/.local/bin/python`으로 연결한다.
- 저장소는 이미 초기화되어 있다(`.specify/`, `.claude/skills/speckit-*`, `.agents/skills/speckit-*`). `specify init`을 다시 실행하지 않는다.
  버전을 올릴 때는 팀이 합의한 뒤 한 사람이 올리고 PR로 공유한다.

### 2. 명세 하나를 진행하는 순서

Claude Code에서 아래 명령을 차례로 실행한다. Codex에서는 `/`를 `$`로 바꿔 입력한다. 결과물은 `specs/<명세 ID>-<짧은 이름>/`에 쌓인다.

| 순서 | 명령 | 결과 |
| --- | --- | --- |
| 0 | `/speckit-constitution docs/sdd/constitution.md 내용으로 채워줘` | `.specify/memory/constitution.md` (처음 한 번, 원칙이 바뀔 때) |
| 1 | `/speckit-specify QK-ING-002 GitHub 저장소 파일을 수집한다` | `spec.md` — 무엇을, 왜 |
| 선택 | `/speckit-clarify` | 모호한 부분을 질문으로 보완한 `spec.md` |
| 2 | `/speckit-plan Python 3.12, LlamaIndex, pgvector` | `plan.md`, `research.md`, `data-model.md`, `contracts/`, `quickstart.md` |
| 3 | `/speckit-tasks` | `tasks.md` — 순서가 있는 작업 목록 |
| 선택 | `/speckit-analyze` | spec·plan·tasks 일관성 보고(파일을 고치지 않음) |
| 4 | `/speckit-implement` | 코드 |

- 명세(1)는 작성자 외 1명이 리뷰한 뒤 계획(2)으로 넘어간다.
- 구현(4) 전에 작업 브랜치와 `TASK.md`를 만든다(`AGENTS.md` 1절). 끝나면 `/harness-commit`, `/harness-pr`로 마무리하고,
  PR의 기능명세서 ID에 명세 ID를 적는다.

### 3. 명세 ID 규칙(자동 적용)

- `/speckit-specify`의 첫 단어는 [로드맵](docs/sdd/roadmap.md) 4절 백로그의 명세 ID다. 예: `QK-ING-002`
- 훅(Claude Code는 `.claude/hooks/speckit_spec_id.py`, Codex는 `.codex/hooks/speckit_spec_id.py`)이 디렉터리를 `specs/QK-ING-002-<영어 짧은 이름>/`으로 고정한다.
- 다음 경우에는 훅이 실행을 막고 이유를 보여 준다.
  - 명세 ID가 없다 — 아직 시작하지 않은 백로그 항목을 함께 보여 준다
  - 백로그에 없는 ID다 — 로드맵 백로그에 먼저 추가한다
  - 같은 ID의 디렉터리가 이미 있다 — 보완은 `/speckit-clarify`나 `spec.md` 직접 수정으로 한다
- `plan`·`tasks`·`implement`는 `.specify/feature.json`이 가리키는 명세를 대상으로 한다. 이 파일은 개인 로컬 상태라 커밋하지 않는다.
  다른 명세로 바꾸려면 `feature_directory` 값을 그 명세 경로로 고친다.

## Codex 설정(팀원마다 한 번)

Codex는 `AGENTS.md`를 직접 읽고, 나머지 규칙은 `CODEX.md`, `.codex/`, `.agents/skills/`로 적용한다.
Claude Code 하네스와의 대응은 [하네스 개요](docs/harness/OVERVIEW.md)의 "Codex 대응"에 있다.

1. 이 저장소를 Codex에서 처음 열 때 신뢰한 프로젝트로 지정한다(첫 실행 프롬프트 또는 `/permissions`).
   신뢰하지 않으면 `.codex/config.toml`과 `.codex/hooks.json`이 로드되지 않는다.
2. `/hooks`에서 프로젝트 훅 2개(SessionStart, UserPromptSubmit)를 검토하고 신뢰한다. 훅 파일이 바뀌면 다시 검토해야 실행된다.
   git 워크트리에서 작업하면 Codex는 훅 선언을 루트 체크아웃의 `.codex/`에서 읽으므로, 루트 체크아웃도 이 설정이 들어간
   `main`을 받아 두어야 한다.
3. 세션을 새로 시작해 `CODEX.md` 내용이 컨텍스트에 들어왔는지 확인한다. 예: "CODEX.md의 프로젝트 Skill 표를 보여 줘".
4. `~/.codex/config.toml`에 `sandbox_mode`를 두지 않는다. 있으면 `.env` 읽기를 막는 권한 프로필이 적용되지 않는다.
