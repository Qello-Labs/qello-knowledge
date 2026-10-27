# Task Contract: #74 명세에 남은 문맥 예산 기본값 2,000 문장을 3,000으로 갱신

> Generated at: `2026-10-27`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: 해당 없음: 2026-10-27 사용자 결정으로 Jira 없이 진행하는 예외 작업
- 기능명세서 ID / 링크: `QK-RET-001` / `specs/QK-RET-001-hybrid-retrieval/`, `QK-CHK-001` / `specs/QK-CHK-001-code-chunker/`(현재 기본값 문장만 갱신. 요구사항은 바꾸지 않는다)
- 팀 스프린트 ID: 해당 없음: Jira 없이 진행하는 예외 작업
- GitHub Issue: `#74`
- Branch: `docs/gh-74-context-budget-3000`
- Base branch: `main`. 2026-10-27 `origin/main` `256de6f`(#78 병합)에서 분기했다

## Objective

- #73(ADR-025)에서 3,000으로 올린 문맥 예산 기본값(`QK_RETRIEVAL_CONTEXT_BUDGET`)을, 현재 기본값을 2,000으로 적은 명세 문장에 반영한다.

## Scope

- `specs/QK-RET-001-hybrid-retrieval/data-model.md` 1.1 표의 `context_budget` 기본값
- `specs/QK-RET-001-hybrid-retrieval/spec.md` "초기값"의 "Context 예산 2,000은 청크 상한(예상 2,800, QK-CHK-002)보다 작아" 문단
- `specs/QK-CHK-001-code-chunker/spec.md` FR-016의 "지금 2,000토큰" 문장
- 세 곳 모두 3,000과 [ADR-025](docs/sdd/decisions/ADR-025-context-budget-3000.md) 링크를 가리킨다
- `TASK.md`

## Explicit exclusions

- 이력 문장: QK-RET-001 research R-08, tasks T003·T014·H01, spec의 Clarification·FR-016 "초기값 2,000"·"초기값" 문단의 나머지, QK-CHK-001 plan의 당시 기준, QK-CHK-001 spec US 근거 문장(66행)
- 코드·설정 변경(기본값은 #73에서 이미 3,000), ADR-025 상태 변경
- `AGENTS.md`, `CLAUDE.md`, `.claude/**` 수정. 원본 자료원 쓰기
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문은 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: 해당 없음
- 외부 API로 보내는 데이터: 해당 없음
- 예상 임베딩·생성 호출량과 무료 한도 대비: 0 Neurons
- 인덱스 버전 변경: 없음

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| 위 명세 문서 3개, `TASK.md` | Byuntil | 사람 리뷰 |

## Existing user-owned changes

- 2026-10-27 `origin/main`(`256de6f`)에서 브랜치를 만들 때 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
```

## Completion criteria

- 갱신 대상 세 곳이 3,000과 ADR-025 링크를 가리키고, 이력 문장은 바뀌지 않는다 — diff
- 문서만 바뀐다 — `python scripts/preflight.py`, `git diff --check`

## Decisions

- 2026-10-27 사용자 결정: #74와 #76은 Jira 없는 예외 작업이고 이슈별로 브랜치·PR을 나눈다.
- 2026-10-27 사실: ADR-025는 아직 `Status: Proposed`다. 상태 변경은 이 작업 범위 밖이다.
