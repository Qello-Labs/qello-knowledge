# Quickstart: QK-RET-001 검증 안내

외부 API 호출 없이 끝나는 검증이 기본이다(가짜 임베딩 제공자). 사람 단계는 3절에 따로 둔다.

## 1. 자동 검증

```bash
python scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
uv run qk-dev db up
uv run qk-migrate          # 두 번 실행, 두 번째 applied=0
uv run qk-migrate
QK_REQUIRE_LOCALDB=1 uv run pytest
```

| spec | 시험 위치 | 보는 것 |
| --- | --- | --- |
| SC-001, US1 | `tests/unit/retrieval/test_fuse.py`, `tests/localdb/retrieval/test_hybrid.py` | RRF 기대값, 한쪽에만 있는 청크, 동점, 두 번 실행 같음 |
| SC-002, US2 | `tests/localdb/retrieval/test_visibility.py` | 미확인·제한·비활성 버전·내림 청크가 결과·Context에 0건, 결과 뒤 내림 → `not_visible` |
| SC-003, US4 | `tests/unit/retrieval/test_pack.py`, `tests/unit/retrieval/test_pack_property.py` | 예산 이하, 잘림 0, 중복 0, 알고리즘 기대 결과 |
| US3 | `tests/unit/retrieval/test_context_blocks.py`, `tests/unit/retrieval/test_expand.py`, `tests/localdb/retrieval/test_context.py`, `tests/localdb/retrieval/test_chunk_context.py` | 문서당 묶음 하나, gaps, `section_first` 정의(같은 제목 경로 두 번) |
| SC-004 | `tests/localdb/retrieval/test_keyword_rules.py` | 식별자 원형·일부 상위 20건 비율(규칙별 DB) |
| SC-005 | 같은 파일 | 문장형 질문 10개 이상, `kw-query-v1` ≥ 90%, `kw-query-raw` 비율 함께 출력 |
| SC-006 | `uv run qk-dev store bench --retrieval`(tasks T053, 결과는 tasks.md 실행 기록. QK-STO-001 SC-005와 같은 방식, 시험 마커 없음) | p95 1.5초, 순수 처리 p95, 조건 출력 |
| SC-007 | `tests/unit/retrieval/test_calls.py` | 확장 상위 1·8·20, 재시도 경로, 버전 바뀜 재검색 0 |
| SC-008, SC-011 | `tests/unit/retrieval/test_degrade.py` | 하이브리드 축소와 사유, 단일 방식 실패, 요약·기록에 질문 없음 |
| SC-009 | `tests/unit/retrieval/test_calls.py`, `tests/localdb/devtools/test_eval_index.py` | 키워드 전용 임베딩 0, 캐시 복사 DB에서 재색인 임베딩 0·원본 쓰기 0 |
| SC-010 | `tests/unit/chunking/test_keyword_rule_version.py` | `chk-md-20d966f730bb`, `iv-4c0bc4fcc642` 유지, 대응표 일치 |
| US7 | `tests/unit/indexer/test_search_cli.py` | 표준 입력, 출력에 질문 없음, 종료 코드 |
| FR-009 | `tests/unit/retrieval/test_degrade.py` | 빈 질문·길이 초과에서 외부 호출 0 |
| FR-028 | `tests/unit/retrieval/test_retrieval_settings.py` | 범위 밖 설정·덮어쓰기 거부 |
| R-03 | `tests/unit/retrieval/test_keyword_query.py`, `tests/localdb/retrieval/test_keyword_terms.py` | 낱말 규칙 기대값(조사·백틱·`OR`, 가운데 `OR`가 낀 질문의 점수), 서로 다른 맞은 낱말 수 정렬, 일치 확장 꺼짐 |
| R-09 | `tests/localdb/devtools/test_eval_index.py` | 준비용 이름 재실행, 최종 이름 있음 → 5, 예상 Neurons > 0 → 4, 저장소 파일 불변 |

## 2. 로컬 손 확인

```bash
echo "결제 취소 API 경로가 뭐야?" | uv run qk-index search --json
echo "retry" | uv run qk-index search --mode keyword
```

로컬 개발 DB에 활성 인덱스가 없으면 종료 코드 1과 `no_active_index`가 나온다. 색인이 있으면 순위·출처·요약이 나오고 질문은 출력에 없다.

## 3. 사람 단계

| 단계 | 내용 | 비용·허락 |
| --- | --- | --- |
| H01 | research R-08 측정(2026-10-22 완료, 예산 유지). 청커·예산 설정을 바꾸면 같은 스크립트로 다시 잰다 | 저장소 복제와 토크나이저 내려받기 허락. Workers AI 0 |
| H02 | `qk-dev eval-index prepare`로 기준선·식별자 분해 평가용 DB를 같은 커밋으로 만들기 | GitHub 읽기. 예상 0 Neurons(0이 아니면 멈춤) |
| H03 | 운영 또는 로컬 색인 DB에 `qk-index search`로 질문 몇 개 확인 | 질의용 임베딩 질문당 1 Neurons 미만. 원격이면 `--allow-remote` |
