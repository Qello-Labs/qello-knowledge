# Task Contract: QK-ING-002 GitHub 저장소 파일 수집 (WBS 1.5)

> Generated at: `2026-10-20`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-100` / https://tkv123.atlassian.net/browse/SCRUM-100 (상위 `SCRUM-42` 팀 RAG 구축)
- 기능명세서 ID / 링크: QK-ING-002 / `specs/QK-ING-002-github-repo-source/spec.md`(작성 예정)
- 팀 스프린트 ID: `QELLO-S2026-W43`
- GitHub Issue: `#41`
- Branch: `feat/SCRUM-100-gh-41-github-repo-source`
- Base branch: `main`(`origin/main` `40fe214`에서 분기)

## Objective

- 이번 단계: QK-ING-002 명세(`spec.md`)를 작성하고 사람 리뷰를 받는다. plan·tasks·구현은 명세 승인 뒤에 한다.
- 함께: 로드맵 진행 상태 열을 GitHub Issue 상태에 맞게 갱신한다(`scripts/roadmap_status.py --write`).

## Scope

- `specs/QK-ING-002-github-repo-source/spec.md`, `checklists/requirements.md`
- `docs/sdd/roadmap.md`의 `상태`·`진행` 열(스크립트 출력만, 손으로 고치지 않음)
- `.specify/feature.json`(git 무시 파일, 로컬 전용)은 이 명세 디렉터리를 가리키게 한다.
- `TASK.md`
- 명세가 다룰 동작:
  - 첫 대상 저장소 `dnd-side-project/dnd-15th-2-backend`(공개, 기본 브랜치 `main`)의 Markdown 문서 수집
  - QK-ING-001 계약(`github_repo_files` 종류, 필수 설정 `repo`·`ref`, 허용 호스트 `api.github.com`)에 맞춘 어댑터와 실제 HTTP 전송
  - 기본 브랜치 트리 조회, 포함·제외 패턴 적용, 파일별 blob SHA 제공. 변경 비교 판정과 삭제 반영은 QK-SYN-001과 경계를 나눈다
  - QK-SEC-001 인계: 공개 범위를 `AccessInfo.raw`의 `("visibility", "public")`로 전달, `source_id`는 저장소 안 경로,
    포함 패턴 확장자와 `FILE_EXTENSIONS` 대조, 자료원 범위를 넓힐 때의 개인 정보 확인 기록 형식과 위치(FR-024)
  - QK-ING-001 인계: GitHub 403 한도 초과의 일시적 재분류, 기본 한도값 측정·조정, T053 후속 메모 두 건

## Explicit exclusions

- 구현, `config/sources.toml` 실제 자료원 등록, 실제 원본 호출(명세 승인 전).
- 청킹(QK-CHK-002), 임베딩(QK-EMB-001), 동기화·변경 판정·삭제 반영(QK-SYN-001).
- QK-ING-001·QK-SEC-001 코드와 승인된 명세 수정.
- 로드맵 `상태`·`진행` 열 외의 `docs/sdd/roadmap.md` 내용, `docs/sdd/constitution.md`, `.specify/memory/constitution.md`, `AGENTS.md`, `CLAUDE.md`, `.claude/**` 수정.
- 원본 자료원(GitHub 대상 저장소 포함)에 쓰기.
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문은 기록하지 않는다. 명세의 토큰 예시는 `<github-token>` 같은 placeholder로 쓴다.

## Data and cost impact

- 새로 읽는 자료원: 이번 단계는 해당 없음. 구현 단계에서 GitHub 공개 저장소 `dnd-side-project/dnd-15th-2-backend`를 읽는다(읽기 전용 토큰)
- 외부 API로 보내는 데이터: 해당 없음
- 예상 임베딩·생성 호출량과 무료 한도 대비: 0 Neurons
- 인덱스 버전 변경: 없음

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `specs/QK-ING-002-github-repo-source/` | Byuntil | 사람 리뷰 |
| `docs/sdd/roadmap.md` 상태 열 | Byuntil | 사람 리뷰 |
| `TASK.md` | Byuntil | 사람 리뷰 |

## Existing user-owned changes

- 2026-10-20 `main`(`40fe214`)에서 브랜치 생성 시 `git status --short` 결과: 변경 없음

## Validation

```bash
python3 scripts/preflight.py
git diff --check
python3 scripts/roadmap_status.py   # "최신" 결과여야 한다
grep -rn "NEEDS CLARIFICATION" specs/QK-ING-002-github-repo-source/*.md   # 결과가 없어야 한다
```

## Completion criteria

- `spec.md`가 사람 리뷰로 승인된다(SCRUM-100 완료 조건 1).
- 구현 단계 조건(SCRUM-100): 대상 저장소의 포함 패턴에 맞는 파일 목록과 본문을 공개 범위 정보와 함께 읽는다(재생 전송 단위 시험, 실제 호출은 external 시험).
  공개 범위를 확인할 수 없는 저장소의 자료는 미확인으로 판정된다(단위 시험).

## Decisions

- 2026-10-20 사용자 결정: 에이전트가 Jira 하위 작업 `SCRUM-100`(SCRUM-42 아래, 담당 구성재)을 만든다.
- 2026-10-20 사용자 결정: 첫 대상 저장소는 `dnd-side-project/dnd-15th-2-backend`다. `config/sources.toml` 예시의 `Qello-Labs/qello-knowledge`는
  비공개이고 인벤토리상 색인 대상이 아니며(`docs/sdd/research/inventory.md:22`), 토큰도 공개 저장소 읽기만 있다(`docs/sdd/research/tokens.md:16`).
- 2026-10-20 사용자 결정: 에이전트가 GitHub Issue `#41`을 만든다(기존 Jira 키 SCRUM-100 입력). 브랜치를 `feat/SCRUM-100-gh-41-github-repo-source`로 바꿨다(push 전).
- 2026-10-20 사용자 결정: 로드맵 상태를 최신화한다. `roadmap_status.py --write`로 0.9·0.11·1.1~1.4 8건과 1.5(🔄 #41)를 반영했다.
- 2026-10-20 사실: 단계 게이트 `0.G`는 ⬜다. 0.1(SDD 리뷰), 0.7(골든셋 v0, `eval/` 없음), 0.8(생산성 기준선)이 끝나지 않아 완료 조건을 채우지 못한다.
  1.1~1.4가 이미 이 상태에서 진행됐고, 사용자 결정으로 Phase 1을 계속 진행한다. 0.8 기준선은 봇 사용 시작(1.11) 전에 끝내야 한다(로드맵 0.8).
- 2026-10-20 사실: FR-ING-02, FR-SYN-02(파일)는 저장소에 원문이 없다. 명세 Assumptions에 기록한다.
- 2026-10-20 사실: "트리 비교" 경계를 명세 FR-024로 제안했다. 수집기는 한 커밋 기준의 완전한 목록과 파일별 blob SHA까지, 이전 실행과의 비교·삭제 판정은 QK-SYN-001이다.
  명세 승인 때 함께 확인한다.
- 2026-10-20 사용자 결정(명세 확인 필요 1건, FR-020): 개인 정보 확인 기록은 자료원마다 한 파일로 `config/` 아래에 두고, 수집 전 검증이 기록된 범위와
  현재 자료원 설정을 대조해 없거나 다르면 원본 호출 없이 실패한다(안 A).
- 2026-10-20 사실: `spec.md`와 `checklists/requirements.md` 초안을 이 세션이 썼다. 이 세션은 명세를 승인하지 않는다(AGENTS.md 2절). 독립 검토와 사람 리뷰 대기.
  FR-009·FR-017은 QK-ING-001 코드·시험 수정이 필요해 plan에서 제외 범위 조정 승인을 받는다.
- 2026-10-20 사실: 명세를 쓰지 않은 Codex 세션이 `$harness-review`로 `40fe214..1208461`을 검토해 변경 요청(FAIL)을 냈다. P1 0건, P2 1건
  (Edge Cases의 크기 초과를 "건너뜀"으로 써 QK-ING-001 R-08·`collect.py`의 "영구 실패, `SIZE_EXCEEDED`"와 다름). 나머지 인계 항목, FR-024 경계,
  FR-020 안 A는 일치로 판정했다. Codex 실행: preflight 318개 파일, `git diff --check`, 확인 필요 표시 검사 통과.
- 2026-10-20 사실: P2를 명세 Edge Cases에서 고쳤다. 검토 중 `roadmap_status.py`가 다른 작업의 Issue #42(1.7 QK-EMB-001)로 1.7 상태가 최신이 아니라고 했다.
  이 작업의 범위가 아니어서 반영하지 않았다.
