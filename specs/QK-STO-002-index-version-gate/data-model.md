# Data Model: QK-STO-002 인덱스 버전 생성·평가 게이트·활성화

**Spec**: [spec.md](spec.md) | **Research**: [research.md](research.md)

## 1. 저장 스키마 (마이그레이션 `0009_index_versions.sql`, research R-18)

### 1.1 `qk.chunk` 출처 열 (R-01)

| 열 | 형식 | 채우는 곳 |
| --- | --- | --- |
| `source_url` | `text` NULL | `_replace_chunk_rows`가 같은 트랜잭션의 `qk.artifact.source_url` |
| `source_modified_at` | `timestamptz` NULL | `qk.artifact.source_modified_at` |
| `collected_at` | `timestamptz` NULL | `qk.artifact.collected_at` |

- 마이그레이션이 기존 행을 자료 행 값으로 채운다. 새 코드가 쓰는 행은 세 열을 언제나 채운다(`source_url`·`collected_at`은 NULL이 아님).
- `qk.hit_json`과 `PostgresStore.trace_chunk`는 `coalesce(c.source_url, a.source_url)`, `coalesce(c.collected_at, a.collected_at)`를 쓴다. 원본 수정 시각은 NULL일 수 있어 청크 `source_url`이 NULL인 옛 행만 자료 행 값을 쓴다(구현 중 보완, 2026-11-05). 출력 키는 그대로다.
- 불변식: 한 청크의 출처 정보는 그 청크를 쓴 트랜잭션의 자료 행 값이다. 다른 버전의 문서 처리는 이 청크 행을 바꾸지 않는다(FR-005).

### 1.2 `qk.index_version` 정리 표시

| 열 | 형식 | 뜻 |
| --- | --- | --- |
| `pruned_at` | `timestamptz` NULL | 청크 정리를 시작한(끝나면 마친) 시각. 값이 있고 청크가 남아 있으면 정리 중이다. 검사 제약 `pruned_at IS NULL OR status = 'archived'` |

상태와 전환(FR-001):

| 전환 | 전 | 후 | 명령 |
| --- | --- | --- | --- |
| 첫 활성화 | 대상 `ready`, 활성 없음 | 대상 `active` | `qk-index index activate <버전>`(QK-SYN-001 FR-021, 바뀌지 않음) |
| 활성화 | 대상 `ready`, V1 `active` | 대상 `active`, V1 `archived` | `qk-index index activate <버전> --gate <기록> --confirm` |
| 되돌리기 | 대상 `archived`(정리 전), V2 `active` | 대상 `active`, V2 `archived` | `qk-index index rollback <버전> --reason … --confirm` |
| 정리 | 대상 `ready`·`archived` | 대상 `archived` + `pruned_at` | `qk-index index prune <버전> --confirm` |
| 재사용 | 대상 `archived`(정리 여부 무관) | 대상 `ready`, `pruned_at = NULL` | `qk-index run --reindex`(현재 설정 버전이 그 ID일 때) |

`activated_at`은 마지막으로 활성이 된 시각으로 덮어쓴다. 활성 이력은 전환 기록(1.3)이 정한다.

### 1.3 `qk.index_transition` (R-07)

| 열 | 형식 | 뜻 |
| --- | --- | --- |
| `id` | `bigint` IDENTITY PK | |
| `kind` | `text` CHECK `first_activation`·`activation`·`rollback`·`prune`·`reuse` | |
| `at` | `timestamptz` DEFAULT `now()` | |
| `version` | `text` FK `qk.index_version(id)` | 대상 버전 |
| `before_active` | `text` NULL | 전환 전 활성 버전 |
| `after_active` | `text` NULL | 전환 뒤 활성 버전 |
| `documents`, `chunks` | `int` | 전환 시점 대상 버전의 노출 문서 수·청크 수 |
| `target` | `text` CHECK `local`·`remote`·`unknown` | 실행 위치(`target_label`). `unknown`은 마이그레이션 채움 행만 |
| `gate_record_id`, `gate_record_sha256` | `text` NULL | 활성화만. 둘 다 있거나 둘 다 없다 |
| `reason` | `text` NULL | 되돌리기만. 1~200자, 비밀값 규칙 통과 |
| `provenance_mismatch` | `int` NULL | 되돌리기만(R-01 D7) |
| `deleted_chunks` | `int` NULL | 정리만 |
| `details` | `jsonb` DEFAULT `'{}'` | 활성화: 게이트 요약(정책 ID·버전, 세트별 지표·판정 질문 수, 임베딩 모델, 질문 세트 버전, FR-032). 첫 활성화 채움: `{"backfilled": true}` |

검사 제약: `activation`이면 게이트 두 열이 NOT NULL, `rollback`이면 `reason` NOT NULL, `prune`이면 `deleted_chunks` NOT NULL. 사람 이름 열은 없다.

### 1.4 `qk.sync_run.kind`

`text NOT NULL DEFAULT 'sync' CHECK (kind IN ('sync', 'reindex'))`. 재색인 실행만 `reindex`다(R-02).

### 1.5 `qk.artifact.processed_outcome`

허용 값에 `not_target`을 더한다(R-03). 뜻: 이 자료는 `processed_index_version` 버전의 청킹에서 대상 아님이었고, 그 버전이 활성일 때의 다음 동기화가 내린다.

## 2. 도메인 값

### 2.1 동기화 (`domain/sync.py`에 더함)

- `ChangeReason.NOT_TARGET_PENDING`: 재색인이 아닌 실행에서 `processed_outcome = 'not_target'`이고 `processed_index_version`이 현재 설정 버전인 자료(R-03).
- `SyncOptions.reindex: bool = False`(`sync/run.py`). `trigger = 'schedule'`이나 `source`와 함께면 `ValueError`.
- `DocumentDecision.not_target: bool = False`. 재색인에서 노출 문서의 청킹 결과가 `NOT_MARKDOWN`일 때 참이고 `actions = (PROCESS,)`, 청크 0개다(R-03). `sync/execute.py`가 처리 결과 `not_target`으로 쓴다.
- 재색인에서 지금 노출되지 않는 저장 문서의 `PROCESS`는 `HOLD`로 바꾼다(R-02). 결과의 `failure`에 `reindex_hidden`을 남긴다. 자료원 단위 보류(`HoldReason`, `ALLOWED` 표)에는 더하지 않는다.
- `RunInfo.kind: str = 'sync'`(`ports/sync.py`).

### 2.2 덮음 (`sync/versions.py`)

`Coverage(version, visible, covered, remaining, failed: tuple[FailedDoc, ...])`. `FailedDoc(display, stage, run_id)`. 정의는 research R-04. 현재 설정 버전에만 계산한다.
불변식: `covered + remaining = visible`, `len(failed) ≤ visible`.

### 2.3 버전 스냅샷 (`ports/index_versions.py`)

`VersionRow(id, embedding_model, dimension, chunking_version, metadata_schema_version, status, created_at, activated_at, pruned_at, documents, chunks, chunks_without_vector, ever_active, last_reindex)`.
`last_reindex = RunRef(run_id, status, finished_at) | None`.

`ActivationState`(활성화 조건 계산 입력, 한 트랜잭션에서 읽음): 활성 버전, 대상 `VersionRow`, 실행 중 동기화 여부, 덮음, 본문 삭제 대기에 대상이 든 문서 수, 운영 키워드 색인 토크나이저,
운영 자료원 이름 목록.

`RollbackState`: 활성 버전, 대상 `VersionRow`, 실행 중 동기화 여부, 본문 삭제 대기에 대상이 든 문서 수, 대상 버전 청크가 없는 노출 문서 수, 출처 어긋남 문서 수(R-01).

`PruneState`: 대상 `VersionRow`, 활성 버전, 현재 설정 버전, 가장 최근 보관 버전(되돌리기 대상), 남은 청크 수.

### 2.4 조건 이름

활성화(FR-021, 번호는 spec 조건 번호):

| 번호 | 이름 | 실패 조건 |
| --- | --- | --- |
| (1) | `current_version`, `ready_version` | 대상이 현재 설정 버전이 아님, 대상이 `ready`가 아님 |
| (2) | `last_reindex` | 대상 버전에 쓴 마지막 `kind = 'reindex'` 실행이 없거나 `succeeded`가 아님 |
| (3) | `coverage`, `failed_documents` | `covered < visible`, 처리 실패 문서 ≥ 1 |
| (4) | `missing_vectors` | 대상 버전 청크 가운데 `embedding_id IS NULL` ≥ 1 |
| (5) | `visible_documents` | 활성화하면 노출될 문서(대상 버전 청크가 있고 노출 조건을 채우는 자료) 0 |
| (6) | `gate_verdict`, `gate_candidate`, `gate_baseline`, `gate_policy`, `gate_integrity` | 판정이 통과가 아님, 후보 ≠ 대상, 기준 ≠ 지금 활성, 정책이 `origin/main` 병합 최신이 아님(R-09), 지문·재판정 불일치(R-11) |
| (7) | `keyword_rule` | 대상이 `INDEX_KEYWORD_RULES`에 없음 |
| (8) | `tokenizer` | 운영 키워드 색인 토크나이저 ≠ 게이트 기록 후보 토크나이저(R-12) |
| (9) | `retrieval_settings` | `RetrievalSettings()`의 `query_rule`·`candidates`·`rrf_k` ≠ 정책 `search` |
| (10) | `purge_pending` | `purge_pending`에 대상이 든 자료 ≥ 1 |
| (11) | `sync_running` | 잠금을 못 잡음 또는 `status = 'running'`인 실행이 있음 |

활성 버전이 없으면 `no_active_version`으로 거부하고 첫 활성화를 안내한다(FR-020).

되돌리기(FR-023·FR-024): `reason_required`(사유 없음·200자 초과), `reason_secret`(비밀값 규칙), `not_archived`, `pruned`, `never_active`, `purge_pending`, `sync_running`,
`provenance_unconfirmed`(출처 어긋남 ≥ 1이고 `--confirm-stale` 없음), `no_active_version`.

정리(FR-027): `active_version`, `current_version`, `rollback_target_unconfirmed`(가장 최근 보관 버전이고 `--confirm-rollback-target` 없음), `sync_running`, `unknown_version`(그런 버전 없음). 이미 정리된 버전은 남은 청크 0이면 바뀌는 것 없이 성공이다(확인 옵션과 관계없이 종료 0).
정리는 청크를 지우기 전에 그 버전을 가리키는 `qk.artifact.processed_index_version`을 비운다. 그래서 그 버전을 다시 쓰는 재색인이 모든 문서를 다시 처리하고, 중단돼도 덮음이 청크 없는 문서를 세지 않는다(구현 검토 반영, 2026-11-05).

활성화 (6)의 `gate_baseline`은 잠금 안에서도 게이트 기록 기준 버전과 지금 활성 버전을 다시 비교한다. 게이트 기록을 읽지 못하면 (8)·(9)는 판단하지 않고 `gate_integrity`만 낸다.
`sync_running`만 남은 거부는 종료 6이다(잠금 경합과 실행 중 기록 모두).

## 3. 게이트 값 (`gate/`)

### 3.1 정책 `GatePolicy` ([contracts/gate-policy.md](contracts/gate-policy.md))

`id`, `version`, `mode`(기본 `hybrid`), `sets: tuple[SetRule]`, `guardrails: tuple[Guardrail]`, `tokenizers(baseline, candidate)`, `search(query_rule, candidates, rrf_k)`, `path`, `sha256`.
`SetRule(id, version, fingerprint, min_judged, max_drop: {recall_at_5, mrr})`. `Guardrail(kind: G1|G2|G3, set, mode, limit: Fraction)`.
검증: 세트 ID 중복 없음, `max_drop`·`limit` ≥ 0, `min_judged` ≥ 1, G2의 세트는 식별자 세트여야 함(판정 때 확인), G3의 방식은 `keyword`.

### 3.2 판정 입력과 출력

- `GateRequest(policy, records: tuple[(path, sha256, RunRecord)], baseline_target, candidate_target, baseline_version, candidate_version, history: HistoryFacts)`.
- `HistoryFacts(main_ref, policy_merge_commit | None, policy_matches_main: bool, newer_policy_on_main: bool, record_commit_contains_policy: {run_id: bool | None}, judge_commit, judge_dirty)`. `None`은 실행 기록 커밋이 없음.
- `Verdict`: `pass`·`fail`·`undecidable`.
- `SetResult(set_id, set_version, judged, excluded: ((question_id, reason),…), metrics: {recall_at_5, mrr}: (baseline, candidate, diff), guardrails: (GuardrailResult,…), regressions, improvements, violations)`.
- `GuardrailResult(kind, mode, judged, baseline, candidate, value, limit, ok)`. `judged`는 가드레일 판정 질문 수(R-10 5단계).
- 불변식: `undecidable`이면 `sets`는 비어 있고 `undecidable_reasons`가 1개 이상(`judged_counts`는 계산된 세트만). `pass`·`fail`이면 사유 0개. `fail`이면 `violations`가 1개 이상.

### 3.3 게이트 기록 `GateRecord` ([contracts/gate-record.md](contracts/gate-record.md))

판정 출력 + 정책 참조 + 입력 실행 기록 참조 + 기준·후보 정보(인덱스 버전, 임베딩 모델, 토크나이저, 대상 이름) + `query_vectors_differ` + 평가가 다룬 자료원 + 판정 코드 커밋.
질문 문장·핵심 사실·라벨 근거 낱말·검색어·청크 본문·접속 정보는 없다(SC-007).
