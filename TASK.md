# Task Contract: QK-ING-003 Confluence 자료원 전환과 Confluence 페이지 수집 명세 (WBS 2.3)

> Generated at: `2026-10-27`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-119` / https://tkv123.atlassian.net/browse/SCRUM-119 (상위 `SCRUM-42` 팀 RAG 구축)
- 기능명세서 ID / 링크: `QK-ING-003` / `specs/QK-ING-003-confluence-pages/spec.md`(작성 중)
- 팀 스프린트 ID: `QELLO-S2026-W44`
- GitHub Issue: `#72`
- Branch: `feat/SCRUM-119-gh-72-confluence-source`
- Base branch: `main`. 2026-10-27 `origin/main` `ba1249e`(#69 병합)에서 분기했다. 이전 `main`의 계약(QK-CHK-001)은 git 이력에 남긴다.
  push 전에 `origin/main` `4286014`(#73 병합) 위로 커밋을 다시 쌓았다. 충돌난 `TASK.md`는 이 계약을 남겼고, `main`의 #68 계약은 git 이력에 남긴다.
  PR #77을 연 뒤 충돌을 풀려고 `origin/main` `5567346`(#71·#75 병합)을 병합했다. `TASK.md`는 같은 방식으로 이 계약을 남겼다(`main`의 #67·#58 계약은 git 이력에 남긴다).

## Objective

- 팀이 2026-10-17에 작업 관리를 Jira `SCRUM` 프로젝트로, 문서를 Confluence `SCRUM` 스페이스로 옮긴 것을 색인 정책과 계획에 반영한다.
- Confluence를 새 자료원 종류로 추가하는 결정 기록(ADR-026, Proposed)을 쓴다(AGENTS.md 3.1).
- QK-ING-003(WBS 2.3) Confluence 페이지 수집 `spec.md`를 Spec Kit으로 쓰고 독립 검토 뒤 사람 승인을 받는다. 승인 뒤 `plan.md`·`tasks.md`로 넘어간다.

## Scope

- `AGENTS.md` 3.1 색인 대상 목록(사람 승인 대상, AGENTS.md 4절)
- `docs/sdd/roadmap.md`: 2절 Phase 2·3 산출물, 3절 Phase 1·2 목표와 범위, 2.3·3.1·6.3, 4절 QK-ING-003·004 행, 6절 RISK-01·02, 이관 설명 한 단락. WBS 번호·명세 ID·선행·크기는 바꾸지 않는다
- `README.md` 소개 문구
- 새 결정 기록 `docs/sdd/decisions/ADR-026-confluence-source.md`(Proposed)
- `specs/QK-ING-003-confluence-pages/`의 `spec.md`, `checklists/requirements.md`. spec 승인 뒤 같은 디렉터리의 plan 산출물
- WBS 보드(Artifact) 제목·메모 6곳. PR 내용 승인 뒤 반영한다
- `TASK.md`(이 파일)

## Explicit exclusions

- 수집기·접근 판정 규칙·변환기 구현, `src/`·`tests/`·`config/` 변경, 자료원 종류 등록
- Jira 이슈 수집 명세(QK-ING-004, Phase 3)와 Jira 자료원 결정 기록
- Atlassian 토큰·서비스 계정 발급, 실제 수집·측정·색인. Confluence·Jira 원본 쓰기
- 기존 ClickUp 조사 문서(`clickup-writing-rules.md`, `research/clickup-migration-check.md`, `research/inventory.md`, `research/tokens.md`), 승인된 명세(QK-CHK-002·QK-SEC-001·QK-ING-001·QK-SYN-001), 기존 ADR 수정
- `CLAUDE.md`, `CODEX.md`, `.claude/**`, `.github/` 수정. `AGENTS.md`는 3.1 목록만 바꾼다
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문은 기록하지 않는다.

## Data and cost impact

- 새로 읽는 자료원: 이번 단계는 없다. 명세가 정할 대상은 Confluence `SCRUM` 스페이스(비공개 팀 자료)다. 결정은 ADR-026에 남긴다(AGENTS.md 3.1)
- 외부 API로 보내는 데이터: 이번 단계 0건. 공식 문서 조회만 했다. 운영에서는 청크 본문이 Workers AI 임베딩(ADR-002)으로 간다
- 예상 임베딩·생성 호출량과 무료 한도 대비: 이번 단계 0 Neurons. 첫 색인 예상은 plan에서 페이지 수를 잰 뒤 추정한다
- 인덱스 버전 변경: 없음

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `AGENTS.md` 3.1, `docs/sdd/roadmap.md`, `README.md`, WBS 보드 | tkv00 | 사람 리뷰(AGENTS.md는 승인 필수) |
| `docs/sdd/decisions/ADR-026-confluence-source.md` | tkv00 | 사람 리뷰 |
| `specs/QK-ING-003-confluence-pages/`, `TASK.md` | tkv00 | 사람 리뷰 |

## Existing user-owned changes

- 2026-10-27 `origin/main`(`ba1249e`)에서 브랜치 생성 시 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
```

문서 단계라 코드 시험은 해당하지 않는다.

## Completion criteria

- AGENTS.md 3.1·로드맵·README 변경과 WBS 보드 변경이 사람 리뷰로 승인된다 — PR 리뷰
- ADR-026(Proposed)이 데이터 처리 정책, 토큰 종류·범위(공식 문서 근거), 수집 계정, `access_scope` 판정 규칙, 개인 스페이스 제외, 본문 변환 방식을 담는다 — PR 리뷰
- QK-ING-003 `spec.md`가 독립 검토를 거쳐 사람 리뷰로 승인된다 — 리뷰 기록

## Decisions

- 2026-10-27 사실: 이관 사실은 `docs/github-workflow.md:5`에 있다. Confluence `Qello 마이그레이션 검증 기록`은 이 세션에서 열지 못했다(Atlassian MCP 미인증).
- 2026-10-27 사실: 별도 세션이 문서 초안(AGENTS.md 3.1·로드맵·README patch, Confluence 결정 기록 초안, ClickUp 전제 문서 목록, 질문 Q1~Q12)을 세션 공유 노트 폴더에 썼다. 저장소 밖 초안이다.
- 2026-10-27 사용자 결정: Jira 이슈 하나와 PR 하나에 AGENTS.md 3.1, 로드맵, README, WBS 보드, ADR-026(Proposed)을 함께 올린다(초안 질문 Q1 A안).
- 2026-10-27 사용자 결정: Spec Kit 규칙대로 설계안을 쓰고 이슈를 만든다. GitHub Issue #72를 작업 폼 형식으로 열었고 `Jira subtask` 워크플로가 `SCRUM-42` 아래 `SCRUM-119`를 만들었다.
  하위 작업의 Jira 스프린트는 상위 이슈를 따라 `Backend·Sprint 3`(10/12–10/18)이라 팀 스프린트 ID와 어긋난다. 옮기는 일은 사람이 한다.
- 2026-10-27 사실: 단계 게이트 1.G는 미완료다. QK-CHK-001 선례(2026-10-26 사용자 결정)처럼 명세 단계만 먼저 한다(작성 세션 해석, 사람 확인 대상).
- 2026-10-27 사실: 작성 시점에는 결정 기록 번호 025가 비어 있었으나, push 전에 `main`에 #68·#73(`ADR-025-context-budget-3000.md`)이 병합됐다.
- 2026-10-27 사용자 결정: 결정 기록을 ADR-026으로 바꾸고, `TASK.md` 충돌은 이 브랜치 계약을 남겨 최신 `main` 위에 커밋 6개를 다시 쌓는다.
  026은 `origin/main`, 원격 브랜치, 열린 PR(#71·#75)에서 쓰이지 않는다. 이 파일의 아래 기록과 명세·로드맵의 "ADR-025" 표기는 ADR-026으로 고쳤다.
- 2026-10-27 사실(specify): `specs/QK-ING-003-confluence-pages/spec.md`(US 6개, FR-001~029, SC-001~010)와 `checklists/requirements.md`를 썼다. 외부 호출 0건, 0 Neurons.
  [NEEDS CLARIFICATION] 2개(FR-012 Free 사이트 판정, FR-021 회의록 이름)를 사람에게 물었다.
- 2026-10-27 사용자 결정(원문 "1. B 2. A"): 회의록 참석자·담당자 이름은 그대로 색인하고 개인 정보 확인 기록에 허용을 적는다(FR-021).
  Free 사이트는 "사이트 사용자가 모두 팀원임"을 사람이 확인한 기록으로 팀 공용을 판정한다(FR-012). ADR-026에도 반영했다.
  멘션도 표시 이름을 남기게 한 것(FR-017)은 작성 세션 판단이다(사람 확인 대상).
- 2026-10-27 사실: spec 독립 검토(작성에 관여하지 않은 별도 서브에이전트) 판정은 변경 요청이다(높음 2, 중간 7, 낮음 8). 다음 지적은 작성 세션이 코드·공식 자료로 다시 확인했다.
  - H1: 수집 계정이 볼 수 없게 된 페이지는 "제한"으로 판정되지 않고 목록에서 빠져 일반 내림(`SOURCE_MISSING`)으로 간다(`sync/plan.py:171-184`). 일반 내림은 내림 비율 검사에 막힐 수 있다.
  - H2: 동기화는 종류당 자료원 하나(`sync/identity.py:19-23`)이고, 범위 키가 바뀌면 `scope_changed`로 멈춘다(`identity.py:28-32`). 원본 정체성이 없으면 보안 동작만 한다(`sync/plan.py:77-81`).
  - M3: 개인 정보 확인 기록 형식은 `result` 두 값과 GitHub 범위 키만 받는다(`sources/scope_review.py:64-67`).
  - M7: 공식 v2 OpenAPI에 `GET /pages/{id}/permissions`·`GET /pages/{id}/restriction-state`(둘 다 `read:page:confluence`)가 있다. ADR-026의 "v2에 대응 엔드포인트가 없다"는 틀렸다.
- 2026-10-27 사용자 결정(독립 검토 반영):
  - H1: 지난 실행에 있었는데 목록에서 빠진 페이지는 단건 확인 뒤 접근 거부·없음이면 보안 내림한다(spec FR-030). QK-SYN-001 동기화 계획 변경이 이 명세 구현 범위에 들어간다.
  - H2: 자료원 하나 = 스페이스 하나. 정체성·범위 키는 스페이스 ID(FR-002·FR-002a). 스페이스 추가는 자료원별 식별 명세 뒤.
  - M1: Free 사이트 사용자 확인 기록은 90일 유효. 판정 방식과 기록 해시를 보안 규칙 버전 재료에 넣는다(FR-006·FR-012).
  - M2: 대응표 키는 첫 단계 페이지 ID. 미분류·스페이스 홈은 색인하지 않고 설정 제외처럼 보안 내림한다(FR-020·FR-020a).
- 2026-10-27 사실: 나머지 지적은 작성 세션이 다음처럼 반영했다(사람 결정 필요 없음으로 판단).
  - M3: 확인 기록 형식 확장(FR-025a). M4: 공통 형식 확장(FR-032), 메타데이터 필터는 QK-TRK-001, 인덱스 버전 영향은 ADR-026 Data and cost.
  - M5: 구조로 알 수 있는 식별자·연락처만 지우고 본문 연락처는 사람 확인으로 막는다(FR-017·FR-021). M6: 보류 페이지 판정 기록에는 페이지 ID만(FR-011).
  - M7·L7: ADR-026 엔드포인트 표와 서비스 계정 문구를 고쳤다. L1: 모르는 권한 주체 규칙을 FR-010과 ADR 표에서 같게 했다.
  - L2: 권한 조회 실패 10% 초과 시 불완전(FR-031). L3·L8: Edge Cases. L4: `일시` 없는 페이지는 회의로 세지 않는다(FR-022). L5: 인증 값 여러 개와 링크 호스트는 plan(FR-018·FR-028).
  - L6: 로드맵 279행을 고쳤다. WBS 보드는 PR 승인 뒤 반영하므로 PR 본문에 그 차이를 적는다. AGENTS.md 3.1 문구는 그대로 두었다(새 자료원은 결정 기록 뒤에 켠다는 규칙이 같은 절에 있다).
  재검토는 받지 않았다.
