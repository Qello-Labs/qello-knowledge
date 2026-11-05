# Plan 검토 기록: QK-STO-002

검토자: 작성에 관여하지 않은 별도 서브에이전트(읽기 전용, 파일 수정·DB·외부 호출 없음). 기준: spec.md 승인본, TASK.md, AGENTS.md, 실제 코드, QK-EVL-001 계약.

## 1차 (2026-11-05) — 변경 요청 16건

| # | 심각도 | 지적 | 반영 |
| --- | --- | --- | --- |
| 1 | 높음 | 재색인이 내린 문서(일반 내림, 보안 내림 뒤 본문 삭제 대기)를 `REINSTATED`로 처리하면 `apply_document`가 자료 행을 되살려 활성 버전 옛 청크가 다시 노출된다. R-03도 같은 길 | R-02: 지금 노출되지 않는 문서는 재색인에서 `HELD`(`reindex_hidden`). R-03 적용 대상을 노출 문서로 좁힘. quickstart 시험 시나리오 추가 |
| 2 | 중간 | 코드가 0009보다 먼저 배포되면 예약 동기화 실패 | R-18: 0009 먼저 적용, 쓰기 전 `schema_outdated` 확인. quickstart H1 순서, 시험 추가 |
| 3 | 중간 | G2·G3를 대상별 `metric_set`으로 계산하면 후보 쪽 분모에서만 질문이 빠진다(FR-016, D3) | R-10 5단계: 가드레일도 판정 질문 집합, 후보 비정상은 Precision@5 0·상한 도달 아님 |
| 4 | 중간 | 정리 때 `purge_reason` 제약과 대기 목록 잔존 | R-16: 마지막 트랜잭션에서 모든 자료 행의 대기 목록에서 빼고 `purge_reason` 갱신 |
| 5 | 낮음 | 덮였지만 마지막 재색인에서 실패한 문서가 안 보임, 버전별 덮음 | R-04: 실패 문서는 노출 문서 전체 기준, 준비 버전마다 덮음 |
| 6 | 낮음 | 예산 초과 거부 시 보안 내림 미반영 | R-02: 다음 예약 실행이 보안 내림을 함(불일치 보류도 허용). 출력에 건수 |
| 7 | 낮음 | 재판정 입력 출처 모호 | R-11·gate-record 5절: 기대 버전은 활성화가 정한 값, 대상 이름은 기록 |
| 8 | 낮음 | `--main-ref` 미기록, `judge_commit.dirty` 미사용, `code_commit.sha = null`, `--source` 재색인, 같은 세트 기록 여럿 | `policy.main_ref` 기록·활성화는 언제나 `origin/main`, `judge_commit`은 기록만(근거 R-09), `code_commit_unknown`, `--source` 금지, `set_duplicate` |
| 9 | 낮음 | `chunk.title` 쓰는 곳 없음, `trace_chunk` 불일치, `replace_chunks` unchanged 경로 | `title` 열 제거, `trace_chunk`도 청크 값 우선, unchanged 경로 설명(R-01) |
| 10 | 낮음 | `sync/execute.py`·`sync/preview.py` 목록 누락 | plan 소스 목록, data-model 2.1 `not_target` 표시 |
| 11 | 낮음 | 첫 활성화 전환 기록의 실행 위치 | R-07: `PostgresSyncStore` 생성 인자 `target`, 채움 행 `unknown` |
| 12 | 낮음 | 이름·참조·예시 불일치, 종료 코드 2 두 뜻 | 조건 이름 `gate_policy`·`no_active_version` 통일, 6절 참조, 정책 예시에 식별자 세트, 종료 코드 2 구분 설명 |
| 13 | 낮음 | 동기화 보고 해소 방법, 자료원 종류, 판정 불가 시 판정 질문 수 | `index_mismatch.resolutions`, `uncovered_sources[{name, kind}]`, `judged_counts` |
| 14 | 낮음 | 실행 기록 커밋 누락 | quickstart H7, gate-record 5절 |
| 15 | 낮음(확인 필요) | HNSW 색인 공유로 FR-005가 벡터 검색에서 근사로만 성립 | R-01 한계 기록, plan 사람 확인 대상 |
| 16 | 낮음 | 병합 커밋 근거 문구(실제 main은 병합 커밋) | R-09 문구 수정, `--diff-merges=first-parent` 명시 |

## 2차 (2026-11-05) — 변경 요청, 1차 16건 해소 확인, 새 지적 7건

1번 보류 규칙은 보안 내림·이미 내린 문서·일반 내림 뒤 재등장·대상 아님·처음 보는 문서·덮음·실행 상태·도메인 규칙·활성화 뒤 동기화 경로에서 코드와 대조해 빈틈이 없다고 확인받았다.

| # | 심각도 | 지적 | 반영 |
| --- | --- | --- | --- |
| N1 | 낮음 | R-09 명령이 diff 본문까지 출력 | `--no-patch` 추가 |
| N2 | 중간 | 기존 CLI 단위 시험의 가짜 저장소가 새 명령과 맞물리지 않음(FR-036) | R-15: 버전 저장소는 동기화 저장소의 `index_versions()`가 내주고 `getattr`로 찾는다. 없으면 지금 키·첫 활성화만. 0009 확인은 어댑터 안에서만(R-18). 기존 시험 파일 수정 없음 |
| N3 | 낮음 | G3가 후보 실패를 유리하게 셈 | 후보 비정상은 상한 도달로 셈(R-10) |
| N4 | 낮음 | 가드레일 판정 질문 0개 | `too_few_judged`(R-10, gate-record 4절) |
| N5 | 낮음 | 활성화 미리 보기 `notes` 키 누락 | cli.md 3절 키 목록 |
| N6 | 낮음 | 0009 확인 범위 모호 | `version >= 9`, `replace_chunks`·`index status` 동작 명시(R-18) |
| N7 | 낮음 | 현재 설정 버전이 아닌 준비 버전의 덮음 | 현재 설정 버전만 값, 나머지 `null` + `not_current_version`(R-04) |
