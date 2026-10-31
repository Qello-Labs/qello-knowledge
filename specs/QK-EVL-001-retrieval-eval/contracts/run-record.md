# Contract: 실행 기록 `qk-evl-001-run/v1`

**Spec**: FR-019~FR-022, FR-024, SC-004, SC-008 | **Research**: R-06, R-08, R-10

실행 하나에 JSON 파일 하나다(UTF-8, 키 정렬, 들여쓰기 2칸). 지표·비교표·리포트 4절의 수치는 이 파일만으로 다시 계산한다(FR-020).
QK-STO-002 평가 게이트가 같은 기록을 읽을 수 있게 스키마 이름에 버전을 둔다. 필드를 더하면 스키마 버전을 올린다.

## 1. 최상위

| 키 | 형식 | 뜻 |
| --- | --- | --- |
| `schema` | `"qk-evl-001-run/v1"` | |
| `run_id` | `evl-<YYYYMMDDTHHMMSSZ>-<16진수 8자>` | |
| `complete` | 불리언 | 모든 질문을 돌렸는지 |
| `stop_reason` | `null`·`provider_quota`·`query_embedding_unavailable`·`store_unavailable`·`index_version_changed`·`interrupted` | `complete = false`일 때만 값(research R-08). 검색 결과의 `source_url`이 실행 전에 읽은 문서 표에 없을 때도 대상이 실행 중 바뀐 것으로 보고 `index_version_changed`다 |
| `conditions` | 2절 | |
| `targets` | 3절 배열 | 실행 요청 순서 |
| `questions` | 4절 배열 | 세트의 질문 순서 |
| `results` | 5절 배열 | 질문 → 대상 → 방식 순 |
| `usage` | `{ provider_calls, neurons, measured_neurons, estimated_neurons }` | 실제 제공자 시도 수와 Neurons(research R-06) |

## 2. `conditions`

| 키 | 뜻 |
| --- | --- |
| `question_set` | `{ id, version, fingerprint, confirmed }` |
| `label_commits` | 자료원 이름 → 라벨 기준 커밋 |
| `modes` | 실행한 방식 목록 |
| `query_rule`, `candidates`, `rrf_k` | 요청 단위 검색 설정 |
| `filters` | `{ source_kinds, artifact_kinds }`(기본 빈 배열) |
| `embedding_model` | 질의 임베딩 모델(대상 모두 같아야 실행됨) |
| `query_vector_reuse` | `true`(이 계약에서 언제나 참) |
| `usage_target` | 질의 임베딩 사용량을 기록한 대상 이름. 키워드 전용 실행이면 `null` |
| `ledger` | `{ target: remote|none, usage_day, day_total, remaining, estimated_neurons, max_calls, max_neurons }`. 키워드 전용이면 `target = none`, 나머지 `null` |
| `started_at`, `finished_at` | UTC ISO 8601 |
| `code_commit` | `{ sha, dirty }`. 실행한 저장소 커밋(40자)과 작업 트리에 커밋하지 않은 변경이 있었는지 |

## 3. `targets[]`

`{ database, candidate, index_version, index_rule, tokenizer, embedding_model, dimension, commits, synced_at, documents }`.
`candidate`는 `A`·`B`·`C`(셋에 맞지 않는 대상은 실행 전에 거부, research R-05), `commits`는 자료원 이름 → 원본 리비전, `documents`는 노출 문서 수다.

## 4. `questions[]`

`{ id, type, label, origin, identifier_form, query_form, evidence: [{ source, location }], metric_target }`.
`metric_target`은 라벨 완료이고 `no_answer`가 아닌지다. 대상별 근거 미색인은 5절 `skipped_reason`에 둔다. 값이 없는 선택 필드는 `null`이다.

## 5. `results[]`

| 키 | 형식 | 뜻 |
| --- | --- | --- |
| `question`, `target`, `mode` | 문자열 | |
| `status` | `ok`·`no_results`·`skipped`·`RetrievalFailure` 값 | 실패면 실패 종류 값이 곧 상태다. `skipped`는 그 대상에서 근거 문서가 모두 미색인 |
| `skipped_reason` | `null`·`evidence_unindexed` | |
| `omitted` | `[{ search, reason, detail }]` | 하이브리드 생략. `detail`은 실패 종류 값만 |
| `keyword_terms` | 정수 | 질의 쪽 규칙이 만든 낱말 수(낱말 자체는 없음) |
| `result_count` | 정수 | 통합 결과 수 |
| `first_evidence_rank` | 정수·`null` | 근거 문서 항목이 처음 나온 통합 순위 |
| `top5` | `[{ rank, source, location, evidence }]` | 상위 5건의 문서 위치와 근거 여부 |
| `unindexed_evidence` | 정수 | 그 대상에서 색인되지 않은 근거 문서 수 |
| `result_digest` | 64자 16진수·`null` | 상위 20건 (순위, 자료원, 위치) 열의 SHA-256. 결과 0건이나 실패면 `null` |

지표 대상이 아닌 질문(`no_answer`, 라벨 미완료)은 `results`에 넣지 않고 `questions[].metric_target`으로 다시 센다.
근거 미색인은 대상마다 방식마다 `skipped` 결과로 남긴다. 모든 대상에서 미색인이어도 같다(research R-08). 그래서 결과 수는 (지표 대상 질문 수 × 대상 수 × 방식 수)와 같다.

## 6. 두지 않는 항목

질문 문장(`text`), 핵심 사실(`facts`), 라벨 근거 낱말(`label_terms`), 검색어 낱말, 청크 본문, 청크 ID, 질의 벡터, 점수, 접속 정보.
스키마 시험은 각 객체의 키가 이 계약의 목록과 같은지 확인하고(목록 밖 키가 있으면 실패), 시험 질문 세트의 질문 문장 문자열이 파일에 0번 나오는지 확인한다(SC-008).

## 7. 쓰기 규칙

- 기록 경로가 이미 있으면 쓰지 않고 인자 오류로 멈춘다. 같은 실행을 다시 하면 새 실행 ID와 새 파일이 생긴다(FR-021).
- 임시 이름(`<경로>.partial`)에 쓴 뒤 이름을 바꾼다. 미완료도 같은 방식으로 쓴다. 미완료 기록은 지금까지 끝낸 질문의 결과만 담는다(위 결과 수 규칙은 완료 기록에만 해당).
- 실행 전 검사나 비용 관문에서 멈추면(외부 호출 0) 기록을 쓰지 않는다.
