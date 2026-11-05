# Implementation Plan: QK-STO-002 인덱스 버전 생성·평가 게이트·활성화

**Branch**: `feat/SCRUM-125-gh-100-index-version-gate-impl` | **Date**: 2026-11-05 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/QK-STO-002-index-version-gate/spec.md`(2026-11-02 승인)

## Summary

불일치 상태(활성 V1, 현재 설정 V2)에서 사람이 시작하는 재색인(`qk-index run --reindex`)이 지금 동기화 흐름을 그대로 써서 V2를 준비 상태로 채운다. 차이는 불일치 보류를 붙이지 않고,
새 설정에서만 나오는 "대상 아님"을 내리지 않으며, 실행 기록에 재색인 표시를 남기는 것뿐이다. 재색인이 활성 버전 검색 결과의 출처 정보를 바꾸지 않도록 청크 행에 출처 열을 두고
검색 결과가 청크 값을 먼저 쓴다(research R-01). 게이트(`qk-dev eval gate`)는 `main`에 병합된 TOML 정책과 QK-EVL-001 실행 기록만 읽어 판정하고 JSON 게이트 기록을 쓴다(DB·외부 호출 0).
판정 질문은 기준이 정하고 후보의 실패는 놓침으로 센다. 활성화·되돌리기·정리(`qk-index index activate|rollback|prune`)는 동기화와 같은 advisory lock을 배타로 잡고 한 트랜잭션에서
조건을 다시 계산한 뒤 전환하며, 모든 전환을 새 표 `qk.index_transition`에 남긴다. 활성화는 게이트 기록의 지문과 재판정 결과, 정책 병합 여부를 다시 확인한다.
저장 변경은 마이그레이션 `0009_index_versions.sql` 하나다. 토크나이저 변경 경로는 만들지 않고 활성화가 운영 토크나이저와 게이트 후보 토크나이저가 같은지만 확인한다(ADR-010 Proposed, R-12).

## Technical Context

**Language/Version**: Python 3.13 (QK-FND-001 R-01)

**Primary Dependencies**: 새 의존성 없음. 기존 `psycopg[binary]`, 표준 라이브러리(`tomllib`, `fractions`, `subprocess`로 `git` 호출)

**Storage**: PostgreSQL(로컬 `supabase/postgres` 이미지, 운영 OCI 인스턴스). 마이그레이션 `0009_index_versions.sql` 추가(research R-18). 기존 마이그레이션은 고치지 않는다

**Testing**: pytest. 단위(가짜 자료원·가짜 임베딩·손으로 만든 실행 기록·정책·가짜 저장소 이력) + 로컬 DB(`QK_REQUIRE_LOCALDB=1`). 외부 호출 시험 없음

**Target Platform**: 운영 담당자가 저장소 체크아웃에서 실행하는 `qk-index`(원격 대상은 `--allow-remote`)와 로컬 도구 `qk-dev`. 서버 systemd 동기화는 예약 실행만 하고 이 절차를 부르지 않는다

**Project Type**: 단일 Python 패키지 안의 흐름 모듈 + 저장 경계 + CLI

**Performance Goals**: 따로 정하지 않는다. 운영 청크 약 1,300개 규모에서 상태 보기·활성화 조건 계산은 질의 몇 개, 정리는 1,000행 묶음(R-16)

**Constraints**: 재색인 동안 활성 버전 결과 불변(FR-005), 전환 원자성(FR-003), 게이트 DB·외부 호출 0(FR-019), 기록에 원문 없음(SC-007), 원본 쓰기 없음(C-09), 무료 예산 안(C-05)

**Scale/Scope**: 새 모듈 약 9개(`gate/` 넷, `sync/versions.py`, `ports/index_versions.py`, `ports/history.py`, `adapters/postgres/index_versions.py`, `adapters/git_history.py`),
CLI 파일 2개(`indexer/index_cli.py`, `devtools/gate_cli.py`), 마이그레이션 1개, 명령 5개(재색인 옵션 1, `index` 하위 명령 3, `eval gate` 1)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md`는 템플릿 상태라 `docs/sdd/constitution.md`와 `AGENTS.md`로 점검한다.

| 원칙 | 이 계획에서 | 결과 |
| --- | --- | --- |
| C-01·C-03 | 답변을 만들지 않는다. 본문 안의 지시를 해석하지 않는다 | 해당 없음·통과 |
| C-02 현재 상태는 원본에서 | 활성화 전 마지막 재색인 성공과 덮음을 확인한다. 게이트는 설정을 판정하고 운영 데이터를 판정하지 않는다는 한계를 기록에 적는다(D1) | 통과 |
| C-04 작게 시작 | 새 의존성 없음, 동기화 흐름 재사용, 평가 계약 재사용, 토크나이저 변경 경로 미구현(R-12) | 통과 |
| C-05 비용 상한 | 재색인 미리 보기·예상 일수, 예산 초과 기본 거부, 시험 0 Neurons. 운영 추정은 R-14 | 통과 |
| C-06 교체 가능한 경계 | `IndexVersionStore`·`RepoHistory` Protocol, `gate/`·`sync/versions.py`는 `adapters`를 가져오지 않는다(경계 시험) | 통과 |
| C-07 재현 | 활성화는 게이트를 통과한 버전만, 기준·후보 인덱스 버전 ID 일치 확인, 정책 고정 | 통과 |
| C-08 멱등·실패 격리 | 재색인 이어 하기, 정리 묶음 커밋·재실행, 전환은 한 트랜잭션, 기록 파일 덮어쓰기 거부 | 통과 |
| C-09 원본 읽기 전용 | 기존 수집 경로만 | 통과 |
| C-10 민감 정보 | 보안 내림 규칙 그대로, 게이트 기록·전환 기록에 원문·이름 없음, 되돌리기 사유 비밀값 검사 | 통과 |
| C-11 명세 먼저 | spec 2026-11-02 승인. plan·tasks 사람 승인 전 구현하지 않는다 | 보류 — plan 사람 승인 |
| C-12 검증으로 닫기 | SC-001~SC-008 시험(quickstart 1절), SC-009는 사람 단계 | 통과 |
| C-13 수치 조건 | 게이트 기록·전환 기록에 모델·인덱스 버전·세트 버전·판정 질문 수, 판정 불가·실패도 기록 | 통과 |
| C-14 권한 확인 자료만 | 노출 조건은 검색 함수 그대로(`qk.is_visible`), 내린 문서는 버전 무관 비노출 | 통과 |
| AGENTS.md 3.3 인덱스 버전 | 이 절차가 3.3의 구현이다. 이 브랜치는 운영 인덱스 버전을 바꾸지 않는다 | 통과 |
| AGENTS.md 3.4 평가 | 정책 커밋을 평가 코드·결과와 분리, 고정 뒤 새 버전만(FR-012). 평가 세트 변경 없음 | 통과 |
| AGENTS.md 3.5 비용 | 이 브랜치 0 Neurons. 운영 실행 전 합계 보고(FR-034) | 통과 |
| AGENTS.md 4절 변경 안전 | 정리는 확인 옵션·되돌리기 대상 별도 확인, 인덱스 전체 삭제 없음, 원격은 `--allow-remote` | 통과 |

Phase 1 설계 뒤 재점검: data-model이 전환 표의 종류별 필수 열과 정리 표시 제약을, contracts가 조건 이름·판정 불가 사유·종료 코드를 고정했다. 새 위반 없음.
보류는 C-11(plan·tasks 승인)과 아래 "사람 확인 대상"이다.

## Project Structure

### Documentation (this feature)

```text
specs/QK-STO-002-index-version-gate/
├── spec.md              # 승인본(바꾸지 않는다)
├── plan.md              # 이 파일
├── research.md          # R-01~R-18
├── data-model.md
├── quickstart.md        # 검증 안내, 운영 1회 실행 순서, FR 추적
├── contracts/
│   ├── cli.md           # qk-index run --reindex, index status|activate|rollback|prune, qk-dev eval gate
│   ├── gate-policy.md   # qk-sto-002-gate-policy/v1
│   └── gate-record.md   # qk-sto-002-gate/v1
├── checklists/
│   └── requirements.md  # 명세 검토 기록(기존), plan 검토 기록을 더한다
└── tasks.md             # /speckit-tasks 산출물
```

### Source Code (repository root)

```text
src/qello_knowledge/
├── adapters/
│   ├── git_history.py                    # 새: RepoHistory 구현(git 명령)
│   └── postgres/
│       ├── migrations/0009_index_versions.sql   # 새(R-18)
│       ├── index_versions.py             # 새: PostgresIndexVersionStore(상태·덮음·전환·정리)
│       ├── store.py                      # _replace_chunk_rows가 청크 출처 열을 쓴다, trace_chunk는 청크 값 우선(R-01)
│       └── sync_store.py                 # prepare_candidate, 실행 kind, 첫 활성화 전환 기록, 0009 확인(R-18)
├── domain/sync.py                        # ChangeReason.NOT_TARGET_PENDING
├── ports/
│   ├── history.py                        # 새: RepoHistory
│   ├── index_versions.py                 # 새: IndexVersionStore, 스냅샷 값
│   └── sync.py                           # RunInfo.kind, SyncStore.prepare_candidate
├── sync/
│   ├── decide.py                         # NOT_TARGET_PENDING 판정
│   ├── plan.py                           # 재색인: 노출 안 되는 문서 보류, NOT_MARKDOWN → not_target(R-02·R-03)
│   ├── execute.py                        # not_target 처리 결과 쓰기
│   ├── run.py                            # SyncOptions.reindex, 예산 선판정, 불일치 보고에 덮음
│   ├── preview.py                        # 재색인 미리 보기 값, not_target 결정은 임베딩 요청에서 뺌
│   └── versions.py                       # 새: 활성화·되돌리기·정리 조건, 덮음·상태 조립
├── gate/                                 # 새 패키지
│   ├── policy.py                         # 정책 읽기·검증
│   ├── judge.py                          # 판정(순수 함수)
│   ├── record.py                         # 게이트 기록 쓰기·읽기·지문
│   └── verify.py                         # 활성화 쪽 확인(지문·재판정·정책 이력)
├── indexer/
│   ├── cli.py                            # index 명령을 index_cli로 넘김
│   ├── index_cli.py                      # 새: index status|activate|rollback|prune
│   └── sync_cli.py                       # run --reindex, query_command는 runs만
└── devtools/
    ├── db.py                             # eval 묶음에 gate 등록
    └── gate_cli.py                       # 새: qk-dev eval gate

tests/
├── fixtures/gate/                        # 손으로 만든 실행 기록·정책 예시
├── unit/gate/, unit/sync/, unit/indexer/, unit/devtools/, unit/test_boundaries.py
└── localdb/sync/                         # 재색인·활성화·되돌리기·정리·상태·동시성

docs/ops/oci-production-store.md          # 인덱스 버전 교체 절차 절 추가
```

**Structure Decision**: 단일 패키지 구조를 따른다. 판단은 `sync/versions.py`·`gate/`의 순수 함수, 저장은 새 경계 `IndexVersionStore`, git 읽기는 `RepoHistory` 경계로 둔다(research R-15).

## Phase 0·1 산출물

- Phase 0: [research.md](research.md) R-01~R-18. `NEEDS CLARIFICATION` 없음. spec이 plan으로 넘긴 항목의 결정 위치:
  FR-005의 방법(문서 단위 출처 정보) → R-01, 명령 이름 → contracts/cli.md, 정책·기록 파일 경로와 운영 쪽 확인(D4) → R-09·R-11, 저장 스키마 변경 → R-18·data-model 1절,
  운영 절차 문서 반영 → quickstart 3절과 tasks(운영 문서 절 추가), D7 출처 어긋남의 뜻 → R-01, D6 토크나이저 → R-12(미결, ADR-010 결과에 따름).
  별도 에이전트 plan 1차 검토(2026-11-05, 변경 요청 16건) 반영: 재색인이 내린 문서를 되살려 활성 버전 옛 청크가 다시 노출되는 경로 차단(R-02, 높음),
  배포 순서 보호 `schema_outdated`(R-18), G2·G3를 판정 질문 집합으로 계산(R-10), 정리 마지막 트랜잭션의 대기 목록·`purge_reason` 갱신(R-16), 처리 실패 문서 정의와 버전별 덮음(R-04),
  예산 초과 시 보안 내림 처리 근거(R-02), 재판정 입력 출처(R-11), `--main-ref` 기록·`code_commit_unknown`·`--source` 금지·`set_duplicate`(R-02·R-09·R-10),
  `chunk.title` 제거와 `trace_chunk`(R-01), 바꿀 파일 목록(`execute.py`·`preview.py`), 첫 활성화 전환 기록의 실행 위치(R-07), 이름·참조·예시 불일치,
  해소 방법·자료원 종류·판정 질문 수 보고(contracts), 실행 기록 커밋(quickstart H7), 벡터 근사 색인 한계(R-01), 병합 커밋 근거 문구(R-09). 검토 기록은 `checklists/plan-review.md`.
- Phase 1: [data-model.md](data-model.md), [contracts/cli.md](contracts/cli.md), [contracts/gate-policy.md](contracts/gate-policy.md), [contracts/gate-record.md](contracts/gate-record.md), [quickstart.md](quickstart.md).

## 구현 Scope 승인이 필요한 것

TASK.md Scope에 경로가 없거나 다른 명세의 코드를 바꾸는 변경이다. tasks 승인 때 TASK.md Scope를 고쳐 함께 승인받는다.

| 변경 | 걸리는 항목 | 이유 |
| --- | --- | --- |
| `adapters/postgres/store.py` `_replace_chunk_rows`, `qk.hit_json` 교체(0009) | QK-STO-001 코드·검색 함수 | FR-005 버전별 출처 정보(R-01). 출력 키 그대로 |
| `sync/plan.py`·`sync/decide.py`·`domain/sync.py`의 대상 아님 처리 | QK-SYN-001 판단 | FR-010(R-03). 재색인이 아닌 실행의 기존 경로는 그대로이고 새 사유는 `not_target` 상태에만 걸린다 |
| `indexer/sync_cli.py`의 `index` 명령을 `indexer/index_cli.py`로 옮김 | QK-SYN-001 CLI | 명령 넷이 늘어 파일을 나눈다. 지금 `index status`·`activate` 출력·종료 코드는 그대로(FR-036) |
| 새 경로 `adapters/git_history.py`, `ports/history.py`, `ports/index_versions.py`, `gate/**`, `devtools/gate_cli.py`, `devtools/db.py`, `tests/unit/test_boundaries.py` | TASK.md Scope에 경로 없음 | R-09·R-15 |
| `devtools/eval_index.py`는 바꾸지 않는다 | TASK.md Scope "필요할 때만" | R-13. Scope에서 뺀다 |

## 사람 확인 대상

- **PR 나누기**: 변경이 크다(모듈 약 9개, 명령 5개, 마이그레이션 1개). TASK.md는 PR 하나로 정했다. 대안은 셋으로 나누는 것이다:
  ① 저장 변경·재색인·상태 보기(US1, US5 상태 보기), ② 게이트(US2), ③ 활성화·되돌리기·정리(US3~US5). ①과 ②는 서로 독립이고 ③은 둘 다 필요하다. 작성 세션은 하나로 두고 커밋을 이 단위로 나누기를 권한다
  (중간 상태가 운영에 반영될 일이 없고 검토 맥락이 한 곳에 있다).
- **D7 출처 어긋남의 뜻**(R-01): 버전별 출처 정보로 "청크와 출처 정보가 서로 어긋남"은 생기지 않게 되므로, 이 수를 "되돌린 버전 청크가 문서의 마지막 처리 원본 버전보다 옛 것인 문서 수"로 센다.
- **정책·기록 위치**(R-09·R-11): `eval/gate_policies/<ID>/v<N>.toml`, `eval/gate_records/<gate_id>.json`.
- **활성화의 재판정**(R-11): 활성화가 게이트 기록을 그대로 믿지 않고 같은 입력으로 다시 판정해 결과가 같은지 본다. 그래서 활성화는 입력 실행 기록 파일과 정책 파일이 있는 저장소 체크아웃에서 돌려야 한다.
- **벡터 근사 색인 한계**(R-01): HNSW 색인을 모든 버전이 함께 써서, 임베딩 입력이 바뀌는 재색인은 활성 버전의 벡터 검색 결과를 근사 오차 범위에서 바꿀 수 있다. 키워드 검색과 출처 정보는 그대로다.
  spec SC-001은 정확 검색과 같아지는 크기로 시험한다. 이 한계를 받아들이고 운영 문서에 적는 안이다. 받아들이지 않으면 재색인 중 활성 버전 벡터 검색을 정확 검색으로 바꾸는 별도 변경이 필요하다.
- **재색인이 내린 문서를 처리하지 않음**(R-02): spec에 없는 경로지만 FR-005("내린 문서가 빠지는 것만 다르다")를 지키려면 필요하다. 그 문서들은 활성화 뒤 첫 동기화가 다시 처리한다.

## 다른 명세에 넘기는 것

| 대상 | 넘기는 내용 |
| --- | --- |
| QK-EVL-001·QK-RET-001 | 후보 A·B·C 밖의 평가 대상(청킹 변경, 코드 청킹·Confluence 켜짐, 모델 교체)과 규칙이 같은 기준·후보의 평가 대상 이름 규칙(R-13) |
| ADR-010 결정 뒤 작업 | C를 고르면 D6 토크나이저 변경 방법 결정과 구현(R-12) |
| US6 운영 실행 작업 | 운영 마이그레이션, 첫 게이트 정책 값, 재색인·게이트·활성화 1회와 증빙(quickstart 3절) |
| QK-SYN-003 | 정리한 버전이 남긴 쓰지 않는 임베딩 벡터 정리 |
| QK-SYN-001 후속(사람 결정) | 불일치 중 예약 실행에서 일반 내림을 풀지(spec D2) |

## Complexity Tracking

| 항목 | 이유 | 더 단순한 대안을 고르지 않은 이유 |
| --- | --- | --- |
| 새 저장 경계 `IndexVersionStore` | 활성화·되돌리기·정리·상태가 동기화와 다른 질의와 잠금 범위를 쓴다 | `SyncStore` 확장 — 동기화 경계와 가짜 구현이 넓어진다(R-15) |
| 활성화의 재판정 | 게이트 기록 판정 필드를 고친 파일로 활성화하는 일을 막는다 | 지문만 확인 — 판정을 고친 뒤 지문을 다시 만들면 통과한다(R-11) |
| 청크 행 출처 열 | 재색인 중 활성 버전 출처 정보 불변(FR-005) | 재색인 중 자료 행 갱신 생략 — 원본 변경 문서에서 어긋난다(R-01) |
