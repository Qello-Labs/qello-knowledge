# Task Contract: QK-EMB-001 임베딩 Provider·캐시·예산 명세 작성

> Generated at: `2026-10-20`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-42` / https://tkv123.atlassian.net/browse/SCRUM-42 (팀 RAG 구축 상위 이슈. 하위 이슈는 아직 없다)
- 기능명세서 ID / 링크: `QK-EMB-001` / `specs/QK-EMB-001-embedding-provider-budget/spec.md`
- 팀 스프린트 ID: `QELLO-S2026-W43`
- GitHub Issue: 해당 없음
- Branch: `docs/SCRUM-42-emb-001-spec`
- Base branch: `main`

## Objective

- 로드맵 WBS 1.7 QK-EMB-001(임베딩 Provider(Workers AI), 캐시, 사용량 기록, 일일 예산, 실행 전 사용량 미리 보기)의
  Spec Kit 문서(`spec.md`, `plan.md`, `tasks.md`와 부속 문서)를 쓴다. 구현은 명세가 사람 리뷰로 승인된 뒤 별도로 한다.

## Scope

- `specs/QK-EMB-001-embedding-provider-budget/` 아래 Spec Kit 산출물: `spec.md`, `checklists/`, `research.md`,
  `data-model.md`, `contracts/`, `quickstart.md`, `plan.md`, `tasks.md`
- `.specify/feature.json`의 현재 명세 경로 갱신(Spec Kit 스크립트가 쓴다. git 추적 대상 아님)
- `TASK.md`(이 파일)

## Explicit exclusions

- `src/`, `tests/`, 마이그레이션 등 구현 코드 변경. 명세 승인 전에는 구현하지 않는다(로드맵 1절 원칙 4).
- 실제 Workers AI 호출, 색인 실행. 외부 API 비용을 쓰지 않는다.
- `docs/sdd/roadmap.md`, ADR, `AGENTS.md`, `CLAUDE.md`, `.claude/**` 수정.
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문은 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: 해당 없음
- 외부 API로 보내는 데이터: 해당 없음(문서 작업)
- 예상 임베딩·생성 호출량과 무료 한도 대비: 해당 없음. 명세가 정하는 예산 규칙은 구현 단계에서 적용된다
- 인덱스 버전 변경: 없음

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `specs/QK-EMB-001-embedding-provider-budget/` | 확인 필요 | 사람 리뷰(명세 승인) |
| `TASK.md`, `.specify/feature.json` | 확인 필요 | 사람 리뷰 |

## Existing user-owned changes

- 2026-10-20 `origin/main`(28792c6)에서 브랜치 생성 시 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
```

## Completion criteria

- `spec.md`가 백로그 행의 다섯 요소(Provider, 캐시, 사용량 기록, 일일 예산, 실행 전 미리 보기)를 검증 가능한 요구사항과
  수용 기준으로 담고, 사람 리뷰로 승인된다 — 검증: 리뷰 기록
- `plan.md`·`tasks.md`가 `spec.md`의 요구사항을 빠짐없이 작업으로 잇는다 — 검증: `/speckit-analyze` 결과와 문서 리뷰
- 문서에 비밀값·계정 식별자가 없다 — 검증: `python scripts/preflight.py`

## Decisions

- 2026-10-20 사용자 결정: Jira 이슈는 상위 이슈 `SCRUM-42`를 쓴다. QK-EMB-001 전용 하위 이슈는 아직 없다.
- 2026-10-20 사용자 결정: 이번 작업은 Spec Kit specify → clarify → plan → tasks까지다. 구현(`/speckit-implement`)은 명세 승인 뒤 별도로 한다.
