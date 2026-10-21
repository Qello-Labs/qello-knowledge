# Implementation Plan: QK-SYN-001 증분 동기화·문서 단위 원자적 교체·실행 기록·스케줄러·CLI

**Branch**: `feat/SCRUM-102-gh-48-incremental-sync` | **Date**: 2026-10-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/QK-SYN-001-incremental-sync/spec.md`(2026-10-21 승인)

## Summary

활성 자료원마다 수집(QK-ING-002) → 보안 필터(QK-SEC-001) → 청킹(QK-CHK-002)을 쓰기 없이 돌려 문서별 판단(`SourcePlan`)을 만들고, 저장된 상태와 청킹 입력 지문으로
바뀐 문서만 문서 단위로 임베딩(QK-EMB-001, 예산은 실행 전체로 한 번 판정)해 문서 하나 = 트랜잭션 하나로 반영한다. 보안 사유 내림을 먼저 반영해 예산·버전·비율 보류와 상관없이 검색에서 빠지게 하고,
본문 삭제는 내림 비율 20% 안전장치를 따른다. 동기화 전용 저장 경계 `SyncStore`와 마이그레이션 `0004_sync.sql`(원본 자료 열 추가, 자료원 정체성, 실행 기록)을 더하고,
QK-STO-001 `Store`의 기존 연산은 바꾸지 않는다. 미리 보기는 같은 판단에 `Embedder.preview()`만 붙인다. 동시 실행은 자료원 종류별 PostgreSQL 세션 advisory lock으로 막고,
주기 실행은 저장소 변수로 켜는 GitHub Actions 워크플로다. 근거는 [research.md](research.md)에 있다.

## Technical Context

**Language/Version**: Python 3.13 (QK-FND-001 R-01)

**Primary Dependencies**: 새 의존성 없음. 기존 `psycopg[binary]`(선택 의존성 `postgres`), `markdown-it-py`(선택 의존성 `index`), 표준 라이브러리

**Storage**: PostgreSQL(로컬 `supabase/postgres` 이미지, 운영 저장소 미정 ADR-008). 마이그레이션 `0004_sync.sql` 추가(research R-02). 지우는 마이그레이션 아님

**Testing**: pytest. 단위(가짜 자료원·가짜 임베딩·메모리 `SyncStore`) + 로컬 DB(`QK_REQUIRE_LOCALDB=1`). 외부 호출 시험 없음. 실제 확인은 quickstart 3절 사람 단계

**Target Platform**: 색인 CLI(로컬 개발 환경, GitHub Actions `ubuntu-latest`). Workers 질의 번들에는 들어가지 않는다

**Project Type**: 단일 Python 패키지 안의 흐름 모듈 + 저장 경계 + CLI + 워크플로

**Performance Goals**: 합성 79개 첫 동기화 60초, 재동기화 30초 이하(spec SC-013, research R-15). 실제 수집은 원본 한도가 정한다(측정 73초)

**Constraints**: 문서 단위 원자 반영(FR-013), 보안 내림 우선(FR-004), 쓰기 전 게이트(FR-027), 기록에 원문·주소 없음(FR-028), 원본 쓰기 없음(C-09), 무료 예산 안(C-05)

**Scale/Scope**: Phase 1 자료원 1개, 문서 80개(필터 통과 79), 하루 1회. 새 모듈 약 8개, 마이그레이션 1개, CLI 하위 명령 5개, 워크플로 1개

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md`는 템플릿 상태라 `docs/sdd/constitution.md`와 `AGENTS.md`로 점검한다.

| 원칙 | 이 계획에서 | 결과 |
| --- | --- | --- |
| C-01·C-03 | 답변을 만들지 않는다. 본문 안의 지시를 해석하지 않는다 | 해당 없음·통과 |
| C-02 현재 상태는 원본에서 | `last_seen_at`을 남겨 색인 자료의 확인 시각을 보일 수 있게 한다(R-03) | 통과 |
| C-04 작게 시작 | 자료원 하나, 새 의존성 없음, 기존 단계 재사용 | 통과 |
| C-05 비용 상한 | 변경 없는 재동기화 0 Neurons, 예산 초과 시 처리 보류, 첫 실제 색인은 미리 보기 뒤 사람 승인. Actions 할당은 사람 확인(R-14) | 통과(R-14 확인 필요) |
| C-06 교체 가능한 경계 | `SyncStore` Protocol, `sync/`는 `adapters`를 가져오지 않는다(경계 시험) | 통과 |
| C-07 재현 | 청킹 입력 지문, 인덱스 버전 식별값을 설정에서 계산(R-03·R-08), 섞지 않음(FR-019) | 통과 |
| C-08 멱등·실패 격리 | 문서 하나 = 트랜잭션 하나, 실패 시 저장 상태 불변, 재실행은 처음부터(R-04) | 통과 |
| C-09 원본 읽기 전용 | 기존 수집 경로만, 추가 원본 요청 없음(R-10) | 통과 |
| C-10 민감 정보 | 보안 필터 생략 경로 없음, 보안 내림은 본문 삭제, 기록은 출력 규칙과 내부 식별값(R-12) | 통과 |
| C-11 명세 먼저 | spec 2026-10-21 승인. plan 승인 전 구현하지 않는다 | 보류 — plan 사람 승인 |
| C-12 검증으로 닫기 | SC마다 시험(quickstart 1절), SC-012는 사람 단계 기록 | 통과 |
| C-13 수치 조건 | 성능·비용 측정 조건을 R-15와 SC-012에 고정 | 통과 |
| C-14 권한 확인 자료만 | 접근 보류 문서 즉시 검색 제외, 어떤 보류에도 막히지 않음(FR-004) | 통과 |
| AGENTS.md 3.1 새 외부 서비스 | 새 서비스 없음. GitHub Actions는 ADR-008 결정. 운영 저장소 정책 확인은 R-13 게이트 | 통과 |
| AGENTS.md 3.3 인덱스 버전 | 메타데이터 스키마 그대로(`meta-v1`). 첫 버전 활성화는 사용자 승인 예외(spec FR-021) | 통과 |
| AGENTS.md 3.5 비용 | 이 계획 단계 0 Neurons. 구현 시험 0. 첫 실제 색인 약 325 Neurons는 사람 단계 H02 | 통과 |
| AGENTS.md 4절 변경 안전 | 기존 열·함수 변경 없음, 대량 삭제는 비율 안전장치, 정리 명령은 재실행 안전·원격은 옵션 필요 | 통과 |

Phase 1 설계 뒤 재점검: data-model이 저장 상태 불변식(내림 사유 ⇔ 삭제 상태, 대기 목록은 보안 사유만)과 `SourcePlan` 불변식(보류 시 처리 결정 없음)을 고정했고,
contracts가 쓰기 순서(점검 → 잠금 → 기록 → 보안 내림 우선)를 고정했다. 새 위반 없음. 보류는 C-11(plan 승인)과 R-14 Actions 할당 확인(사람 단계 H07)이다.

## Project Structure

### Documentation (this feature)

```text
specs/QK-SYN-001-incremental-sync/
├── spec.md
├── plan.md              # 이 파일
├── research.md          # R-01~R-18
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── sync.md          # 흐름 함수, SyncStore, 다른 경계에 더하는 것
│   └── cli.md           # qk-index 명령, 종료 코드, 출력, 주기 실행 정의
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks 산출물
```

### Source Code (repository root)

```text
src/qello_knowledge/
├── domain/
│   ├── source.py                 # SourceOrigin, ListPage.origin, Listing.origin 추가(R-10)
│   ├── security.py               # ScreenResult.listing 추가(R-18)
│   └── sync.py                   # ChangeReason, DocumentOutcome, HoldReason, DocumentDecision, SourcePlan, SyncPreview, SyncRunResult, ActivationCheck
├── ports/
│   └── sync.py                   # SyncStore, SyncLock, StoredDocument, StoredSource, IndexState
├── sync/
│   ├── __init__.py               # run_sync, preview, activate_first_index 공개
│   ├── keys.py                   # chunk_input_hash, doc_key, index_version_id, scope_key(R-03·R-08·R-10·R-12)
│   ├── decide.py                 # 변경 판단, 내림 판단, 비율 판정(R-03·R-05)
│   ├── plan.py                   # plan_source: 수집·필터·청킹 + 판단(쓰기 없음, R-07)
│   ├── identity.py               # 설정상·수집 뒤 정체성 판정(R-10)
│   ├── execute.py                # 쓰기 단계: 보안 내림 → 일반 내림 → 대기 삭제 → 임베딩·반영 → mark_seen
│   ├── preview.py                # preview: 미리 보기(쓰기 없음, R-07)
│   ├── activate.py               # activate_first_index(R-09)
│   ├── run.py                    # run_sync: 점검 → 잠금 → 기록 → 자료원별 실행 → 마감(R-06·R-16)
│   └── report.py                 # 요약·JSON·사람용 출력(FR-028)
├── security/screen.py            # screen_source가 ScreenResult.listing을 채움(R-18)
├── sources/collect.py            # list_all이 Listing.origin을 채움
├── adapters/
│   ├── github.py                 # 첫 페이지 origin(id, full_name)
│   ├── fake.py                   # 시험 응답 origin
│   └── postgres/
│       ├── store.py              # replace_chunks 청크 쓰기 부분을 내부 함수로 분리(동작 그대로)
│       ├── sync_store.py         # PostgresSyncStore(R-04·R-06·R-09·R-11)
│       └── migrations/0004_sync.sql
└── indexer/
    ├── cli.py                    # run(동기화·--preview), runs, index 하위 명령
    └── sync_cli.py               # 옵션 해석, 의존성 조립, 종료 코드(contracts/cli.md)
config/
└── store_policy.toml             # 만들지 않는다. 사람 단계 H04에서 PR로 더한다(R-13)
.github/workflows/
└── index-sync.yml                # 주기 실행, QK_SYNC_ENABLED로 켬(R-14)
tests/
├── unit/sync/                    # 판단·미리 보기·실행 기록·정체성(메모리 SyncStore, fake_store.py)
├── localdb/sync/                 # 원자 반영·내림·인덱스 버전·동시 실행·성능
├── unit/indexer/                 # test_run_cli.py, test_schedule_workflow.py
├── contract/                     # origin 계약 항목
└── unit/test_boundaries.py       # sync 경계 규칙
```

**Structure Decision**: 판단(`plan.py`·`decide.py`)과 쓰기(`execute.py`)를 나눠 미리 보기와 실제 실행이 같은 판단 경로를 쓰게 한다(R-07). 저장은 `SyncStore`만 거치게 해
메모리 구현으로 대부분의 시험을 돌리고, 트랜잭션·잠금·검색 노출은 로컬 DB 시험으로 확인한다. QK-STO-001 `Store`·QK-EMB-001 `Embedder` 경계는 그대로 쓴다.

## Phase 0·1 산출물

- Phase 0: [research.md](research.md) R-01~R-18. `NEEDS CLARIFICATION` 없음. spec이 plan으로 넘긴 항목의 결정 위치:
  내림 비율 초기값(FR-017) → R-05, 주기 실행 시각(FR-034) → R-14, 실행 기록 보관 기간·정리(FR-027) → R-11, 명령·옵션 이름(FR-030) → contracts/cli.md,
  자료원 정체성 저장 위치와 원본 정체성 필드(FR-002) → R-02·R-10, 성능 측정 조건(SC-013) → R-15.
  남는 위험: R-06(운영 저장소 앞 연결 풀러가 세션 잠금을 깨는 경우), R-14(비공개 저장소 Actions 할당).
  Codex plan 1차 검토(변경 요청 12건) 반영: 삭제 대기와 검색 제외 불변식 분리(data-model 1.1), 결과 기본 키에 작업(1.4), 수집 중단 보류(R-16), 종류별 잠금과 잠금 안 재검사(R-06),
  문서 단위 임베딩과 실행 전체 예산(R-17), 지운 자료원 대상화(R-06), `ScreenResult.listing`(R-18), 보안 근거·수집 요약 기록, 미리 보기 옵션(R-07), 정리의 `running` 제외(R-11),
  FR 추적표(quickstart 4절).
  Codex plan 2차 검토(변경 요청, 새 지적 7건) 반영: 바뀐 문서만 청킹(R-18), 실행 소진 상태와 캐시 완비 문서의 직접 반영(R-17), 설정 제외는 보안 필터와 같은 판정(R-18),
  같은 종류 자료원 교체 거부(R-10), 보류 사유별 작업 허용표(data-model 2.4), 남은 청크 없는 삭제 보류(data-model 1.1).
  Codex plan 3차 검토(변경 요청 4건) 반영: 버전 불일치에서 일반 내림 막음(spec SC-011), 장부 오류도 실행 소진 신호(R-17), 청킹 대상은 R-03 변경 조건 전체(R-18),
  캐시 직접 반영 문서의 임베딩 요약(R-17·data-model 2.8).
- Phase 1: [data-model.md](data-model.md), [contracts/sync.md](contracts/sync.md), [contracts/cli.md](contracts/cli.md), [quickstart.md](quickstart.md).

## 구현 Scope 승인이 필요한 것

TASK.md 제외 범위에 걸리는 변경이다. tasks 승인 때 Scope를 고쳐 함께 승인받는다.

| 변경 | 걸리는 제외 항목 | 이유 |
| --- | --- | --- |
| `domain/source.py`, `sources/collect.py`, `adapters/github.py`, `adapters/fake.py`, 계약 시험에 `origin` 추가 | QK-ING-001·002 코드 | spec FR-002 수집 뒤 정체성 비교(contracts/sync.md 3절) |
| `adapters/postgres/store.py` 내부 함수 분리 | QK-STO-001 코드 | 같은 청크 쓰기 SQL을 두 곳에 두지 않기 위해(R-01). 동작 변경 없음 |
| `domain/security.py`·`security/screen.py`에 `ScreenResult.listing`과 공개 이름 `source_excluded` 추가 | QK-SEC-001 코드 | 수집 뒤 정체성·목록 완전 여부를 넘기고, 저장된 문서의 설정 제외를 보안 필터와 같은 규칙으로 판정하기 위해(R-18). 판정 동작 변경 없음 |
| 마이그레이션 `0004_sync.sql` | 저장 스키마 변경 | spec FR-027 사용자 결정(실행 기록 DB), FR-006 저장 상태 |
| `.github/workflows/index-sync.yml` | (워크플로 파일) | spec FR-034. 변수로 꺼진 채 더한다 |

## 다른 명세에 넘기는 것

| 대상 | 넘기는 내용 |
| --- | --- |
| QK-SYN-002 | `qk.sync_document_result`의 `doc_key`·`outcome='FAILED'`로 실패 문서 고르기(R-12), 실패 문서만 다시 돌리기, Discord `/reindex` |
| QK-SYN-003 | 일반 내림 문서의 청크·원본 자료 항목 물리 정리, 쓰지 않는 벡터 정리, 주기적 전체 대조 |
| QK-STO-002 | 쓰지 않게 된 준비 버전 정리, 인덱스 버전 교체(평가 게이트), 버전 불일치 해소 절차 |
| QK-RET-001 | 검색 결과에 `last_seen_at`을 수집 시각으로 보일지(C-02) |
| 같은 종류 자료원을 더하는 명세(예: Android 저장소) | `qk.artifact` 유일 키에 자료원 이름 넣기, spec FR-002 검사 풀기 |
| 운영 저장소 결정(ADR-008 변경 제안) | 연결 방식이 세션 잠금을 유지하는지(R-06), 정책 확인(R-13) |

## Complexity Tracking

| 항목 | 이유 | 더 단순한 대안을 고르지 않은 이유 |
| --- | --- | --- |
| 새 저장 경계 `SyncStore` | 상태·청크·결과를 한 트랜잭션으로 반영해야 한다(FR-013) | `Store` 확장 — 검색 경계와 가짜 구현까지 넓어진다(R-01) |
| 보안 내림의 삭제 대기 목록 | 비율 초과 시에도 보안 대상 본문을 추적해야 한다(FR-015·017) | 대기 없이 즉시 삭제 — 사실상 전체 삭제를 사람 확인 없이 하게 된다(AGENTS.md 4절) |
| 수집 경계에 `origin` 추가 | 설정 그대로 원본이 바뀌는 경우를 잡아야 한다(FR-002) | 설정 비교만 — 리다이렉트로 따라간 이름 변경을 놓친다(Codex 2차 검토) |
