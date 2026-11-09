# Quickstart: QK-STO-002 검증 안내

**Spec**: [spec.md](spec.md) | **Contracts**: [cli.md](contracts/cli.md), [gate-policy.md](contracts/gate-policy.md), [gate-record.md](contracts/gate-record.md) | **Data model**: [data-model.md](data-model.md)

## 1. 기본 검증 (자동, 0 Neurons)

```bash
python scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
uv run qk-dev db up
QK_REQUIRE_LOCALDB=1 uv run pytest
```

시험은 로컬 DB, 가짜 자료원·가짜 임베딩 제공자, 손으로 만든 실행 기록·게이트 정책 예시만 쓴다(FR-035, SC-008). `-m external`은 넣지 않는다.

| 시나리오 | 확인 | 성공 기준 | 시험 위치 |
| --- | --- | --- | --- |
| 재색인 전후 활성 버전 검색 | V1 활성 상태에서 청킹 설정을 바꿔 재색인, 같은 질의의 상위 20건 비교(원본 변경 문서 포함) | SC-001 | `tests/localdb/sync/test_reindex.py` |
| 재색인 미리 보기 | 대상 문서·청크·캐시·Neurons·예상 일수·덮음, 쓰기 0 | US1-1·US1-9 | `tests/unit/sync/test_reindex_preview.py`, `tests/unit/indexer/test_reindex_cli.py` |
| 이어 하기·중복 없음 | 부분 실행 뒤 재실행, 변경 없는 재색인 두 번 | SC-006 | `tests/localdb/sync/test_reindex.py` |
| 재색인 중 보안·일반 내림·대상 아님 | 비밀값 문서 즉시 제외, 원본 삭제 문서 V1에서 제외, 대상 아님은 내리지 않음, 내렸던 문서(일반·보안 본문 삭제 대기)를 재색인이 되살리지 않음 | US1-4·US1-5, FR-005, FR-010 | `tests/localdb/sync/test_reindex.py`, `tests/unit/sync/test_reindex_plan.py` |
| 예약 실행 보류 | 불일치 중 예약 실행은 재색인하지 않고 보고에 덮음 | US1-6, FR-029 | `tests/unit/sync/test_reindex_plan.py` |
| 설정 재변경·재사용 | V2 중 V3로 바뀜, 보관 ID 재사용 | US1-7·US1-8 | `tests/localdb/sync/test_reindex_versions.py` |
| 게이트 정책 형식 | 형식 예시, 오류 이름마다 하나 | contracts/gate-policy.md | `tests/unit/gate/test_gate_policy.py` |
| 게이트 판정 고정 예시 | 통과, 지표 하락, 후보만 실패, G1~G3 각 하나, 판정 불가 사유마다 하나 | SC-003 | `tests/unit/gate/test_judge.py`(사례 설명 `tests/fixtures/gate/README.md`) |
| 게이트 기록 | 스키마 키, 지문, 덮어쓰기 거부, 금지 문자열 0 | FR-018, SC-007 | `tests/unit/gate/test_gate_record.py` |
| 활성화 쪽 게이트 확인 | 판정·후보·기준·정책·지문·재판정 | FR-021 (6) | `tests/unit/gate/test_gate_verify.py`, `tests/unit/gate/test_repo_history.py` |
| 활성화 조건 | 조건 열한 가지를 하나씩만 어긴 사례에서 거부, 상태·전환 기록 불변 | SC-002 | `tests/unit/sync/test_version_conditions.py`, `tests/localdb/sync/test_index_activation.py` |
| 되돌리기 조건 | FR-023·FR-024 조건을 하나씩만 어긴 사례 | SC-002 | `tests/unit/sync/test_rollback_conditions.py`, `tests/localdb/sync/test_index_rollback.py` |
| 전환 중 동시 검색 | 검색 반복 중 활성화·되돌리기, 섞임·활성 없음 0, `index_version_changed` 수 기록 | SC-004 | `tests/localdb/sync/test_index_switch_concurrency.py` |
| 정리 | 지정 버전 청크 0, 다른 버전 청크·임베딩 그대로, 대기 목록에서 빠짐, 중단 뒤 재실행 | SC-005 | `tests/unit/sync/test_prune_conditions.py`, `tests/localdb/sync/test_index_prune.py` |
| 상태 보기 | 버전 다섯 개 상태 값이 DB와 같음, 해소 방법 | US5-1 | `tests/localdb/sync/test_index_status.py` |
| 명령 계약 | 옵션·종료 코드·원격 확인·출력 키 | contracts/cli.md | `tests/unit/indexer/test_index_cli.py`, `test_index_rollback_cli.py`, `test_index_prune_cli.py`, `tests/unit/devtools/test_gate_cli.py` |
| 저장 변경 | 0009 채우기·제약, 버전별 출처 정보, 첫 활성화 전환 기록, 버전 저장소 읽기 | research R-01·R-07·R-18 | `tests/localdb/sync/test_migration_0009.py`, `test_chunk_provenance.py`, `test_first_activation_transition.py`, `test_index_version_store.py` |
| 기존 기대값 | 첫 활성화, 예약 실행 보류, 실행 기록 스키마 시험이 그대로 통과 | FR-036 | 기존 시험 |
| 배포 순서 보호 | 0009가 없는 DB에서 쓰기 명령이 `schema_outdated`로 쓰기 없이 멈춤 | research R-18 | `tests/localdb/sync/test_schema_guard.py` |

## 2. 로컬 수동 확인 (선택 단계, 완료 판정에 넣지 않음)

`qk-index run`은 Workers AI 제공자와 실제 자료원 설정(`config/sources.toml`)으로 조립돼 CLI에서 가짜 제공자로 바꿀 수 없다(2026-11-05 구현 중 확인).
같은 흐름(첫 색인 → 재색인 → 활성화 → 되돌리기 → 정리)은 주입 시험 `tests/localdb/sync/test_reindex.py`, `test_index_activation.py`, `test_index_rollback.py`, `test_index_prune.py`가 덮는다.
실제 제공자로 따라 하려면 로컬 DB와 비용 승인이 필요하고, 순서는 아래와 같다.

1. 첫 색인과 첫 활성화: `uv run qk-index run` → `uv run qk-index index activate <current>`.
2. 청킹 설정을 바꿔 `uv run qk-index index status`가 `matches: false`와 해소 방법을 보이는지 본다.
3. `uv run qk-index run --reindex --preview` → `uv run qk-index run --reindex`.
4. 손으로 만든 실행 기록 예시(`tests/fixtures/gate/`)와 시험 정책으로 `uv run qk-dev eval gate …`를 돌린다(시험 정책은 `main`에 없어 `policy_unmerged`로 판정 불가가 나오는 것이 정상이다).
5. `uv run qk-index index activate <current> --gate <기록>`이 미리 보기와 `gate_policy` 실패를 보이는지 본다.

## 3. 운영 1회 실행 (US6, 사람 단계, 이 브랜치 밖)

ADR-010 Status 결정과 이 브랜치 병합 뒤 별도 작업으로 한다. 순서와 승인 지점만 적는다. 마이그레이션(H1)은 새 코드 배포보다 먼저다(research R-18).

| 단계 | 하는 일 | 승인 |
| --- | --- | --- |
| H1 | 운영 마이그레이션 `0009_index_versions` 적용(`qk-migrate --dry-run` → 적용 → `applied=0`) → 새 코드 배포 → 예약 동기화 한 번 정상 확인 | 사람 |
| H2 | 게이트 정책 첫 버전 값 결정, 정책만 담은 PR 병합 | 사람(결정자) |
| H3 | 설정 변경 PR 병합·배포(예: ADR-010 B면 키워드 규칙 설정) | 사람 |
| H4 | 예상 Neurons 합계 보고: 재색인 미리 보기 + 평가 대상 준비 + 질의 임베딩 미리 보기, 운영 장부 잔여량과 대조(FR-034, research R-14) | 사람 |
| H5 | `qk-index run --reindex --allow-remote`(필요하면 여러 날) | 사람 |
| H6 | 기준 평가 대상을 활성 버전 커밋으로 준비(`git worktree add <커밋>` 안에서 `qk-dev eval-index prepare`), 후보 대상 준비, `qk-dev eval run` | 사람 |
| H7 | `qk-dev eval gate …` → 입력 실행 기록과 게이트 기록을 저장소에 커밋(활성화가 지문을 다시 확인한다) | 사람 리뷰 |
| H8 | `git fetch origin` 뒤 `qk-index index activate <후보> --gate <기록> --allow-remote` 미리 보기 → `--confirm` | 사람 |
| H9 | 게이트 기록·전환 기록·실제 Neurons를 Jira 증빙으로 남김. 실패·판정 불가도 기록(SC-009) | 사람 |

비용 보고 표(H4):

| 항목 | 예상 Neurons | 근거 |
| --- | ---: | --- |
| 재색인 | 미리 보기 값 | `qk-index run --reindex --preview` |
| 평가 대상 준비(기준·후보) | 준비 명령 미리 보기 값 | `qk-dev eval-index prepare`(캐시 부족 시 종료 4) |
| 질의 임베딩 | 실행 미리 보기 값 | `qk-dev eval run`(종료 4) |
| 합계 / 운영 장부 잔여 | | `qk-index usage` |

## 4. 요구사항 추적

| FR | 설계 위치 |
| --- | --- |
| FR-001~FR-003 | data-model 1.2·1.3, research R-06·R-07·R-08 |
| FR-004~FR-011 | research R-02~R-06, contracts/cli.md 1절, data-model 2.2 |
| FR-012~FR-019 | contracts/gate-policy.md, contracts/gate-record.md, research R-09~R-11·R-13 |
| FR-020~FR-022 | contracts/cli.md 3절, data-model 2.4, research R-08·R-11·R-12 |
| FR-023~FR-025 | contracts/cli.md 4절, research R-01(D7)·R-08 |
| FR-026~FR-029 | contracts/cli.md 2·5절, research R-16·R-17, R-02(예약 실행) |
| FR-030 | research R-05(US1-9)·R-13(평가 대상 확장은 넘김) |
| FR-031 | data-model 2.4 (9) |
| FR-032 | data-model 1.3 `details`, contracts/gate-record.md |
| FR-033 | research R-12 |
| FR-034 | research R-14, 3절 비용 표 |
| FR-035·FR-036 | 1절 |
