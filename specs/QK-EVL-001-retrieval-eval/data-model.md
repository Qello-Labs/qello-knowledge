# Data Model: QK-EVL-001

**Date**: 2026-10-31 | **Spec**: [spec.md](spec.md) | **Research**: [research.md](research.md)

새 데이터베이스 테이블·열·마이그레이션은 없다. 아래 타입은 `src/qello_knowledge/evaluation/`(순수)과 `ports/evaluation.py`(경계)에 둔다.
질문 문장은 `repr`에 나오지 않게 한다(`field(repr=False)`, QK-RET-001 `RetrievalRequest`와 같은 방식).

## 1. 질문 세트 (파일 → `QuestionSet`)

파일 필드와 검증 규칙은 [contracts/question-set.md](contracts/question-set.md).

| 타입 | 필드 | 규칙 |
| --- | --- | --- |
| `SourceLabel` | `name`, `label_commit` | 이름은 세트 안에서 유일, 커밋은 40자 소문자 16진수 |
| `Evidence` | `source`, `location` | `source`는 세트 자료원 목록 안. 질문 안에서 (source, location) 중복 금지 |
| `Question` | `id`, `text`(repr 없음), `type`, `label`, `evidence`, `facts`(repr 없음), `origin`, `identifier_form`, `query_form`, `label_terms`(repr 없음), `original_number` | contracts 4절 |
| `QuestionSet` | `id`, `version`, `sources`, `labeling`, `created`, `confirmed`, `confirmed_on`, `origin_set`, `shortfall`, `questions`, `fingerprint` | `fingerprint`는 파일 바이트 SHA-256 |
| `SetIssue` | `question_id`(머리 정보면 `None`), `field`, `rule` | 값·문장을 담지 않는다 |
| `SetCheck` | `ok`, `issues`, `counts`(질문, 유형별, 라벨 상태별, 미완료), `warnings` | `warnings`는 대상 지정 시 근거 미색인(질문 ID, 근거 위치) |

열거값:

- `QuestionType`: `code`, `doc`, `meeting`, `synthesis`, `no_answer`
- `LabelStatus`: `done`, `pending`
- `QuestionOrigin`: `team`, `synthetic`
- `IdentifierForm`: `camel`, `pascal`, `acronym`, `digit`, `snake`, `kebab`, `url_path`
- `QueryForm`: `original`, `partial`, `sentence`

지표 대상(`is_metric_target`): `label == done` 이고 `type != no_answer`. 대상별 근거 미색인은 실행 때 정하고 `skipped` 결과로 남긴다(3절, research R-08).

## 2. 평가 대상 (`ports/evaluation.py`)

```text
EvalTarget (Protocol)
  describe() -> TargetDescription
  documents() -> tuple[TargetDocument, ...]      # 노출 청크가 하나 이상인 문서(R-04)
  store: RetrievalStore                          # retrieve가 쓰는 것과 같은 저장소

DayUsageReader (Protocol)
  today() -> AnswerUsageToday                    # 읽기 전용, 쓰기 메서드 없음
```

| 타입 | 필드 |
| --- | --- |
| `TargetDescription` | `database`, `index_version`, `embedding_model`, `dimension`, `index_rule`, `tokenizer`(읽지 못하면 `None`), `commits`(자료원 이름 → 원본 리비전), `synced_at`, `sources`, `unlocated_documents`(노출 청크가 있는데 `source_name`·`location`이 빈 자료 수. 0이 아니면 실행 전에 거부) |
| `TargetDocument` | `source`(`qk.artifact.source_name`), `location`(`qk.artifact.location`), `source_url` |
| `Candidate` | `A`, `B`, `C` — (`index_rule`, `tokenizer`)로 정한다. 셋에 맞지 않으면 실행 전에 거부(research R-05) |
| `AnswerUsageToday` | 기존 `domain/generation.py` 타입을 그대로 쓴다(`usage_day`, `generation_used`, `query_embedding_used`, `index_used`, `day_total`, `query_reserve` 등). 파싱은 기존 `answer_usage` |

상태: 대상 설명은 실행 전에 한 번 읽고 실행 내내 고정한다. 검색 요약의 인덱스 버전이 이 값과 다르면 실행을 멈춘다(research R-08).

## 3. 평가 실행

```text
RunRequest
  question_set: QuestionSet
  targets: tuple[str, ...]           # 데이터베이스 이름, 순서가 곧 표 순서
  modes: tuple[RetrievalMode, ...]   # 기본 (vector, hybrid, keyword)
  settings: RetrievalSettings        # 요청 단위 설정. 지정하지 않으면 운영 기본값
  filters: SearchFilter              # 기본 NO_FILTER
  usage_target: str                  # 질의 임베딩 사용량을 기록할 대상(research R-06)
  retry: RetryPolicy                 # 질의 경로 RetryPolicy(max_retries=1). 호출 상한도 이 값에서 계산
  allow_query_embedding: bool
  max_neurons: float | None          # 사람이 미리 보기를 보고 허락한 상한(research R-07)
  allow_remote_read: bool
```

| 타입 | 필드 | 비고 |
| --- | --- | --- |
| `CostPreview` | `questions`, `max_calls`, `estimated_neurons`, `day_usage`(못 읽으면 `None`), `remaining`, `query_reserve`, `blocked_reason` | `blocked_reason`: `approval_missing`, `ledger_not_production`, `remote_read_not_allowed`, `ledger_unreadable`, `over_remaining`, `over_max_neurons`, `None` |
| `RunConditions` | spec 용어 "실행 조건" 전부 + `usage_target`, `ledger_target`(`remote`·`none`) | 기록 2절 |
| `QuestionResult` | `question`, `target`, `mode`, `status`, `skipped_reason`, `omitted`, `keyword_terms`, `result_count`, `first_evidence_rank`, `top5`, `unindexed_evidence`, `result_digest` | 이름·뜻은 contracts/run-record.md 5절과 같다. 실패는 `status` 값 |
| `TopHit` | `rank`, `source`, `location`, `evidence` | 문서 위치만 |
| `RunRecord` | `schema`, `run_id`, `complete`, `stop_reason`, `conditions`, `targets`, `questions`, `results`, `usage` | `usage`: 실제 제공자 호출 수, Neurons(측정·추정 구분) |

상태 전이:

```text
created → prechecked → (cost_previewed) → running → complete
                 │                │            └→ incomplete(stop_reason: provider_quota | query_embedding_unavailable | store_unavailable | index_version_changed | interrupted)
                 └→ refused(외부 호출 0)   └→ refused(질의 임베딩 0)
```

`refused`는 기록 파일을 쓰지 않는다. `incomplete`는 기록을 쓰되 비교·리포트가 받지 않는다(FR-021).

## 4. 지표

| 타입 | 필드 |
| --- | --- |
| `Ratio` | `numerator`, `denominator`, `value`(`Fraction`, 출력은 소수 넷째 자리) |
| `MetricSet` | `recall_at_5`, `mrr`, `top20`, `precision_at_5`(식별자 세트만), `mean_results`·`cap_hit`(키워드 전용만), `excluded`(사유별 수), `failures`(종류별 수), `omitted`(사유별 수), `zero_terms` |
| `Breakdown` | 분류 키(`type`, `identifier_form`, `query_form`) → `MetricSet` |

지표 정의는 spec FR-017, 계산 규칙은 research R-09.

## 5. 비교

| 타입 | 필드 |
| --- | --- |
| `ComparisonInput` | 실행 기록 하나 이상과 대상 이름 목록 |
| `ConditionMismatch` | 항목 이름, 기록별 값 |
| `CommonSet` | 방식 → (질문 ID 목록, 뺀 질문 ID와 사유) |
| `ComparisonTable` | 후보별 `MetricSet`(공통 질문 집합), `vector_differs`(질문 ID 목록), `different_runs`(bool) |

비교 거부 조건과 공통 질문 집합 규칙은 spec FR-024·FR-025, research R-11.
