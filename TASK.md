# Task Contract: QK-SYN-001 증분 동기화·원자적 교체·실행 기록·스케줄러·CLI (WBS 1.8)

> Generated at: `2026-10-21`
>
> 이 파일은 현재 작업 브랜치의 계약이다. 저장소 공통 정책은 `AGENTS.md`를 따른다.

## Work gate

- Jira 이슈: `SCRUM-102` / https://tkv123.atlassian.net/browse/SCRUM-102 (상위 `SCRUM-42` 팀 RAG 구축)
- 기능명세서 ID / 링크: QK-SYN-001 / `specs/QK-SYN-001-incremental-sync/spec.md`(2026-10-21 승인)
- 팀 스프린트 ID: `QELLO-S2026-W43`
- GitHub Issue: `#48`
- Branch: `feat/SCRUM-102-gh-48-incremental-sync`
- Base branch: `main`. 2026-10-21 `origin/main` `96f54a8`(#47 병합)에서 분기했다

## Objective

- 이번 단계: QK-SYN-001 명세(`spec.md`)를 `/speckit-specify`로 작성하고 사람 리뷰로 승인받는다.
- 승인 뒤 `/speckit-plan`·`/speckit-tasks`와 구현을 이어 간다. 각 단계 시작 전에 이 파일의 Scope를 갱신해 승인받는다.
- 함께: 로드맵 진행 상태 열을 GitHub Issue 상태에 맞게 갱신한다(`scripts/roadmap_status.py --write`).

## Scope

- `specs/QK-SYN-001-incremental-sync/spec.md`, `checklists/requirements.md`
- `.specify/feature.json`(git 무시 파일, 로컬 전용)은 이 명세 디렉터리를 가리키게 한다.
- `docs/sdd/roadmap.md`의 `상태`·`진행` 열(스크립트 출력만, 손으로 고치지 않음)
- `TASK.md`
- 명세가 다룰 동작:
  - 색인 실행: 수집(QK-ING-002) → 보안 필터(QK-SEC-001) → 청킹(QK-CHK-002) → 임베딩(QK-EMB-001) → 저장(QK-STO-001)
  - 증분 동기화: 원본 버전·내용 해시로 바뀐 문서만 다시 청킹·임베딩. 변경 없는 재동기화에서 임베딩 호출 0건
  - 문서 단위 원자적 교체: 문서 하나의 청크를 한 번에 바꾸고, 실패한 문서는 이전 청크를 유지(constitution C-08)
  - 기존 청크 처리: 원본에서 사라진 문서, 접근 범위가 바뀌거나 미확인이 된 문서, 보안 규칙 버전·청킹 규칙 버전이 바뀐 문서, 빈 문서·청킹 실패 문서
  - 실행 기록(수집·필터·청킹·임베딩 요약, 실패 목록), 실행 전 사용량 미리 보기(`qk-index run --preview`)
  - 스케줄러(주기 실행, `usage prune` 포함)와 CLI. 실행 위치는 ADR-008(색인은 Workers 밖, GitHub Actions 또는 로컬 CLI)

## Explicit exclusions

- 이번 단계(명세)에서 `src/`·`tests/`·`pyproject.toml`·`uv.lock` 변경. 구현은 plan·tasks 승인 뒤 Scope를 갱신하고 한다.
- Discord `/reindex`·실패 문서 재시도(QK-SYN-002), 인덱스 버전 평가 게이트·활성화(QK-STO-002), 전체 대조 삭제·백업·복구(QK-SYN-003).
- 새 자료원(QK-ING-003 이후), 검색·생성.
- QK-ING-002·QK-SEC-001·QK-CHK-002·QK-EMB-001·QK-STO-001의 승인된 명세 변경.
- 로드맵 `상태`·`진행` 열 외의 `docs/sdd/roadmap.md` 내용, `docs/sdd/constitution.md`, `.specify/memory/constitution.md`, `AGENTS.md`, `CLAUDE.md`, `.claude/**` 수정.
- 실제 색인 실행(Workers AI 호출, 운영 DB 저장). 첫 실제 색인은 구현 뒤 미리 보기 사용량 보고와 사람 승인 뒤에만 한다.
- 원본 자료원에 쓰기.
- 공유 DB 초기화, 인덱스 전체 삭제, 유료 과금 설정 변경은 별도 승인 없이 하지 않는다.
- 비밀값, 토큰, `.env` 값, 비공개 원문은 기록하지 않는다. 명세 예시는 합성 문서로 쓴다.

## Data and cost impact

- 새로 읽는 자료원: 해당 없음. 대상은 이미 활성화된 `dnd-backend-docs`(ADR-019)
- 외부 API로 보내는 데이터: 이번 단계(명세) 해당 없음. 구현 뒤 실제 실행에서는 필터를 통과한 청크를 Workers AI bge-m3(ADR-002)로 보낸다
- 예상 임베딩·생성 호출량과 무료 한도 대비: 이번 단계 0 Neurons. 첫 실제 색인 예상 사용량은 `--preview`로 보고하고 무료 한도 안에서만 실행한다
- 인덱스 버전 변경: 명세 단계 없음. 실행 기록 등 저장 스키마 변경 여부는 명세·plan에서 정한다. 첫 실제 저장 전에 저장소 제공자(Supabase) 데이터 처리 정책을 확인한다(ADR-019 결정)

## Ownership

| Area (paths) | Owner | Required review |
| --- | --- | --- |
| `specs/QK-SYN-001-incremental-sync/` | Byuntil | 사람 리뷰(명세 승인) |
| `docs/sdd/roadmap.md` 상태 열 | Byuntil | 사람 리뷰 |
| `TASK.md` | Byuntil | 사람 리뷰 |

## Existing user-owned changes

- 2026-10-21 `origin/main`(`96f54a8`)에서 브랜치 생성 시 `git status --short` 결과: 변경 없음

## Validation

```bash
python scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
uv run qk-dev db up
QK_REQUIRE_LOCALDB=1 uv run pytest
```

## Completion criteria

- `spec.md`가 사람 리뷰로 승인된다 — 리뷰 기록
- (구현 단계) 변경 없는 재동기화에서 임베딩 호출 0건, 문서 1개를 고치면 그 문서의 청크만 교체된다 — 가짜 자료원·가짜 임베딩 시험(로드맵 1.G 조건)
- (구현 단계) 원본에서 지운 문서와 접근 범위가 미확인으로 바뀐 문서는 검색되지 않는다 — 로컬 DB 시험

## Decisions

- 2026-10-21 사용자 결정: WBS 1.8(#48) 진행.
- 2026-10-21 사실: Jira `SCRUM-102`(SCRUM-42 하위 작업, 해야 할 일)와 GitHub `#48`이 같은 작업을 가리키는 것을 확인했다. 선행 1.5(#41)·1.7(#42)·1.6(#46, PR #47 병합 `96f54a8`)은 끝났다.
- 2026-10-21 사실: 요구사항 FR-SYN-01, 03, 04, 05(CLI), 06은 저장소에 원문이 없다. 백로그 제목·constitution·관련 ADR에서 요구를 끌어내고 명세 Assumptions에 적는다.
- 2026-10-20 사용자 결정(이어받음): 단계 게이트 0.G 미완료 상태로 Phase 1을 계속 진행한다.
- 2026-10-21 사용자 결정: TASK.md 초안 승인, 명세 디렉터리 `specs/QK-SYN-001-incremental-sync/`로 명세 작성 시작.
- 2026-10-21 사실: `spec.md`·`checklists/requirements.md` 초안 작성. 확인 필요 표시 2건을 사용자에게 물었다.
- 2026-10-21 사용자 결정: 첫 인덱스 버전은 동기화가 준비 상태로 만들고, 활성 버전이 없을 때만 쓰는 활성화 명령으로 사람이 활성화한다(첫 버전 평가 예외, FR-021).
- 2026-10-21 사용자 결정: 실행 기록은 저장소(DB) 테이블로 남긴다(FR-027). 구현 단계에서 마이그레이션 추가(저장 스키마 변경, 인덱스 버전 변경 아님)가 Scope에 들어간다.
- 2026-10-21 사실: Codex 패널 명세 1차 검토 "변경 요청"(높음 5, 중간 4, 낮음 1). 10건 모두 코드·선행 명세와 대조해 맞다고 확인했다.
- 2026-10-21 사용자 결정: 내림 때 청크 본문 삭제는 보안 내림(비밀값 차단·접근 범위 보류·설정 제외 패턴)만 한다. 일반 내림은 검색 제외만 하고 물리 정리는 QK-SYN-003.
- 2026-10-21 사실: 1차 검토 10건 반영. 보안 검색 제외는 버전 불일치·예산 초과·비율 초과에도 적용, 문서 단위 반영 연산 추가(QK-STO-001 기존 연산은 그대로),
  변경 조건에 원본 제목·인덱스 버전 추가, 처리 버전과 확인 버전 분리, 같은 종류 자료원·자료원 정체성 변경을 실행 전 점검에서 막음, 미리 보기는 대상 집합 비교,
  실행 기록은 점검 통과 뒤 생성·문서 결과는 반영과 함께, 내부 식별값 분리, 첫 버전 활성화 조건.
- 2026-10-21 사실: Codex 명세 2차 검토 "변경 요청"(1차 2건 해소·8건 일부, 새 지적 높음 2·중간 5). 모두 확인 후 사용자 승인으로 반영했다.
  FR-008 (4)를 접근 범위·내림 기준으로 좁힘, 활성화 대상은 현재 설정 버전·실행 중 없음·검색될 문서 1개 이상·벡터 누락 0으로 한정하고 동기화와 배타,
  "본문 삭제 대기" 상태와 비율 기준(분모 0 규칙), 자료원 제거는 정체성 검사 대신 일반 내림·수집 뒤 정체성 비교, 모든 쓰기는 FR-002·029·032·033 통과 뒤,
  끝나지 않은 기록은 같은 자료원 실행이 실행 중 아님을 확인한 경우만 닫음, US4·Edge Cases 옛 문구 정리.
- 2026-10-21 사실: Codex 명세 3차 검토 "변경 요청"(2차 5건 해소, 남은 지적 높음 1·중간 1·낮음 1). 확인 후 사용자 승인으로 반영했다.
  "본문 삭제 대기"를 검색 제외와 분리해 보안 대상 본문이 남은 인덱스 버전 목록으로 정의(다시 처리해도 다른 버전 본문은 확인 옵션 실행에서만 지움),
  수집 공통 결과가 자료원 정체성(바뀌지 않는 식별값, 이름·위치)을 내보내도록 수집 경계 확장(구현 때 QK-ING-001·002 코드 변경 필요), US3 시나리오 전제 보완.
- 2026-10-21 사실: Codex 명세 4차 검토 "변경 요청"(중간 2: 정체성 기준값 등록 시점 불일치, FR-017 "확인 옵션 없는 삭제 금지" 문장 범위). 사용자 결정으로 두 건만 고치고 5차 검토 없이 사람이 직접 검토한다.
- 2026-10-21 사실: Codex 명세 5차 검토 "승인" 권고(4차 지적 2건과 정체성·체크리스트 이전 지적 모두 해소, 새 지적 0건). 명세 수준 판정이며 구현 검증은 아니다. 사람 승인 전이다.
- 2026-10-21 사용자 결정: QK-SYN-001 명세 승인(Codex 5차 검토 "승인" 권고 뒤, 커밋과 plan 진행 지시). 저장소 관례대로 `spec.md`의 Status 표기는 바꾸지 않고 이 기록으로 승인을 남긴다.
