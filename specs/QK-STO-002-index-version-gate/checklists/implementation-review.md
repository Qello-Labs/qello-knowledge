# 구현 검토 기록: QK-STO-002

검토자: 작성에 관여하지 않은 별도 서브에이전트(읽기와 시험 실행만, 파일 수정·커밋·외부 호출 없음). 기준: spec·plan·contracts·tasks 승인본, TASK.md, AGENTS.md, 실제 diff.

## 1차 (2026-11-05) — 변경 요청 7건 (API 연결 오류로 한 번 끊긴 뒤 이어서 끝냄)

검토자가 실행한 것: 전체 시험 3,977 passed(변수 이름 변경 전 작업 트리), 관련 시험 440 passed, `ruff check`·`ruff format --check`·`git diff --check`·`preflight` 통과, 1번 재현 시험(scratchpad, 저장소 밖).

| # | 심각도 | 지적 | 반영 |
| --- | --- | --- | --- |
| 1 | 높음 | 정리가 청크만 지우고 `processed_index_version`을 남겨, 설정이 그 버전으로 돌아오면 재색인이 UNCHANGED로 끝나고 덮음이 청크 없는 문서를 세어 활성화 뒤 문서가 사라짐(재현: 10개 중 1개만 검색). 정리 중단 뒤 준비 버전 재사용도 같음 | `prune`이 청크 삭제 전 별도 트랜잭션에서 그 버전을 가리키는 자료 행의 `processed_index_version`을 NULL로. 회귀 시험 2개(`test_index_prune.py`). data-model 2.4 기록 |
| 2 | 중간 | 활성화 잠금 안에서 게이트 기준 버전을 다시 확인하지 않음(FR-003, FR-021 (6)) | `GateFacts.baseline`, `activation_conditions`가 잠금 안 스냅샷의 활성 버전과 비교. 단위 시험 |
| 3 | 중간·낮음 | 예약 동기화 끝의 덮음 계산 연결 실패가 `finish_run`을 막음 | `mismatch_coverage`가 `StoreError`를 잡아 `coverage: null`. 단위 시험 2개 |
| 4 | 낮음 | 게이트 기록을 못 읽으면 `tokenizer`·`retrieval_settings`도 실패로 나옴 | 값이 없으면 (8)(9)를 판단하지 않고 `gate_integrity`만. 단위 시험 |
| 5 | 낮음 | 종료 6이 잠금 실패에만 나옴 | `sync_running`만 남은 거부는 미리 보기·실행 모두 종료 6. 통합 시험 기대값 |
| 6 | 낮음 | 예산 초과 안내 문구, 이미 정리된 버전의 확인 옵션 없는 정리, `unknown_version` 미기재 | `note` 문구, 이미 정리됐으면 종료 0, data-model 2.4 |
| 7 | 낮음 | 판정 불가 사유를 포함 여부로만 단언, SC-001 종단 시험이 출처 열 회귀를 못 잡음 | 정확한 튜플 비교로 바꾸며 사유 둘이 함께 나오던 원인(병합 커밋 없을 때 `code_before_policy`, G2 세트 종류에서 가드레일 계산) 수정. 출처 열은 `test_chunk_provenance.py`가 직접 검증 |

## 2차 (2026-11-05) — 승인 가능, 1차 7건 반영 확인, 새 지적 2건

검토자가 실행한 것: 바뀐 영역 시험 515 passed, 1차 재현 시험 통과(활성화 뒤 문서 10개 모두 검색), `ruff check`·`ruff format --check` 통과. `processed_index_version` NULL 처리가 일반 동기화·덮음·상태 보기·되돌리기·첫 활성화에 주는 부작용이 없음을 사용처 전체로 확인.

| # | 심각도 | 지적 | 반영 |
| --- | --- | --- | --- |
| 1 | 중간(사람 결정으로 남김) | 정리가 중단된 보관 버전은 `pruned_at`이 비어 있어 되돌리기가 거부되지 않고, 청크가 지워진 문서가 검색에서 빠진다(1차 전부터 있던 경로) | 작성 세션이 안전한 쪽(제안 (a))으로 반영: 정리 시작 트랜잭션에서 `archived` + `pruned_at`을 써서 "정리 중"을 표시, 되돌리기는 `pruned`로 거부, 다시 실행하면 마저 지운다. 상태 보기에서 청크가 남은 정리 중 버전은 정리 대상으로 보인다. data-model 1.2 `pruned_at` 뜻 수정. 회귀 시험 `test_interrupted_prune_blocks_rollback_until_finished`. 2차 반영분은 다시 검토받지 않았다 |
| 2 | 낮음 | 0009 확인 질의 중 연결이 끊기면 날 `psycopg` 예외가 저장소 오류로 바뀌지 않음 | `require_schema` 호출을 `_db`의 예외 매핑 안으로 옮김 |
