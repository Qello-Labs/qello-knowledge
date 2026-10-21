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

- 완료: QK-SYN-001 명세(`spec.md`)를 `/speckit-specify`로 작성하고 Codex 독립 검토 5회를 거쳐 사람 승인을 받았다(2026-10-21).
- 완료: `/speckit-plan` 설계 산출물을 만들고 Codex 독립 검토 4회를 거쳐 사람 승인을 받았다(2026-10-21).
- 완료: `/speckit-tasks` 작업 목록(`tasks.md`, 작업 50개 + 사람 단계 7개)을 만들고 사람 승인을 받았다(2026-10-21, 독립 검토 없이 승인).
- 이번 단계: `tasks.md` T001~T050 구현. 사람 단계 H01~H07은 구현 뒤 사람이 한다(H01~H03은 사람 승인 뒤 실행 가능).
- 함께: 로드맵 진행 상태 열을 GitHub Issue 상태에 맞게 갱신한다(`scripts/roadmap_status.py --write`).

## Scope

- `specs/QK-SYN-001-incremental-sync/spec.md`, `checklists/requirements.md`(승인됨, 바꾸려면 다시 승인)
- 설계 산출물: 같은 디렉터리의 `plan.md`, `research.md`, `data-model.md`, `quickstart.md`, `contracts/`(승인됨, 바꾸려면 다시 승인)
- 작업 목록: 같은 디렉터리의 `tasks.md`(승인됨). 구현 중 체크 표시와 실행 기록은 고친다.
- 구현(tasks.md, plan.md Project Structure·"구현 Scope 승인이 필요한 것"):
  - 새 파일: `src/qello_knowledge/domain/sync.py`, `src/qello_knowledge/ports/sync.py`, `src/qello_knowledge/sync/`(`__init__`, `keys`, `decide`, `plan`, `identity`, `execute`, `preview`, `activate`, `run`, `report`),
    `src/qello_knowledge/adapters/postgres/sync_store.py`, `src/qello_knowledge/adapters/postgres/migrations/0004_sync.sql`, `src/qello_knowledge/indexer/sync_cli.py`, `.github/workflows/index-sync.yml`,
    `tests/unit/sync/`, `tests/localdb/sync/`, `tests/fixtures/sync/`, `tests/unit/indexer/test_run_cli.py`, `tests/unit/indexer/test_schedule_workflow.py`, `tests/unit/security/test_screen_listing.py`
  - 고치는 파일(Scope 표의 변경만): `src/qello_knowledge/domain/source.py`·`sources/collect.py`·`adapters/github.py`·`adapters/fake.py`(QK-ING-001·002 `origin`),
    `src/qello_knowledge/domain/security.py`·`security/screen.py`(QK-SEC-001 `ScreenResult.listing`, `source_excluded`), `src/qello_knowledge/adapters/postgres/store.py`(QK-STO-001 내부 함수 분리, 동작 그대로),
    `src/qello_knowledge/indexer/cli.py`, `tests/unit/test_boundaries.py`, `tests/contract/source_adapter_contract.py`·GitHub 재생 시험, `tests/unit/sources/test_list_all.py`,
    `tests/unit/chunking/test_perf.py`(합성 문서 생성기 재사용이 필요할 때 도우미로 옮기는 것만)
    `tests/unit/indexer/test_cli.py`(`run` 성공 경로 사례 3개에 가짜 의존성 주입과 새 출력 기대값만. 실패 경로·다른 하위 명령 사례는 그대로, 2026-10-21 사용자 결정)
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

- 위 구현 목록 밖의 `src/`·`tests/` 변경. 새 의존성 추가, `pyproject.toml`·`uv.lock` 변경.
- 기존 시험 삭제·수정으로 통과시키기, `skip`·`xfail`, 경고 suppress(AGENTS.md 9절). 계약 시험은 항목을 더하기만 한다.
- 승인된 spec·plan 산출물 변경(구현과 다르면 먼저 사람 승인, tasks T049).
- 저장소 Secret·변수 등록, 워크플로 켜기(`QK_SYNC_ENABLED`), `config/store_policy.toml` 작성(사람 단계 H04·H07).
- Discord `/reindex`·실패 문서 재시도(QK-SYN-002), 인덱스 버전 평가 게이트·활성화(QK-STO-002), 전체 대조 삭제·백업·복구(QK-SYN-003).
- 새 자료원(QK-ING-003 이후), 검색·생성.
- QK-ING-002·QK-SEC-001·QK-CHK-002·QK-EMB-001·QK-STO-001의 승인된 명세 변경.
- 로드맵 `상태`·`진행` 열 외의 `docs/sdd/roadmap.md` 내용, `docs/sdd/constitution.md`, `.specify/memory/constitution.md`, `AGENTS.md`, `CLAUDE.md`, `.claude/**` 수정.
- 실제 색인 실행(실제 원본 수집, Workers AI 호출, 운영 DB 저장). 사람 단계 H01~H07로만 하고, 각 단계는 미리 보기 사용량 보고와 사람 승인 뒤에만 한다.
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
| `src/qello_knowledge/sync/`, `domain/sync.py`, `ports/sync.py`, `adapters/postgres/sync_store.py`, `migrations/0004_sync.sql`, `indexer/` | Byuntil | 사람 리뷰 |
| QK-ING-001·002·QK-SEC-001·QK-STO-001 코드의 Scope 표 변경 | Byuntil | 사람 리뷰(선행 명세 동작 불변 확인) |
| `.github/workflows/index-sync.yml` | Byuntil | 사람 리뷰 |
| `tests/unit/sync/`, `tests/localdb/sync/`, `tests/fixtures/sync/`, 그 밖에 고치는 시험 | Byuntil | 사람 리뷰 |

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
- 2026-10-21 사용자 결정: 명세 커밋 뒤 plan 단계 진행. Scope에 plan 설계 산출물(문서)을 더했다.
- 2026-10-21 사실: plan 산출물(plan·research R-01~R-16·data-model·contracts/sync.md·contracts/cli.md·quickstart) 작성. 사람 승인 전이다.
  구현 Scope에 걸리는 변경(수집 경계 origin, store.py 내부 함수 분리, 마이그레이션 0004, 주기 실행 워크플로)은 plan.md "구현 Scope 승인이 필요한 것"에 모았다.
- 2026-10-21 사실: Codex plan 1차 검토 "변경 요청"(높음 5, 중간 7). 모두 코드와 대조해 맞다고 확인하고 사용자 승인으로 반영했다.
  구현 Scope 표에 QK-SEC-001 코드(`ScreenResult.listing`)가 더해졌고, `qk.sync_source(source_kind)` 유일 제약으로 종류마다 자료원 하나를 DB가 강제한다.
- 2026-10-21 사실: Codex plan 2차 검토 "변경 요청"(1차 7건 해소·5건 일부, 새 지적 높음 3·중간 4. N2·N4는 Codex 메모리 재현). 모두 확인하고 기존 결정 안에서 반영했다.
  바뀐 문서만 청킹, 실행 소진 상태와 캐시 완비 문서 직접 반영(QK-EMB-001 경계 변경 없음), 설정 제외는 보안 필터 규칙(`source_excluded` 공개 이름 추가, Scope 표 반영),
  같은 종류 자료원 교체는 첫 쓰기 전 거부(교체 절차는 같은 종류 자료원을 더하는 명세로), 보류 사유별 작업 허용표, 남은 청크 없는 삭제 보류는 대기 비움.
- 2026-10-21 사실: Codex plan 3차 검토 "변경 요청"(2차 4건 해소·3건 일부, 새 지적 높음 2·중간 2. M2는 Codex 메모리 재현). 모두 확인하고 반영했다.
  버전 불일치에서 일반 내림 막음(spec SC-011과 맞춤), 사용량 장부 오류(예약 실패 항목·정산 실패 경고)도 실행 소진 신호, 청킹 대상은 변경 조건 전체, 캐시 직접 반영 문서의 임베딩 요약.
- 2026-10-21 사실: Codex plan 4차 검토 "승인" 권고(3차 M1~M4와 이전 일부 해소 항목 모두 해소, 새 지적 0건. 설계 수준 판정). 사람 승인 전이다.
- 2026-10-21 사용자 결정: QK-SYN-001 plan 승인(Codex 4차 검토 "승인" 권고 뒤). 같은 종류 자료원 교체 거부(research R-10, 교체 절차는 같은 종류 자료원을 더하는 명세로)도 승인.
- 2026-10-21 사용자 결정: plan 커밋 뒤 tasks 단계 진행.
- 2026-10-21 사실: `tasks.md` 작성(작업 50개 + 사람 단계 7개). 작성 중 plan.md Project Structure에 `sync/preview.py`·`sync/activate.py`를 더했다(미리 보기·활성화를 `run.py`와 나눔).
  승인된 plan 산출물의 보완이라 tasks 승인 때 함께 확인받는다.
- 2026-10-21 사용자 결정: `tasks.md` 승인(Codex 독립 검토 없이). plan.md 구조도 보완(`sync/preview.py`·`sync/activate.py`)과 구현 Scope(위 Scope·제외 범위·Ownership)를 함께 열었다.
- 2026-10-21 사용자 결정: 구현은 우측 패널 Codex 세션이 한다. 이 Claude 세션은 커밋·검토 조율과 독립 리뷰를 맡는다(구현을 같은 세션이 승인하지 않는다, AGENTS.md 2절).
- 2026-10-21 사실: Codex 구현 BLOCKED(T002 완료·T001 일부). 승인된 저장 스키마에 저장된 문서의 위치가 없어 research R-18의 설정 제외 판정을 할 수 없다(청크가 없는 문서는 locator로도 복구 불가).
- 2026-10-21 사용자 결정: `qk.artifact`에 `location` 열을 더한다(0004, 더하기만, 인덱스 버전 변경 아님). data-model 1.1, research R-02·R-04·R-18, tasks T012·T013·T017을 보완했다.
- 2026-10-21 사실: Codex 구현 2차 BLOCKED(완료 체크 28개, 전체 pytest 1198 passed). `run`을 실제 동기화로 바꾸면 기존 `test_cli.py`의 성공 경로 사례 3개가 점검 전용 출력을 기대해 충돌한다. T024 통합 시험은 구현 뒤 작성됐다.
- 2026-10-21 사용자 결정: `test_cli.py`의 `run` 성공 경로 사례 3개에만 가짜 의존성을 주입하고 출력 기대값을 새 동작에 맞춘다(T041 예외, 점검 통과 검증은 유지). T024는 구현을 임시로 깨뜨려 RED를 증명하고 원복한 뒤 완료한다.
- 2026-10-21 사실: Claude 세션 독립 리뷰(`/harness-review`) "변경 요청". 높음 1(이미 내려진 보안 문서를 매 실행 다시 내려 확인 옵션 뒤에도 내림 비율로 계속 멈춤, 메모리 재현), 중간 1, 낮음 2. 기본 검증은 재실행해 통과(1251 passed).
- 2026-10-21 사용자 결정: 첫 버전 활성화 조건의 "끝나지 않은 실행이 없다"는 지금 `running`인 실행이 없음으로 읽는다(이미 `unfinished`로 닫힌 이력은 보지 않음). research R-09를 보완했다. 리뷰 지적 1~4는 Codex가 고친다.
- 2026-10-21 사실: Codex가 독립 리뷰 지적 1~4를 반영했다. Claude 세션 재확인: 재현 스크립트 2건 모두 확인 뒤 실행 `succeeded`(종료 코드 0), 이미 내려진 보안 문서 재내림 0, 활성화 조건·정체성 등록 오류·CLI 시험 보완 확인.
  기본 검증 재실행 통과(preflight 543, ruff, format 372, 로컬 DB, `QK_REQUIRE_LOCALDB=1 pytest` 1263 passed). 재리뷰 권고: 승인. 사람 단계 H01~H07은 남아 있다.
- 2026-10-21 사실: 사람 단계 H01(로컬 DB 실제 미리 보기) 실행. 사전에 로컬 DB에 마이그레이션 0003·0004 적용. 결과: 원본 요청 84회, 처리 예정 79, 청크 1,291, 예상 368.93 Neurons(색인 예산 5,000 안),
  쓰기 0·임베딩 호출 0 확인. 자세한 조건은 tasks.md H01 결과. H02(첫 실제 색인)는 사람 승인 대기.
- 2026-10-21 사실: 사람 단계 H02(로컬 DB 첫 실제 색인과 재실행) 실행. 1회차 79개 처리·청크 1,291·제공자 호출 95·894.50 Neurons(측정값), 2회차 변경 없음 79·제공자 호출 0. SC-012 충족(예산 5,000 안).
  관찰: 미리 보기 예상 368.93 대비 실제 894.50(약 2.42배)로 QK-EMB-001 SC-005(±20%) 미달. 예상식 보정은 이 작업 범위 밖이라 사람 결정이 필요하다.
- 2026-10-21 사실: 사람 단계 H03 실행. 로컬 DB에서 첫 인덱스 버전 `iv-4c0bc4fcc642` 활성화(검색될 문서 79, 청크 1,291, 벡터 없는 청크 0). 키워드·벡터 검색 결과가 활성 버전에서 나옴(질의 임베딩 0.01 Neurons).
  H01~H03 완료로 spec SC-012 증빙을 갖췄다. H04~H07(운영 저장소·Actions)은 운영 저장소 결정 뒤.
- 2026-10-21 사용자 결정: 미리 보기 예상식 오차(실제 약 2.42배, QK-EMB-001 SC-005 미달)는 이 PR과 분리한다. QK-EMB-001 후속 작업으로 넘기고 PR 본문 위험 항목에 적는다. 이 작업에서 QK-EMB-001 코드·명세는 바꾸지 않는다.
- 2026-10-21 사용자 결정: H01~H03 기록을 커밋하고 `/harness-pr`로 진행한다. H04~H07은 운영 저장소 결정 뒤 미실행으로 남긴다.
