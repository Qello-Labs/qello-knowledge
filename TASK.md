# Task Contract: Phase 1 첫 명세 세 건 작성·승인 (WBS 0.11)

> Generated at: `2026-10-18`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-92` / https://tkv123.atlassian.net/browse/SCRUM-92 (상위 `SCRUM-42` 팀 RAG 구축)
- 기능명세서 ID / 링크: QK-FND-001, QK-STO-001, QK-ING-001 / `docs/sdd/roadmap.md` 4절 명세 백로그
- 팀 스프린트 ID: `QELLO-S2026-W42`
- GitHub Issue: `#24`
- Branch: `docs/SCRUM-92-gh-24-phase1-first-specs`
- Base branch: `main`

## Objective

- Phase 1 첫 명세 세 건(QK-FND-001 골격·설정·CI, QK-STO-001 저장 스키마·검색 SQL, QK-ING-001 자료원 어댑터 계약)을
  Spec Kit으로 쓰고 사람 승인을 받아, 0.G 완료 조건 "첫 명세 3개가 승인됐다"를 닫는다.

## Scope

- `specs/QK-FND-001-<짧은 이름>/`, `specs/QK-STO-001-<짧은 이름>/`, `specs/QK-ING-001-<짧은 이름>/`의 `spec.md`와
  `checklists/requirements.md`. `/speckit-specify`로 만들고 필요하면 `/speckit-clarify`로 열린 질문을 닫는다.
- `.specify/feature.json`: 현재 작성 중인 명세 디렉터리를 가리키도록 갱신한다.
- 작성 순서는 QK-FND-001 → QK-STO-001·QK-ING-001이다(로드맵 4절 선행 관계).
- QK-FND-001: 요구사항 FR-ING-10, FR-SEC-01, NFR-10, NFR-12, ADR-017. ADR-008 Follow-ups에 따라 `docker compose`는
  로컬 개발·테스트 범위로 좁히고, 실행 환경은 Cloudflare Workers(질의응답)와 Workers 밖 색인(GitHub Actions 또는 로컬 CLI)을 전제로 한다.
- QK-STO-001: 요구사항 FR-STO-01~03, ADR-006·007. Supabase 데이터 처리 정책 확인과 PGroonga 활성화 확인을 명세의 작업 항목으로 넣는다.
  ADR-007은 Phase 1 스파이크에서 정하므로 두 선택지를 모두 받는 요구로 쓴다.
- QK-ING-001: 요구사항 FR-ING-01, 10, 11.
- 다른 문서에 남길 수정(로드맵의 compose 서술 등)은 각 명세의 가정·발견 사항으로만 적는다.

## Explicit exclusions

- `/speckit-plan`·`/speckit-tasks` 산출물과 구현 코드. 구현은 SCRUM-89(골격·설정·compose·CI)·SCRUM-90(저장, 스키마, 검색 SQL 구현)에서 한다.
- Cloudflare Workers·Supabase 계정 설정, 배포, PGroonga 실제 활성화, 마이그레이션 실행.
- `docs/sdd/roadmap.md`, `docs/sdd/constitution.md`, `.specify/memory/constitution.md`, `AGENTS.md`, `CLAUDE.md`, `.claude/**` 수정.
- 로드맵 상태 표 갱신(`scripts/roadmap_status.py --write`).
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 계정 ID, DB 연결 주소, 비공개 원문은 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: 해당 없음. 저장소 문서만 읽고 쓴다.
- 외부 API로 보내는 데이터: 해당 없음
- 예상 임베딩·생성 호출량과 무료 한도 대비: 0 Neurons
- 인덱스 버전 변경: 없음

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `specs/QK-FND-001-*/`, `specs/QK-STO-001-*/`, `specs/QK-ING-001-*/` | 확인 필요 | 사람 리뷰. 명세 승인은 사람이 한다(AGENTS.md 2절) |
| `.specify/feature.json`, `TASK.md` | 확인 필요 | 사람 리뷰 |

## Existing user-owned changes

- 2026-10-18 `origin/main`(`0abe4b4`)에서 브랜치 생성 시 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
grep -rn "NEEDS CLARIFICATION" specs/*/spec.md   # 결과가 없어야 한다. 체크리스트 항목 이름은 제외
grep -rnE 'postgres(ql)?://|\.supabase\.co|\.neon\.tech' specs TASK.md   # 결과가 없어야 한다. DB 연결 주소
```

## Completion criteria

- 명세 3건의 `spec.md`에 사용자 시나리오, 기능 요구사항, 성공 기준, 가정이 있고 `[NEEDS CLARIFICATION]` 표시가 없다. 위 grep과 사람 리뷰로 확인한다.
- 각 명세가 로드맵 4절 백로그의 요구사항 ID를 모두 다룬다. 사람 리뷰로 확인한다.
- 명세 3건을 사람이 승인했다. 명세를 쓴 세션은 승인하지 않는다. PR 리뷰 승인 기록으로 확인한다.

## Decisions

- 2026-10-18 사용자 결정: WBS 0.11은 새 Jira 하위 작업(SCRUM-92, 상위 SCRUM-42)으로 추적하고, 구현 이슈 SCRUM-89·SCRUM-90과 Relates로 링크한다.
- 2026-10-18 사용자 결정: Backend·Sprint 3에 넣는다. 하위 작업은 스프린트를 직접 받지 않아 상위 SCRUM-42의 스프린트를 따른다.
- 2026-10-18 에이전트 판단: 명세 3건을 GitHub Issue 하나(#24)로 묶는다. 0.11이 WBS 작업 하나이기 때문이다.
- 2026-10-18 에이전트 확인: QK-FND-001 백로그 행의 요구사항 ID(FR-ING-10, FR-SEC-01, NFR-10, NFR-12, ADR-017)는 저장소(git 이력 포함),
  Confluence `SCRUM` 스페이스, 로컬 파일 어디에도 원문이 없다.
- 2026-10-18 사용자 결정: 요구사항 원문이 없으므로 에이전트가 백로그 제목, constitution, ADR-008, AGENTS.md를 근거로 설계한다.
  완료 조건 "백로그 요구사항 ID를 모두 다룬다"는 원문이 생길 때까지 명세의 백로그 제목 대응표로 대신 확인한다.
- 2026-10-19 사용자 결정: PR 작성 규칙(`.claude/skills/harness-pr/references/writing-style.md`, `.github/PULL_REQUEST_TEMPLATE.md`)에
  "가독성 좋게 쓰고, 쓸데없는 문장은 쓰지 않는다" 원칙을 추가하고 이 브랜치에 함께 커밋한다. 제외 범위의 `.claude/**` 수정에 대한 예외다.
