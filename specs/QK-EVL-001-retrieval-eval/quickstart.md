# Quickstart: QK-EVL-001

**Spec**: [spec.md](spec.md) | **Contracts**: [cli.md](contracts/cli.md), [question-set.md](contracts/question-set.md), [run-record.md](contracts/run-record.md)

## 1. 기본 검증 (외부 호출 0)

```bash
python scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
uv run qk-dev db up
QK_REQUIRE_LOCALDB=1 uv run pytest
```

| 확인 | 시험 위치(예정) | 방법 |
| --- | --- | --- |
| SC-001 형식 규칙 | `tests/unit/evaluation/test_question_set.py` | contracts/question-set.md 4절 규칙마다 그 규칙 하나만 어긴 파일 1개 이상 + 올바른 파일. 출력에 질문 문장·핵심 사실 0건 |
| SC-002 H05 v2 옮김 | `tests/unit/evaluation/test_golden_v1.py`(세트 파일과 같은 커밋, research R-14) | H05 v2 Markdown 표를 읽어 골든 세트 v1과 번호·문장·근거·핵심 사실 대조(11문항) |
| SC-003 지표 | `tests/unit/evaluation/test_metrics.py` | 손으로 정한 순위 사례(spec SC-003 목록)의 기대값과 소수 넷째 자리 비교 |
| SC-004 재현 | `tests/localdb/evaluation/test_eval_run.py` | 작은 시험 색인에서 가짜 제공자로 두 번 실행. 키워드 전용 질문별 결과 지문·첫 근거 순위가 같고, 기록으로 다시 계산한 지표 = 출력 |
| SC-005 관문 | `tests/unit/evaluation/test_prechecks.py`, `tests/localdb/evaluation/test_eval_target.py` | 어긋나는 사례마다(`index_rule_unknown`, `tokenizer_unknown`, `source_url_duplicate` 포함) 가짜 제공자 호출 0, 장부 읽기 전에 멈춤. 허락 없음·`ledger_not_production`(로컬 컨테이너·평가 대상을 가리킴)·장부 실패·잔여량 초과·`--max-neurons` 초과에서 질의 임베딩 0 |
| SC-006 벡터 재사용 | `tests/unit/evaluation/test_reuse.py` | 질문 N, 방식 셋, 대상 셋에서 `CountingProvider` 시도 수 = N(일시 실패 없음). 항목 실패도 대상·방식 모두 같은 상태. 호출 상한이 주입한 `RetryPolicy(max_retries=1)`에서 N × 2로 계산됨 |
| 멈춤·미색인 기록 | `tests/unit/evaluation/test_runner.py` | `provider_quota`·`EmbedError`·`store_unavailable`·`no_active_index`에서 미완료와 사유. 벡터 전용 임베딩 실패(요약 인덱스 버전 `None`)는 질문별 실패로 남고 멈추지 않음. 모든 대상에서 근거 미색인인 질문이 대상·방식마다 `skipped`로 남음 |
| SC-007 비교 | `tests/unit/evaluation/test_compare.py` | 조건 하나만 다른 기록 쌍마다 거부와 항목 이름. 같은 조건이면 표, 한 후보에서만 실패·생략된 질문이 공통 집합에서 빠짐 |
| SC-008 비노출 | `tests/unit/evaluation/test_record_schema.py` | 기록·표 객체 키가 계약 목록과 같음, 시험 세트 질문 문장 문자열 0회(문장은 문서 위치와 겹치지 않게 만든다) |
| SC-009 후보 C | `tests/localdb/devtools/test_eval_index_tokenizer.py` | 시험 커밋으로 A를 만든 뒤 C 준비. C의 토크나이저 값, 같은 영문 일부 낱말(예: 시험 문서의 `retryPayment`에서 `payment`)이 A의 키워드 검색에서는 0건이고 C에서는 그 문서를 찾음, A·B 데이터베이스와 원본 DB의 색인 정의 불변, 마이그레이션 파일 목록 불변, 기존 `test_eval_index.py` 그대로 통과 |
| SC-010 외부 호출 0 | 위 시험 전부 | 가짜 제공자·가짜 장부·로컬 DB만. `tests/conftest.py`의 네트워크 차단 그대로 |
| 장부 읽기 전용 | `tests/localdb/evaluation/test_day_usage_reader.py` | 시험용 데이터베이스에서 읽기 전용 연결 구현이 `day_total`을 읽고, 같은 연결로 쓰기를 시도하면 읽기 전용 오류. 실행 전후 장부 행 수 같음. 실행 명령의 관문은 로컬 장부를 거부하므로 이 시험은 연결 구현만 직접 부른다 |
| 경계 | `tests/unit/test_boundaries.py` | `evaluation/`이 `adapters`·`psycopg`·`devtools`를 가져오지 않음 |

## 2. 측정 단계 (사람 승인 뒤, 작업자 PC)

각 단계는 실행 전에 사람이 허락한다. 비용 근거는 [research.md](research.md) R-15.

| 단계 | 하는 일 | 확인 |
| --- | --- | --- |
| H01 | `qk-dev eval-index prepare --rule kw-index-baseline-v1 --commit 6aeccd039b825dcd7a2b6c046a34ef72089a1f78` | 종료 0, `estimated_neurons` 0. 4로 멈추면 사람이 다시 임베딩할지 정한다 |
| H02 | 같은 명령에 `--rule kw-index-idsplit-v1` | 위와 같음. 캐시 원본으로 H01 데이터베이스를 `--from-url-env`로 줄 수 있다 |
| H03 | 같은 커밋에 `--rule kw-index-baseline-v1 --keyword-tokenizer TokenBigramSplitSymbolAlpha` | 종료 0, `tokenizer` 값, 외부 호출 0 |
| H04 | `qk-dev eval check` 두 세트(`--target` H01 데이터베이스), `qk-dev eval identifiers --set` | 통과, 근거 미색인 경고 검토, 식별자 근거 일치. 사람이 식별자 세트를 확정 |
| H05 | 리포트 계약 절과 ADR-010 판단 규칙 커밋 | 사람 확인(research R-14). 이 커밋 뒤로 계약 절을 바꾸지 않는다 |
| H06 | `qk-dev eval run`을 세트마다 대상 셋으로 실행. `--out specs/QK-EVL-001-retrieval-eval/measurement/runs/`(미리 만든 디렉터리)를 주면 `<실행 ID>.json`으로 쓴다. 먼저 `--ledger-url-env`, `--allow-remote-read`만 주고 미리 보기를 본 뒤(종료 4), 사람이 `--allow-query-embedding --max-neurons X`로 다시 실행 | 미리 보기의 예상 Neurons ≤ 잔여량, X ≥ 예상치, 종료 0, 기록 `complete = true` |
| H07 | `qk-dev eval tables`로 대상별·비교 표, 리포트 2~9절 작성 | 리포트 수치 = 표 출력, 확정 세트만 결론에 사용 |
| H08 | ADR-010 Proposed 작성 | 리포트 수치·실행 조건·판단 규칙을 그대로 인용(SC-012) |

정리: 평가용 데이터베이스(최종 이름)는 사람이 `DROP DATABASE`로 지운다. 명령은 `__preparing` 잔여물만 지운다.
