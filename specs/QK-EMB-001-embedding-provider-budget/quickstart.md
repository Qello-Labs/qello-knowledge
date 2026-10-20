# Quickstart: QK-EMB-001 검증 절차

1~3절은 토큰 없이 로컬에서 끝나고 외부 요청이 0건이다. 4절만 실제 Workers AI를 부르며 사람 승인 뒤에 한다.
경계는 [contracts/embedder.md](contracts/embedder.md), 명령은 [contracts/cli.md](contracts/cli.md), 테이블·함수는 [data-model.md](data-model.md).

## 준비

```bash
uv sync
uv run qk-dev db up
uv run qk-migrate
```

기대: `0003_embedding_usage`가 적용된다. 다시 실행하면 `applied=0`.

## 1. 규칙 단위 테스트 (US1~5)

```bash
uv run pytest tests/unit/embedding tests/contract -v
```

| 테스트 | 확인 | 성공 기준 |
| --- | --- | --- |
| `test_service_basic.py` | 순서·차원·모델 버전, 빈 입력, 출처 없는 색인 입력 거부, 비밀값 전송 직전 차단 | US1 AS1·5, FR-005, SC-006 |
| `test_service_limits.py` | 한도 초과 단독 처리·쪼개기, 나머지 정상 | US1 AS2, FR-003, SC-004 |
| `test_service_failures.py` | 일시 오류 재시도, 할당 소진 즉시 중단, 인증 오류 | US1 AS3·4, FR-004·020 |
| `test_service_cache.py` | 두 번째 실행 호출 0건, 바뀐 1개만 전송, 모델 다르면 미적중, 묶음 중복 1회, 질의 미저장 | US2 AS1~5, SC-001 |
| `test_service_budget.py` | 예산 소진 거부, 질의는 계속, 부분 실행, 하루 경계, 예비분 경고 | US4 AS1~5, SC-002 |
| `test_preview.py` | 외부 호출 0건, 캐시·중복·한도 초과 예상 개수, 예산 초과 판정, 기본 실행 거부 | US5 AS1~4, FR-024 |
| `test_estimate.py` | 바이트 기반 예상 계산과 근거 출력 | FR-023 |
| `test_settings.py` | 예산 합이 할당을 넘으면 설정 검사 실패 | US4 AS6, FR-017 |
| `tests/contract/test_embedding_providers.py` | 가짜·재생 REST 제공자 계약 | contracts/embedder.md |
| `tests/unit/test_boundaries.py` (기존) | 경계 밖에서 제공자 모듈 참조 0건 | SC-007 |

## 2. 사용량 장부 로컬 DB 테스트 (US3·US4)

```bash
QK_REQUIRE_LOCALDB=1 uv run pytest tests/localdb/embedding -v
```

| 테스트 | 확인 | 성공 기준 |
| --- | --- | --- |
| `test_usage_record.py` | 호출 기록 필드, 원문 없음, 추정 표시, 합계 = 가짜 제공자 값 합 | US3 AS1~5, SC-003 |
| `test_reserve_concurrency.py` | 스레드 2개 동시 예약에서 초과 폭 ≤ 요청 하나 | FR-021, SC-002 |
| `test_day_boundary.py` | 23:59:59 UTC와 00:00:00 UTC 기록이 다른 날로 집계 | US4 AS4 |
| `test_prune.py` | 90일 지난 날 일 합계 이동·삭제, 두 번째 실행 0건 | FR-025 |
| `test_find_embeddings.py` | 묶음 캐시 조회 | R-07 |

## 3. CLI

```bash
uv run qk-index usage
uv run qk-index usage --json
uv run qk-index usage prune
QK_EMBED_INDEX_BUDGET=8000 uv run qk-index check
```

기대: 첫 세 명령은 종료 코드 0. 마지막은 8000 + 3000 > 10000이라 종료 코드 1.

## 4. 실측 시험 (사람 승인 뒤, SC-005)

예상 사용량: 합성 텍스트 20개(한국어 10, 영어·코드 10, 합계 약 20 KB) → 약 6 Neurons. 일일 할당의 0.1% 미만.

```bash
uv run pytest -m external tests/external/test_workers_ai_embedding.py -v
```

기록할 것: 텍스트 수, 언어 비중, 바이트 합, 예상 Neurons, 측정 Neurons(`cf-ai-neurons` 합), 차이(%), 모델, 실행일. 차이가 ±20%를 넘으면
research R-04의 `bytes_per_token_estimate`를 고치는 별도 커밋을 만든다.

## 기본 검증 (AGENTS.md 7절)

```bash
python scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
QK_REQUIRE_LOCALDB=1 uv run pytest
```
