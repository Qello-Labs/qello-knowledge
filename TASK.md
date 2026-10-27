# Task Contract: ADR-024 승인 기록 (QK-BOT-001)

> Generated at: `2026-10-27`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-115` / https://tkv123.atlassian.net/browse/SCRUM-115 (상위 `SCRUM-42` 팀 RAG 구축)
- 기능명세서 ID / 링크: `QK-BOT-001` / `specs/QK-BOT-001-discord-ask/`
- 팀 스프린트 ID: `QELLO-S2026-W43`
- GitHub Issue: `#58`
- Branch: `docs/SCRUM-115-gh-58-adr-024-accepted`
- Base branch: `main`. 2026-10-27 `origin/main` `ba1249e`(#69 병합)에서 분기했다
- 이전 계약: `main`의 직전 계약(QK-CHK-001, #69)과 QK-BOT-001 운영 계약(`e701d5b`, #66)은 git 이력에 남긴다

## Objective

- PR #66 리뷰 승인(tkv00, 2026-10-27)을 근거로 ADR-024(Discord 중계 Worker TypeScript 전환)를 Accepted로 기록한다.

## Scope

- `TASK.md`
- `docs/sdd/decisions/ADR-024-ts-relay-worker.md`: Status, Approval
- `docs/sdd/decisions/ADR-022-discord-query-path.md`: ADR-024 링크 문장 한 줄

## Explicit exclusions

- 코드·시험·설정·운영 변경. #67·#68 작업(별도 작업 폴더·브랜치에서 진행 중).
- `AGENTS.md`, `CLAUDE.md`, `.claude/**`, constitution, 로드맵 수정. 원본 자료원에 쓰기. Jira 상태 변경.
- 비밀값, 토큰, `.env` 값, 주소, 식별자는 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: 해당 없음
- 외부 API로 보내는 데이터: 해당 없음
- 예상 임베딩·생성 호출량과 무료 한도 대비: 0 Neurons
- 인덱스 버전 변경: 없음

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `TASK.md`, ADR-022·ADR-024 | Byuntil | 사람 리뷰 |

## Existing user-owned changes

- 2026-10-27 `origin/main`(`ba1249e`)에서 브랜치를 만들 때 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
```

문서만 바꾼다.

## Completion criteria

- ADR-024 Status가 Accepted이고, Approval에 승인자와 PR #66 승인 기록 링크가 있다 — 리뷰
- ADR-022의 ADR-024 언급이 채택 상태와 맞다 — 리뷰

## Decisions

- 2026-10-27 사실: PR #66이 tkv00 리뷰 승인(APPROVED, 04:45 UTC) 뒤 병합됐다(`e701d5b`). PR 본문은 ADR-024 승인과 공유 인스턴스 구성 요소 추가 확인을 요청했다.
- 2026-10-27 사용자 요청: ADR-024 승인 기록을 별도 브랜치로 처리한다. 이 세션은 사람의 리뷰를 기록하며 스스로 승인하지 않는다.
- 2026-10-27 사실: #66 뒤에 #69(QK-CHK-001 구현)가 병합돼 이 브랜치는 그 위에서 시작했다.
