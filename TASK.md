# Task Contract: 쓰지 않는 예약 동기화 워크플로 삭제 (ADR-020 후속)

> Generated at: `2026-10-25`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-113` / https://tkv123.atlassian.net/browse/SCRUM-113 (상위 `SCRUM-42` 팀 RAG 구축)
- 기능명세서 ID / 링크: 해당 없음: 저장소 정리 작업이다. ADR-020 Negative("`index-sync.yml`은 저장소에 남는다. 후속 작업에서 지우거나 고친다")의 후속이며,
  QK-SYN-001(`specs/QK-SYN-001-incremental-sync/`) 문서의 주기 실행 경로 기록을 함께 고친다
- 팀 스프린트 ID: `QELLO-S2026-W43`
- GitHub Issue: 해당 없음
- Branch: `chore/SCRUM-113-remove-index-sync-workflow`
- Base branch: `main`. 2026-10-25 `origin/main` `f11e146`(#56 병합)에서 분기했다

## Objective

- ADR-020으로 쓰지 않기로 한 GitHub Actions 예약 동기화 워크플로를 저장소에서 지운다. 누군가 저장소 변수와 Secret을 넣어 공개 저장소의 Actions에서 운영 DB로 동기화하는 경로를 없앤다.
- 명세·운영 문서·결정 기록이 주기 실행 경로를 서버 systemd 타이머(ADR-020)로 적게 한다.

## Scope

- `TASK.md`
- `.github/workflows/index-sync.yml` 삭제
- `tests/unit/indexer/test_schedule_workflow.py` 삭제: 이 파일은 지우는 워크플로 파일의 내용만 검사한다. 기능을 없애므로 시험도 없앤다(2026-10-25 사용자 결정). 다른 시험은 바꾸지 않는다
- `specs/QK-SYN-001-incremental-sync/`: `contracts/cli.md` 5절을 systemd 타이머 기준으로 바꾸고, `research.md` R-14·`plan.md`·`quickstart.md` H07·`spec.md` Assumptions·`tasks.md`(T042·T047·H07)에 바뀐 사실을 적는다.
  완료된 작업 기록은 지우지 않고 바뀐 사실을 덧붙인다
- `specs/QK-GEN-001-answer-generation/tasks.md`: 워크플로 줄 번호를 가리키는 한 곳에 바뀐 실행 위치를 덧붙인다
- `docs/ops/oci-production-store.md` 2절 11번, `docs/sdd/decisions/ADR-020-scheduled-sync-systemd-timer.md` Negative의 `index-sync.yml` 줄

## Explicit exclusions

- 서버 타이머·실행 스크립트·유닛 변경. 실패 알림(SCRUM-108, PR #57)
- `.github/workflows/ci.yml`·`jira-subtask.yml` 등 다른 워크플로, `src/`, 다른 시험
- 명세의 요구사항(FR-034~037) 문장 변경. 요구사항은 실행 위치를 정하지 않으므로 systemd 타이머로도 충족한다 `(추론, 리뷰에서 확인)`
- `AGENTS.md`, `CLAUDE.md`, `.claude/**`, constitution, 로드맵 수정. 원본 자료원에 쓰기
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다
- 비밀값, 토큰, `.env` 값, 접속 주소, OCI 계정 식별자, 비공개 원문은 기록하지 않는다

## Data and cost impact

- 새로 읽는 자료원: 해당 없음
- 외부 API로 보내는 데이터: 해당 없음
- 예상 임베딩·생성 호출량과 무료 한도 대비: 해당 없음(0 Neurons). 매일 00:30 UTC에 건너뛰던 Actions 실행이 없어진다
- 인덱스 버전 변경: 없음(`iv-4c0bc4fcc642` 유지)

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `.github/workflows/index-sync.yml`, `tests/unit/indexer/test_schedule_workflow.py` 삭제 | Byuntil | 사람 리뷰(시험 삭제 사유 확인) |
| `specs/QK-SYN-001-incremental-sync/**`, `specs/QK-GEN-001-answer-generation/tasks.md` 한 줄 | Byuntil | 사람 리뷰 |
| `docs/ops/oci-production-store.md`, ADR-020 한 줄 | Byuntil | 사람 리뷰 |

## Existing user-owned changes

- 2026-10-25 `origin/main`(`f11e146`)에서 브랜치 생성 시 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
uv run qk-dev db up
QK_REQUIRE_LOCALDB=1 uv run pytest
git grep -n 'index-sync.yml'   # 남은 언급이 모두 "삭제했다"는 기록인지 확인
```

## Completion criteria

- `index-sync.yml`과 그 전용 시험이 저장소에 없고, 남은 시험과 PR CI가 통과한다 — pytest, PR CI
- 명세·운영 문서·결정 기록이 주기 실행 경로를 systemd 타이머(ADR-020)로 적는다 — 이 PR 리뷰
- 서버 예약 실행이 계속 성공한다(이 PR은 서버를 바꾸지 않는다) — 병합 뒤 다음 예약 실행 기록

## Decisions

- 2026-10-25 사실: Jira `SCRUM-113`을 사용자 요청으로 만들었다(SCRUM-42 하위 작업, 레이블 `tech-debt`·`team-backend`).
- 2026-10-25 사용자 결정: 워크플로는 수동 실행용으로 남기지 않고 지운다. 수동 실행도 GitHub에 운영 DB 경로와 Secret을 두어야 해서 ADR-020과 맞지 않는다. 수동 실행은 서버 `systemctl start qk-sync.service`(운영 문서 6절)로 한다.
- 2026-10-25 사용자 결정: 워크플로 파일만 검사하는 `tests/unit/indexer/test_schedule_workflow.py`를 함께 지운다. 검증을 통과시키려는 삭제가 아니라 기능 삭제에 따른 것이다(AGENTS.md 9절과 구분).
- 2026-10-25 사실(읽기 전용): 저장소 변수·Secret 목록이 비어 있다(`gh variable list`, `gh secret list`). 지금 워크플로는 매일 건너뛴다.
- 2026-10-25 사실: SCRUM-108(PR #57)이 운영 문서 2절 11번 바로 뒤와 ADR-020 Negative의 인접 줄을 고친다. 먼저 병합되는 쪽에 맞춰 나중 PR을 rebase한다.
