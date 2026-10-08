# Task Contract: Codex 하네스 구성

> Generated at: `2026-10-09`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- ClickUp 작업 ID / URL: 해당 없음: 초기 세팅 단계 예외. 하네스 도구 작업이라 WBS에 등록하지 않음
- 기능명세서 ID / 링크: 해당 없음: 하네스 도구 작업이라 명세 백로그 대상이 아님. 작업 정의는 Issue #9
- 팀 스프린트 ID: `QELLO-S2026-W41`
- GitHub Issue: `#9`
- Branch: `chore/gh-9-codex-harness`
- Base branch: `main`

## Objective

- Claude Code 하네스(`CLAUDE.md`, `.claude/settings.json`, `.claude/hooks`, `.claude/skills`)의 규칙이 Codex에서도 같은 방식으로 적용되게 Codex 하네스를 구성한다.

## Scope

- `CODEX.md`: `CLAUDE.md`와 같은 구조의 Codex 진입점을 만든다.
- `.codex/hooks.json`, `.codex/hooks/`: SessionStart에서 `CODEX.md`와 `TASK.md`를 주입한다. UserPromptSubmit에서 `$speckit-specify`의 명세 ID를 검사하며, 판정은 `.claude/hooks/speckit_spec_id.py`의 함수를 불러 쓴다.
- `.codex/config.toml`: `.env`, `.env.*`, `secrets/` 읽기를 막는 권한 프로필을 둔다.
- `.agents/skills/harness-commit`, `harness-pr`, `harness-review`: Claude Skill을 복사해 Codex 도구와 호출 문법에 맞게 고친다.
- Spec Kit 1.1.0 Codex 통합을 `specify integration install codex --script py`로 설치한다(`.agents/skills/speckit-*`, `.specify/` manifest). `speckit-specify`에 `agents/openai.yaml`을 더해 명시 호출만 허용한다.
- `AGENTS.md`: 도입부 도구별 지침에 `CODEX.md`를, 4절 승인 대상에 `CODEX.md`, `.codex/**`, `.agents/**`를 추가한다.
- `docs/harness/OVERVIEW.md`, `README.md`: Codex 구성, Claude 하네스와의 대응표, Codex 사용법을 적는다.

## Explicit exclusions

- `.claude/**`와 `CLAUDE.md` 수정
- CI, 브랜치 보호 규칙
- 각자의 Codex 사용자 설정(`~/.codex/config.toml`) 변경
- 원본 자료원(ClickUp, Notion, GitHub, Figma)에 쓰기. GitHub는 Issue #9 생성과 이 브랜치 PR만 한다.
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문은 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: 해당 없음
- 외부 API로 보내는 데이터: Spec Kit 설치 때 GitHub에서 spec-kit v1.1.0을 받는다. Codex 실행 확인을 하면 확인 대화와 저장소 파일 일부가 OpenAI로 전송된다.
- 예상 임베딩·생성 호출량과 무료 한도 대비: 해당 없음
- 인덱스 버전 변경: 없음

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `CODEX.md`, `.codex/**`, `.agents/**` | 확인 필요 | 사람 리뷰 |
| `.specify/integration.json`, `.specify/integrations/*.manifest.json`, `.specify/scripts/bash/` | 확인 필요 | 사람 리뷰 |
| `AGENTS.md` | 확인 필요 | 사람 리뷰(AGENTS.md 4절 승인 필요) |
| `docs/harness/OVERVIEW.md`, `README.md` | 확인 필요 | 사람 리뷰 |
| `TASK.md` | 확인 필요 | 사람 리뷰 |

## Existing user-owned changes

- 2026-10-09 워크트리 생성 시 `git status --short` 결과: 변경 없음
- 원래 작업 트리(`docs/gh-8-clickup-migration-check`)의 미커밋 변경은 이 워크트리와 무관하며 건드리지 않는다.

## Validation

```bash
python3 scripts/preflight.py
git diff --check
# 훅 단위 확인: 이벤트 JSON을 stdin으로 넣고 출력 확인
# Codex 실행 확인: 세션 시작·명세 ID 훅 출력, 스킬 목록(codex debug prompt-input), 더미 .env 읽기 거부(codex sandbox -P qello)
```

## Completion criteria

- Codex 세션 시작 시 `CODEX.md`와 `TASK.md`가 컨텍스트에 들어가고, `$speckit-specify`에 명세 ID가 없거나 백로그에 없거나 디렉터리가 이미 있으면 차단된다. 훅 단위 실행 결과와 Codex 실행으로 확인한다.
- Codex 스킬 목록에 `harness-*`와 `speckit-*`가 보이고, Codex 샌드박스 명령으로 더미 `.env`를 읽으면 거부된다. Codex 실행으로 확인한다.
- `AGENTS.md` 변경 범위와 문구를 사람이 승인했다(AGENTS.md 4절). PR 리뷰 승인으로 확인한다.

## Decisions

- 2026-10-09 사용자 결정: 0.2·0.10처럼 초기 세팅 단계 예외로 ClickUp 작업 없이 진행한다. 하네스 도구 작업이라 로드맵·WBS 보드에 등록하지 않는다.
- 2026-10-09 사용자 결정: Issue #9를 만들고 별도 워크트리에서 작업한다.
- 2026-10-09 사용자 결정: Codex 진입점은 `CLAUDE.md`와 같은 구조의 `CODEX.md`로 둔다. `AGENTS.md`는 진입점 안내와 4절 승인 대상 추가만 고친다.
- 2026-10-09 사용자 결정: harness Skill은 Claude Skill을 전체 복사한 뒤 Codex용으로 고친다. 원본이 두 벌이므로 절차를 바꿀 때 함께 고친다.
- 2026-10-09 사용자 결정: Spec Kit Codex 통합은 `uvx`로 공식 명령(`specify integration install codex`)을 실행해 설치한다.
- 2026-10-09 사용자 확인: 이 `TASK.md` 초안으로 구현을 시작한다. `AGENTS.md` 문구는 구현 뒤 diff로 따로 승인한다.
- 2026-10-09 사용자 결정: Codex 실행 확인은 에이전트가 이 워크트리에서 `codex exec`로 한다. 훅 신뢰 검토는 그 실행에 한해 `--dangerously-bypass-hook-trust`로 건너뛴다.
- 2026-10-09 사용자 승인: `AGENTS.md` 도입부 진입점 안내와 4절 승인 대상(`CODEX.md`, `.codex/**`, `.agents/**`) 추가 문구를 승인했다.
- 2026-10-09 사용자 정정: Spec Kit Codex 통합과 명세 ID 훅도 Codex에 반드시 필요하다. 잠시 뺐던 통합 산출물과 훅을 다시 넣는다.
