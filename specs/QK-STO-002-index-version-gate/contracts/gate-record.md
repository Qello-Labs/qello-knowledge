# Contract: 게이트 기록 `qk-sto-002-gate/v1`

**Spec**: FR-015~FR-019, FR-021 (6), FR-032, SC-003, SC-007 | **Research**: R-10, R-11

판정 하나에 JSON 파일 하나다(UTF-8, 키 정렬, 들여쓰기 2칸, 끝에 줄바꿈 하나). 판정 불가도 기록을 쓴다. 필드를 더하면 스키마 버전을 올린다.

## 1. 최상위

| 키 | 형식 | 뜻 |
| --- | --- | --- |
| `schema` | `"qk-sto-002-gate/v1"` | |
| `gate_id` | `gate-<YYYYMMDDTHHMMSSZ>-<16진수 8자>` | |
| `judged_at` | UTC ISO 8601 | |
| `verdict` | `pass`·`fail`·`undecidable` | |
| `undecidable_reasons` | 4절 이름 배열(정렬) | `undecidable`일 때만 1개 이상 |
| `violations` | `[{ set, kind, mode, metric }]` | `fail`일 때만 1개 이상. `kind`는 `metric`·`G1`·`G2`·`G3` |
| `policy` | `{ id, version, path, sha256, merge_commit, main_ref }` | `merge_commit`은 40자 또는 `null`(병합 전). `main_ref`는 확인에 쓴 참조 |
| `baseline`, `candidate` | 2절 | |
| `runs` | `[{ run_id, path, sha256, code_commit: { sha, dirty }, set: { id, version, fingerprint } }]` | 입력 실행 기록. `path`는 저장소 상대 경로 |
| `query_vectors_differ` | 불리언 | 기준·후보가 다른 실행 기록이고 임베딩 모델이 다름(FR-015 (4) 예외) |
| `mode` | 문자열 | 판정 방식 |
| `search` | `{ query_rule, candidates, rrf_k }` | 정책의 요청 단위 검색 설정 |
| `sets` | 3절 배열 | `undecidable`이면 빈 배열 |
| `judged_counts` | `{ <세트 ID>: 정수 }` | 판정 질문 수를 계산할 수 있었던 세트. 판정 불가에서도 남긴다 |
| `covered_sources` | 문자열 배열(정렬) | 입력 실행 기록 `conditions.label_commits`의 자료원 이름 합집합 |
| `judge_commit` | `{ sha, dirty }` | 판정한 저장소 커밋 |
| `limits` | 문자열 배열 | 고정 문구: `"evaluates the index version settings on a local eval target, not production data"`(D1) |

## 2. `baseline` / `candidate`

`{ target, index_version, expected_index_version, embedding_model, tokenizer, index_rule }`. `target`은 실행 기록 `targets[].database`, 나머지는 그 대상 값이다.
`expected_index_version`은 명령 인자(기준 = 운영 활성 버전, 후보 = 준비 버전)다.

## 3. `sets[]`

| 키 | 뜻 |
| --- | --- |
| `id`, `version` | 질문 세트 |
| `judged` | 판정 질문 수 |
| `excluded` | `[{ question, reason }]`. `reason`은 `baseline_skipped`·`baseline_failed:<상태>`·`baseline_omitted` |
| `metrics` | `{ recall_at_5: {...}, mrr: {...} }`. 각 값 `{ baseline, candidate, diff, baseline_fraction, candidate_fraction, max_drop, ok }`. 수치는 소수 넷째 자리 문자열, 분수는 `분자/분모` |
| `guardrails` | `[{ kind, mode, judged, baseline, candidate, value, limit, ok }]`. `judged`는 가드레일 판정 질문 수. G1의 `value`는 질문 수, G2·G3는 차이(G2는 기준 − 후보, G3는 후보 − 기준) |
| `new_failures` | G1에 센 질문 ID 배열 |
| `regressions`, `improvements` | 질문 ID 배열(세트 질문 순서) |

질문 ID와 상태 이름만 담는다. 질문 문장, 핵심 사실, 라벨 근거 낱말, 검색어, 청크 본문, 청크 ID, 점수, 접속 정보는 담지 않는다(SC-007).

## 4. 판정 불가 사유 (FR-015)

| 사유 | 조건 |
| --- | --- |
| `record_schema` | 입력 실행 기록의 `schema`가 `qk-evl-001-run/v1`이 아니거나 읽기 실패 |
| `record_incomplete` | `complete = false` (1) |
| `set_missing` | 정책 세트에 맞는 기록 없음 (2) |
| `set_unconfirmed` | `conditions.question_set.confirmed = false` (2) |
| `set_mismatch` | 세트 ID·버전·지문이 정책과 다름 (2) |
| `target_missing` | 기준·후보 대상 이름이 기록 `targets`에 없음 (3) |
| `index_version_mismatch` | 대상 인덱스 버전 ≠ 기대 인덱스 버전 (3) |
| `condition_mismatch` | 같은 세트의 기준·후보 비교 조건(QK-EVL-001 R-11 항목)이 다름. 임베딩 모델은 예외 규칙(FR-015 (4)) (4) |
| `search_settings_mismatch` | 기록의 `query_rule`·`candidates`·`rrf_k` ≠ 정책 (5) |
| `mode_missing` | 판정 방식이나 가드레일 방식이 기록 `modes`에 없음 (5) |
| `index_rule_unknown` | 대상 `index_rule = unknown` (6) |
| `tokenizer_mismatch` | 대상 토크나이저 ≠ 정책 (7) |
| `policy_unmerged`, `policy_changed`, `code_commit_unknown`, `code_before_policy`, `dirty_code` | R-09 (8) |
| `set_duplicate` | 한 정책 세트에 맞는 실행 기록이 둘 이상 |
| `too_few_judged` | 세트 판정 질문 수 < 정책 `min_judged` (9), 또는 가드레일 판정 질문 0개 |
| `guardrail_set_kind` | G2 세트가 식별자 세트가 아님 |

## 5. 활성화의 확인 (FR-021 (6), R-11)

활성화는 기록을 읽어 다음을 모두 확인한다. 하나라도 어긋나면 해당 조건 이름으로 거부한다.

- `gate_verdict`: `verdict = pass`.
- `gate_candidate`: `candidate.index_version` = 활성화 대상. `gate_baseline`: `baseline.index_version` = 지금 활성 버전.
- `gate_policy`: 정책 파일이 `origin/main`과 같고, 병합 커밋이 있고, 같은 ID의 더 높은 버전이 `origin/main`에 없음.
- `gate_integrity`: `runs[].path` 파일의 SHA-256 = `runs[].sha256`, 정책 파일 SHA-256 = `policy.sha256`, 같은 입력으로 다시 판정한 `verdict`·`sets`·`violations`가 기록과 같음.
  다시 판정의 기대 인덱스 버전은 기록 값이 아니라 활성화가 정한 값(기준 = 지금 운영 활성 버전, 후보 = 활성화 대상)이고, 대상 이름은 기록의 `baseline.target`·`candidate.target`이다.
  실행 기록·정책 파일은 저장소에 커밋돼 있어야 다른 체크아웃에서도 이 확인이 통과한다.

전환 기록에는 `gate_id`와 기록 파일 SHA-256을 남긴다.
