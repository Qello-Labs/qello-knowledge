# Quickstart: QK-STO-001 검증 절차

토큰 없이 로컬에서 끝난다. 외부 요청은 0건이다. 명령 계약은 [contracts/cli.md](contracts/cli.md), 경계는 [contracts/store.md](contracts/store.md)를 본다.

## 준비

```bash
uv sync
uv run qk-dev db up
```

## 1. 마이그레이션 두 번 적용 (US3, SC-004)

```bash
uv run qk-migrate
uv run qk-migrate
```

기대: 첫 실행 `applied=N`, 두 번째 실행 `applied=0`. 종료 코드 모두 0.

## 2. 저장소 테스트 (US1~5, SC-001~003, SC-007)

```bash
QK_REQUIRE_LOCALDB=1 uv run pytest tests/localdb/store -v
```

| 테스트 파일 | 확인 | 성공 기준 |
| --- | --- | --- |
| `test_provenance.py` | 출처·버전 추적, 출처 누락·차원 불일치 거부 | US1 AS1~3, SC-001 |
| `test_search_filters.py` | 미확인·제한·삭제·비활성 버전 청크 노출 0건, 자료원 필터, 결과 필드 | US2 AS1~3·6·7, SC-002 |
| `test_keyword.py` | 식별자 원형(함수명·경로·snake_case 각 5개), 한국어, 특수 문자, 빈 검색어 | US2 AS4·5, SC-007 |
| `test_replace.py` | 교체, 실패 주입, 재실행, 동시 교체 | US4 AS1~4, SC-003 |
| `test_embedding_reuse.py` | (입력 해시, 모델 버전) 재사용 | US5 AS1~2 |
| `test_migrate.py` | 재적용 0건, 실패 시 부분 반영 없음, 체크섬 불일치, 파괴적 표시 | US3 AS1~4, SC-004 |
| `test_no_active_index.py` | 활성 인덱스 없음 상태, 상위 N 상한 | Edge Cases, FR-010 |
| `test_neighbors.py` | 앞뒤 청크·상위 절 조회, 노출 조건 | FR-011 |
| `test_mark_deleted.py` | 삭제 전환 즉시 검색 제외 | FR-014 |
| `test_usage.py` | 사용량 조회 | FR-023 |

테스트는 `qk_test_<무작위>` 데이터베이스를 만들고 지운다. 공유 `postgres` 데이터베이스는 건드리지 않는다.

## 3. 기본 검증 (AGENTS.md 7절)

```bash
python scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
QK_REQUIRE_LOCALDB=1 uv run pytest
```

## 4. 성능·용량 측정 (SC-005, SC-006)

```bash
uv run qk-dev store bench
```

기대: 벡터·키워드 상위 20건 p95가 각각 1초 이하. 원문 대비 저장 배율로 10 MB 규모 추정치가 저장 예산 500 MB의 50%(250 MB) 이하.
결과는 아래 기록 표에 조건과 함께 남긴다(C-13).

- 측정 조건: 합성 데이터(한국어 단어 + 식별자 3%), 청크 약 1,200 B, 문서당 청크 8개, 시드 20261019, 같은 PC에서 연결 하나로 순차 호출.
- 저장 사용량은 `qk` 스키마 테이블·인덱스 합계(원문의 13.7배, 대부분 벡터와 HNSW 인덱스)다. DB 전체 크기는 확장·카탈로그 포함 약 160 MB다.
- 인덱스 사용: HNSW는 `pg_stat_user_indexes`로 101회 확인. PGroonga는 이 카운터가 0으로 나와 실행 계획(`Bitmap Index Scan on chunk_search_text_pgroonga`)으로 확인했다.
- 운영 인스턴스(Oracle Cloud A1 2 OCPU·12 GB) 수치가 아니다. 운영 측정은 QK-RET-001·QK-BOT-001에서 한다.

| 측정일 | 이미지 | CPU | 데이터 규모 | 반복 | 벡터 p95 | 키워드 p95 | 10 MB 추정 사용량 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 2026-10-19 | `supabase/postgres:17.11.0.004` | Apple Silicon arm64(macOS, Docker) | 원문 1,106,676 B, 청크 920, 벡터 920(1,024차원) | 각 100회, 상위 20 | p50 3.6 ms / p95 5.4 ms | p50 2.9 ms / p95 6.2 ms | 137 MB(예산 500 MB의 27.4%) |

## 5. 결정 기록 확인 (US6, SC-008)

- `docs/sdd/decisions/ADR-007-storage-schema.md`가 있고 근거 표가 채워져 있다.
- `docs/sdd/decisions/ADR-008-runtime-and-cost-cap.md` 변경 제안 절에 Oracle Cloud 데이터 처리 정책(출처 URL·조회일, 확인 못 한 항목 표시)이 있다.
- 운영 PGroonga 확인은 Oracle Cloud 인스턴스가 생긴 뒤 같은 이미지로 한다. 인스턴스 생성은 이 작업 범위 밖이라 사람 확인 대기다(research R-13). 끝나기 전에는 운영 저장소에 실제 팀 자료를 넣지 않는다.
