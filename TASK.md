# Task Contract: QK-SEC-001 색인 제외 경로·비밀값 차단·접근 범위 판정 (WBS 1.4)

> Generated at: `2026-10-19`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-99` / https://tkv123.atlassian.net/browse/SCRUM-99 (상위 `SCRUM-42` 팀 RAG 구축)
- 기능명세서 ID / 링크: QK-SEC-001 / `specs/QK-SEC-001-security-filter/spec.md`(작성 중)
- 팀 스프린트 ID: `QELLO-S2026-W43`
- GitHub Issue: `#37`
- Branch: `feat/SCRUM-99-gh-37-security-filter`
- Base branch: `feat/SCRUM-98-gh-34-source-adapter-contract`(PR #35). #35 병합 후 `main`으로 rebase한다. 아래 Decisions 참조

## Objective

- 이번 단계: QK-SEC-001 명세(`spec.md`)를 `/speckit-specify`로 작성해 사람 리뷰를 받는다.
- 다음 단계(명세 승인 후): `/speckit-plan`·`/speckit-tasks`로 설계하고 구현해, 첫 실제 색인 전에 색인 제외 경로·비밀값 차단·접근 범위 판정이
  모든 자료에 적용되게 한다(로드맵 2절, RISK-09).

## Scope

- `specs/QK-SEC-001-security-filter/spec.md`와 `checklists/requirements.md`. `.specify/feature.json`(git 무시 파일, 로컬 전용)은 이 명세 디렉터리를 가리키게 한다.
- 명세가 다룰 동작:
  - 색인 제외 경로: 자료원 설정의 포함·제외 패턴과 별개로 항상 적용하는 제외 규칙과 제외 사유 기록
  - 비밀값 차단: 임베딩·생성 API로 보내기 전 비밀값 패턴 검사, 걸린 자료는 임베딩·저장하지 않음(AGENTS.md 3.1)
  - 접근 범위(`access_scope`): 값 체계, QK-ING-001 `SourceItem.access`를 입력으로 한 판정, 확인할 수 없으면 "미확인"
- `TASK.md`

## Explicit exclusions

- 이번 단계에서 `plan.md`, `tasks.md`, 구현 코드, 테스트. 명세 승인 후 Decisions에 기록하고 범위를 넓힌다.
- 실제 GitHub 수집기와 실제 원본 호출(QK-ING-002), 청커(QK-CHK-002), 동기화·삭제 반영(QK-SYN-001), 저장 스키마와 마이그레이션(QK-STO-001).
- QK-ING-001 코드·명세 수정. 필요한 변경은 PR #35 쪽에서 다룬다.
- 런타임 의존성 추가(`pyproject.toml`의 `dependencies`). 필요하면 사람 승인을 받는다.
- `docs/sdd/roadmap.md`, `docs/sdd/constitution.md`, `.specify/memory/constitution.md`, `AGENTS.md`, `CLAUDE.md`, `.claude/**` 수정.
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문은 기록하지 않는다. 명세의 비밀값 예시는 `<github-token>` 같은 placeholder로 쓴다.

## Data and cost impact

- 새로 읽는 자료원: 해당 없음
- 외부 API로 보내는 데이터: 해당 없음
- 예상 임베딩·생성 호출량과 무료 한도 대비: 0 Neurons
- 인덱스 버전 변경: 없음

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `specs/QK-SEC-001-security-filter/` | Byuntil | 사람 리뷰 |
| `TASK.md` | Byuntil | 사람 리뷰 |

## Existing user-owned changes

- 2026-10-19 `feat/SCRUM-98-gh-34-source-adapter-contract`(`baa59b8`)에서 브랜치 생성 시 `git status --short` 결과: 변경 없음

## Validation

```bash
python3 scripts/preflight.py
git diff --check
grep -rn "NEEDS CLARIFICATION" specs/QK-SEC-001-security-filter/spec.md   # 결과가 없어야 한다
```

## Completion criteria

- `spec.md`가 사람 리뷰로 승인된다.
- 명세에 비밀값을 심은 샘플 자료가 임베딩·저장 단계로 넘어가지 않음을 확인할 측정 가능한 성공 기준이 있다.
- 명세에 접근 범위를 확인할 수 없는 자료가 "미확인"으로 판정되고 팀 공용으로 승격되지 않음을 확인할 측정 가능한 성공 기준이 있다.

## Decisions

- 2026-10-19 사실: PR #35(QK-ING-001)는 OPEN이고 팀원 리뷰 승인이 없다. `origin/main`은 `b7be62a`(#29)다.
- 2026-10-19 사용자 결정: PR #35가 승인·병합됐다고 가정하고 QK-SEC-001을 시작한다. AGENTS.md 1절 3항(최신 `origin/main`에서 분기)의 예외로,
  #35 브랜치 HEAD `baa59b8` 위에 이 브랜치를 쌓는다. PR을 열면 base를 #35 브랜치로 하고, #35가 병합되면 `main`으로 rebase한 뒤 base를 `main`으로 바꾼다.
  #35 리뷰에서 계약(`SourceItem.access` 등)이 바뀌면 이 명세도 다시 맞춘다.
- 2026-10-19 사용자 결정: 에이전트가 Jira 하위 작업 `SCRUM-99`(SCRUM-42 아래, 담당 구성재)와 GitHub Issue `#37`을 만든다. 저장소의 Jira 자동 생성은
  Secret이 없어 동작하지 않으므로 Jira를 먼저 만들고 Issue 폼의 "기존 Jira 이슈 키"에 넣었다.
- 2026-10-19 사용자 결정: 이번 세션은 명세(`spec.md`)까지만 작성한다. plan·tasks·구현은 명세 승인 뒤에 한다.
- 2026-10-19 사실: 백로그 행의 요구사항 FR-SEC-03, FR-SEC-06, sources.md 8절은 저장소에 원문이 없다. QK-ING-001과 같은 방식으로 명세 Assumptions에 기록한다.
- 2026-10-19 사용자 결정(명세 확인 필요 2건): 1) 접근 범위가 미확인·제한인 자료는 본문을 조회하지 않고 청킹·임베딩·저장하지 않는다(FR-018).
  2) 비밀값 규칙에 걸린 자료는 문서 전체를 청킹·임베딩·저장하지 않는다(FR-011).
- 2026-10-19 사실: `spec.md`와 `checklists/requirements.md` 초안을 이 세션이 썼다. 이 세션은 명세를 승인하지 않는다(AGENTS.md 2절). 사람 리뷰 대기.
