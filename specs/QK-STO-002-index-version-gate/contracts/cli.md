# Contract: 명령

**Spec**: FR-004~FR-011, FR-015, FR-018~FR-029, FR-034 | **Research**: R-02, R-05, R-08, R-09, R-11, R-15~R-17

운영 저장소를 바꾸는 명령은 지금 `qk-index` 규칙을 따른다. 원격 대상이면 `--allow-remote`가 있어야 하고(없으면 종료 3 `remote_confirmation_required`),
저장소 정책 파일(`config/store_policy.toml`)이 유효해야 한다(없으면 종료 1 `store_policy_required`). 모든 명령은 `--json`과 `--env-file`(기본 `.env`)을 받는다.
출력은 지금처럼 출력 규칙(`_rescreen`)을 거친다. 본문·질문 문장·접속 정보를 내지 않는다.

공통 종료 코드: 0 성공, 1 조건 미충족·입력 오류(`schema_outdated` 포함), 2 저장소 접근 불가(`store_unavailable`), 3 원격 확인 옵션 없음, 4 미리 보기만 함(조건 모두 충족), 5 예산 초과, 6 동기화 실행 중.
argparse 인자 오류도 종료 2다(지금 `qk-index`와 같다). 둘은 출력의 `error` 값(`store_unavailable`)이나 argparse 사용법 출력으로 가른다.
Postgres 저장소는 마이그레이션 `version >= 9` 적용 여부를 본다. 쓰는 명령과 `index status`는 0009가 없으면 쓰기 없이 종료 1 `schema_outdated`다(research R-18).

## 1. `qk-index run --reindex` (US1)

| 옵션 | 뜻 |
| --- | --- |
| `--reindex` | 재색인 실행. 지금 `run`의 모든 점검(설정, 자료원 검토, 보안 정책, Confluence 등록 검사)을 먼저 한다 |
| `--preview` | 미리 보기만. 원본 읽기는 하고 임베딩 호출·저장소 쓰기는 0(FR-006) |
| `--allow-partial-budget` | 예산 초과일 때 예산 안 부분 실행(FR-006) |
| `--confirm-takedown`, `--allow-remote` | 지금 `run`과 같다 |

- `--trigger schedule`이나 `--source`와 함께 쓰면 인자 오류(종료 2, argparse). `--trigger manual`은 허용한다.
- 쓰기 전 거부: 활성 버전 없음 → 종료 1 `no_active_version`(첫 색인은 `run`), 현재 설정 버전 = 활성 버전 → 종료 1 `not_mismatched`.
- 미리 보기 출력 키(지금 `--preview` 키에 더함): `reindex: { candidate, candidate_status, documents, to_process, embedding: { requested, cache_hits, to_embed, estimated_neurons, basis }, budget: { index_budget, used_today, remaining_today }, estimated_days, coverage: { visible, covered, remaining, failed }, hidden_held, security_takedowns }`.
  `hidden_held`는 지금 노출되지 않아 처리하지 않는 문서 수(research R-02), `security_takedowns`는 이 계획의 보안 내림 수다.
  종료 0(실행 가능) 또는 5(예산 초과).
- 실행: 예산 초과이고 `--allow-partial-budget`이 없으면 실행 기록 없이 종료 5 `budget_exceeded`(출력에 `security_takedowns`를 보이고 다음 예약 실행이 반영한다고 안내). 그 밖에는 지금 `run`과 같은 출력에 `reindex` 요약(후보, 덮음)을 더한다.
  종료 코드는 지금 `run`과 같다(0 성공, 4 일부 실패, 5 멈춤, 6 실행 중).
- 재색인이 아닌 실행의 불일치 보고에는 요약 `index_mismatch: { active, current, coverage, resolutions }`를 더한다(FR-008, US1-6, US4-2). `resolutions`는 2절과 같다. 동작은 그대로다.

## 2. `qk-index index status` (US5, FR-026)

읽기 전용. 지금 키 `active`, `ready`, `current`, `matches`는 그대로이고 다음을 더한다.

- `mismatch_since`: research R-17. 일치면 `null`.
- `versions`: 버전마다 `{ id, status, embedding_model, dimension, chunking_version, metadata_schema_version, created_at, activated_at, pruned_at, documents, chunks, last_reindex, ever_active, prune_candidate, rollback_target }`.
  `prune_candidate`는 `ready`이고 현재 설정 버전이 아님 또는 `archived`이고 정리 전. `rollback_target`은 정리 전 보관 버전 가운데 가장 최근 보관된 것.
- `coverage`: 불일치면 현재 설정 버전의 `{ visible, covered, remaining, failed: [{ display, stage, run_id }] }`, 아니면 `null`. `versions[]` 항목마다 `coverage` 키가 있고 현재 설정 버전만 값이 있다. 그 밖은 `null`이고 `coverage_note: "not_current_version"`이다(research R-04).
- `resolutions`: 불일치면 `["reindex_gate_activate", "redeploy_active_settings"]`, 아니면 `[]`. 텍스트 출력은 각 절차를 한 줄로 설명한다.

종료 0 또는 2.

## 3. `qk-index index activate <버전>` (US3, FR-020~FR-022)

| 옵션 | 뜻 |
| --- | --- |
| (없음) | 활성 버전이 없으면 지금 첫 활성화 그대로(QK-SYN-001 FR-021, 전환 기록 `first_activation`만 더함) |
| `--gate <게이트 기록 경로>` | 활성 버전이 있을 때 필수. 없으면 종료 1 `gate_record_required` |
| `--confirm` | 조건을 모두 채우면 전환한다. 없으면 미리 보기만 |
| `--allow-remote` | 지금과 같다 |

- 활성 버전이 있고 `--gate`가 있으면 data-model 2.4 활성화 조건을 계산한다.
- 미리 보기 출력(US3-3): `{ baseline: { version, documents, chunks }, candidate: { version, documents, chunks, chunks_without_vector }, coverage, failed_documents, purge_pending_documents,
  gate: { gate_id, verdict, policy, sets: [{ id, version, judged, recall_at_5, mrr }] }, retrieval_settings: { policy, code_defaults }, uncovered_sources, notes, failed_conditions, applied: false }`.
  `uncovered_sources`는 운영 `qk.sync_source` 가운데 이름이 게이트 기록 `covered_sources`에 없는 자료원의 `[{ name, kind }]`(spec US3-3 "자료원 종류"). 텍스트 출력은 종류별로 묶는다.
  `notes`에는 벡터 근사 색인 한계 안내(research R-01)를 고정 문구로 둔다.
- 조건 미충족이면 종료 1(미리 보기·실행 모두, `failed_conditions`에 이름을 모두 낸다). 충족이고 `--confirm`이 없으면 종료 4. `--confirm`이면 전환 뒤 `applied: true`, `transition_id`와 함께 종료 0.
- 잠금을 못 잡으면 종료 6 `sync_running`.

## 4. `qk-index index rollback <버전>` (US4, FR-023~FR-025)

| 옵션 | 뜻 |
| --- | --- |
| `--reason <문자열>` | 필수, 1~200자. 사람 이름을 쓰지 않는다 |
| `--confirm` | 전환한다. 없으면 미리 보기만 |
| `--confirm-stale` | 출처 어긋남 문서가 있어도 되돌린다(FR-024, D7) |

- 미리 보기 출력(US4-4): `{ target: { version, documents, chunks }, active: { version }, missing_documents, provenance_mismatch, purge_pending_documents, failed_conditions, applied: false }`.
  `missing_documents`는 지금 노출 문서 가운데 대상 버전 청크가 없는 문서 수.
- 종료 코드는 3절과 같다. 전환 뒤 현재 설정 버전 ≠ 새 활성 버전이면 출력에 `mismatch_after: true`와 2절 `resolutions`를 더한다(US4-2).

## 5. `qk-index index prune <버전>` (US5, FR-027·FR-028)

| 옵션 | 뜻 |
| --- | --- |
| `--confirm` | 지운다. 없으면 지울 청크 수만 보인다 |
| `--confirm-rollback-target` | 가장 최근 보관 버전(되돌리기 대상)을 지울 때 필수 |

- 출력: `{ version, status, chunks_to_delete, deleted_chunks, pruned, failed_conditions, applied }`. 미리 보기는 종료 4(조건 충족) 또는 1, 실행은 종료 0.
- 중단된 정리를 다시 실행하면 남은 청크만 지운다. 이미 정리됐고 남은 청크 0이면 바뀌는 것 없이 종료 0.

## 6. `qk-dev eval gate` (US2, FR-012~FR-019)

로컬 도구. DB·외부 호출 0. 저장소 git 이력만 읽는다.

| 옵션 | 뜻 |
| --- | --- |
| `--policy <정책 파일>` | 필수 |
| `--run <실행 기록>` | 필수, 여러 번. 정책 필수 세트마다 하나(모델 교체면 기준·후보 각각) |
| `--baseline-target <대상 이름>`, `--candidate-target <대상 이름>` | 필수. 실행 기록 `targets[].database` |
| `--baseline-version <iv-…>` | 필수. 운영 활성 버전(`qk-index index status`의 `active`) |
| `--candidate-version <iv-…>` | 필수. 후보 준비 버전(`current`) |
| `--out <경로>` | 필수. 이미 있으면 종료 2. 권장 `eval/gate_records/<gate_id>.json`(`{gate_id}` 자리표시자를 받는다) |
| `--main-ref <참조>` | 기본 `origin/main`. 값은 게이트 기록 `policy.main_ref`에 남는다. 활성화는 이 값과 관계없이 `origin/main`으로 다시 확인한다 |
| `--json` | 판정 요약을 JSON으로 |

- 출력: 기록 경로, 판정, 세트별 주 지표(기준·후보·차이·판정 질문 수), 가드레일 결과, 위반, 판정 불가 사유, 회귀·개선 질문 수.
- 종료 코드: 0 통과, 1 실패, 3 판정 불가(셋 모두 기록을 쓴다), 2 인자·정책 검증 오류·출력 경로 있음(기록 없음).
