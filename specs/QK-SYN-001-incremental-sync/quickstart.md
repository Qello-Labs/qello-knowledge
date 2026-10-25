# Quickstart: QK-SYN-001 검증 안내

**명세**: [spec.md](spec.md) · **계약**: [contracts/sync.md](contracts/sync.md), [contracts/cli.md](contracts/cli.md)

1절은 자동 시험(외부 호출 0), 2절은 로컬 수동 확인(외부 호출 0), 3절은 사람 단계(외부 호출·운영 저장소)다.

## 0. 준비

```bash
uv sync --locked
uv run qk-dev db up
uv run qk-migrate          # 0004_sync.sql 포함. 두 번째 실행은 applied=0
```

## 1. 자동 시험

```bash
python scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
QK_REQUIRE_LOCALDB=1 uv run pytest
```

| 묶음 | 위치 | 확인하는 것 | spec |
| --- | --- | --- | --- |
| 변경 판단 | `tests/unit/sync/test_incremental.py` | 첫 동기화 전부 처리, 무변경 재동기화 임베딩 요청 0·청킹 호출 0·교체 0, 무변경 문서도 본문 재조회·새 보안 규칙 판정, 커밋만 바뀐 원본 0과 처리 버전·링크 유지·확인 버전 갱신, 문서 1개 수정 시 그 문서만, 제목·위치 변경 감지, 빈 문서 청크 0개 교체, 두 번 연속 실행 중복 0 | US1, SC-001·002·006 |
| 원자 반영 | `tests/localdb/sync/test_atomic.py` | 청킹·임베딩(종류별)·저장 실패 주입 시 이전 청크·저장 상태·다음 판단 유지, 반영 직전·직후·실행 기록 닫기 직전 끊김, 실패 원인 제거 뒤 그 문서만 처리, 캐시 완비 문서와 다른 문서의 `EmbedError` 혼합 | US2, SC-004·006·014 |
| 내림 | `tests/localdb/sync/test_takedown.py` | 보류 사유별 허용표(data-model 2.4) 전 칸, 빈 문서 보안 내림 비율 보류 시 대기 목록·사유 비움, 사라진 문서·권한 미확인·비밀값·설정 제외의 검색 미노출, 보안 내림 본문·키워드 텍스트 삭제, 불완전 목록·수집 중단의 일반 내림 0과 실행 상태 `stopped`, 비율 초과 보류와 확인 옵션, 삭제 대기 목록과 복수 준비 버전 사례(active + 대기), 한 실행 안 `PURGE`→`PROCESS`·`PURGE`→`UNCHANGED`·일반 내림 뒤 `PURGE`, 설정에서 지운 자료원의 일반 내림, 비공개 전환·버전 불일치·예산 초과와 보안 내림 조합 | US3, SC-003·005·015 |
| 인덱스 버전 | `tests/localdb/sync/test_index_version.py` | 준비 버전 생성·재사용, 활성화 전 무변경 재실행 0, 설정 변경 시 새 준비 버전 재처리, 활성화 조건 4개 각각의 거부, 활성 버전 있을 때 거부, 동기화 중 활성화 거부 | SC-014 |
| 미리 보기·예산 | `tests/unit/sync/test_preview_budget.py` | 미리 보기 쓰기 0·임베딩 호출 0(확인 옵션을 준 미리 보기 포함), 실제 실행과 대상 집합 일치, 통제 시험 성공 수 일치, 예산 초과 시 교체 0, 두 자료원 합계만 예산 초과일 때 둘 다 보류, 부분 실행 옵션, 실행 중 예산 소진 뒤 캐시 완비 문서 반영 | US4, SC-007·008 |
| 실행 기록 | `tests/unit/sync/test_run_record.py` | 요약 = 문서별 결과 수, 원문·비밀값·토큰·주소 0, 가려진 식별자·새 실패 문서의 `doc_key`로 재식별 | SC-009 |
| 동시 실행 | `tests/localdb/sync/test_concurrency.py` | 같은 자료원 겹침 거부와 쓰기 0, 같은 종류·다른 이름·같은 원본 식별자 자료원 두 실행의 동시 첫 실행에서 하나만 진행, 끊긴 실행 뒤 다음 실행 가능, 다른 종류 자료원 실행 기록 보존, 실행 중 `runs prune`이 `running` 기록을 남김 | SC-010·014 |
| 정체성·점검 | `tests/unit/sync/test_identity.py` | 같은 종류 둘, 설정상 정체성 변경, 자료원 제거만 하면 내림 경로·제거와 같은 종류 새 자료원 추가를 함께 하면 첫 쓰기 전 거부, 수집 뒤 식별값만·이름만 다름·정보 없음, 빈 목록·불완전 목록에서도 원본 정체성·버전 보존, 첫 부분 저장 뒤 끊김과 정체성 변경, 미리 보기는 기준값 미등록 | SC-011 |
| 점검 무쓰기 | `tests/unit/indexer/test_run_cli.py` | 각 점검 실패·원격 확인 없음·정책 파일 없음에서 원본 요청 0과 저장소 쓰기 0, 종료 코드 0~6, 기존 하위 명령(`check`, `sources check`, `security check`, `usage`, `usage prune`) 출력·종료 코드 회귀 | US5, SC-011 |
| 주기 실행 정의 | `tests/unit/indexer/test_schedule_workflow.py` | 트리거, 켜기 게이트, 권한, 비밀값 이름, 정리 단계, 값이 적히지 않음 | US5 |
| 수집 경계 | `tests/contract/` | `origin` 필드 계약(가짜·GitHub 재생 응답) | FR-002 |
| 성능 | `tests/localdb/sync/test_perf.py` | 합성 79개 첫 동기화 60초, 재동기화 30초 이하(research R-15) | SC-013 |
| 경계 | `tests/unit/test_boundaries.py` | `sync`가 `adapters`를 가져오지 않음 | C-06 |

기존 시험(`tests/localdb/store/test_replace.py` 등)은 그대로 통과해야 한다(contracts/sync.md 3절).

## 2. 로컬 수동 확인 (외부 호출 0)

가짜 자료원 설정과 가짜 임베딩 제공자로 명령을 끝까지 돌려 출력과 종료 코드를 본다. 설정 파일과 실행 방법은 tasks에서 시험용 고정 파일로 만든다.

1. `qk-index run --preview --json` → `preview: true`, 저장소 행 수 변화 없음.
2. `qk-index run --json` → 종료 코드 0, `index_active: false`(준비 버전).
3. 같은 명령 다시 → 모든 문서 `UNCHANGED`, `embedding.provider_calls == 0`.
4. `qk-index index status` → 준비 버전 = 현재 설정 버전. `qk-index index activate <버전>` → 활성화.
5. `qk-index runs list`, `qk-index runs show <run-id> --failures`.

## 3. 사람 단계 (외부 호출·운영 저장소)

순서대로 한다. 각 단계는 사람의 승인 뒤에만 한다(AGENTS.md 3.5, spec FR-033·FR-036).

| 단계 | 하는 일 | 비용·위험 | 기록 |
| --- | --- | --- | --- |
| H01 | 로컬 DB에 실제 자료원 미리 보기: `uv run qk-index run --preview --json` | GitHub 약 83회, 0 Neurons | 처리 예정 문서 수, 예상 Neurons |
| H02 | 로컬 DB에 첫 실제 색인과 재실행: `qk-index run` 두 번 | 예상 약 325 Neurons(ADR-002 추정, H01 값으로 확인) | spec SC-012 측정 조건과 값. 두 번째 실행 `provider_calls == 0` |
| H03 | 로컬 DB에서 첫 버전 활성화와 검색 확인 | 질의 임베딩 소량 | 활성화 요약, 검색 결과 출처 |
| H04 | 운영 저장소 제공자 데이터 처리 정책 확인과 `config/store_policy.toml` PR | 없음 | ADR-008 또는 ADR-019에 출처·조회일 |
| H05 | 운영 저장소 연결 방식 확인(세션 advisory lock이 유지되는 직접 연결인지, research R-06) | 없음 | 확인 방법과 결과 |
| H06 | 운영 저장소 첫 실제 색인(`--allow-remote`)과 활성화 | H02와 같은 Neurons | spec SC-012 |
| H07 | 서버 systemd 타이머 구성·비밀값 파일·수동 1회 실행 뒤 타이머 켜기(ADR-020. 처음 계획은 GitHub Actions Secret과 `QK_SYNC_ENABLED`였다) | 없음 | 첫 예약 실행 결과(`journalctl`, `qk-index runs list`) |

H01~H03은 이 작업의 완료 판정(spec SC-012)에 쓴다. H04~H07은 운영 저장소가 정해진 뒤에 하고, 1.G 완료 리뷰 전까지 끝낸다.

## 4. 요구사항 추적표

FR마다 설계 위치와 시험 사례, 확인할 값을 잇는다. 시험 파일 이름은 1절 표의 묶음이다.

| FR | 설계 위치 | 시험 사례 | 확인할 값 |
| --- | --- | --- | --- |
| 001 | contracts/sync.md 1절, research R-18 | `test_incremental` 첫 동기화 | 단계별 요약이 모두 있음, 필터 생략 경로 없음 |
| 002 | research R-06·R-10, contracts/sync.md 1절 1·2·5단계 | `test_identity`, `test_run_cli`, `test_concurrency` | 점검 실패 시 원본 요청 0·쓰기 0, 잠금 뒤 재검사, 수집 뒤 불일치 시 처리·일반 내림 0 |
| 003 | contracts/sync.md 3절(원본 요청 그대로) | `test_incremental` | 원본 쓰기 요청 0(가짜 전송 기록), 임베딩 입력 출처 있음 |
| 004 | contracts/sync.md 1절 7단계, research R-17 | `test_atomic`, `test_takedown` 조합 | 다른 문서 처리 계속, 보류 중 보안 검색 제외 100% |
| 005 | research R-18 | `test_incremental` 무변경 문서 재판정 | 무변경 문서도 본문 조회 1회, 새 규칙에 걸리면 보안 내림 |
| 006·007 | data-model 1.1, research R-04 | `test_atomic` | 실패 문서의 저장 상태 열 전부 이전 값 |
| 008 | research R-03·R-18 | `test_incremental` 사유별 사례 | `change_reason` = 기대값, 지문이 같고 청킹 규칙·내림 복구·인덱스 버전만 다른 세 사례도 청킹·처리됨, 커밋만 바뀐 경우 `UNCHANGED` |
| 009 | research R-18(바뀐 문서만 청킹), contracts/sync.md 1절 7단계 | `test_incremental` 무변경 | 청킹 호출 0, 임베딩 요청 0, 청크 교체 0 |
| 010 | research R-03 `mark_seen` | `test_incremental` 커밋만 바뀜 | `source_version`·`source_url` 그대로, `last_seen_version`·`last_seen_at` 갱신 |
| 011 | research R-04 `apply_document` | `test_incremental` 빈 문서 | 청크 0개, `processed_outcome='empty'`, 검색 0건 |
| 012 | research R-03 | `test_atomic` 실패 뒤 재실행 | 실패했던 문서만 `PROCESS` |
| 013·014 | research R-04·R-17 | `test_atomic` | 일부 청크만 임베딩 성공 시 교체 0, 검색은 이전 묶음 |
| 015 | research R-04 표, data-model 1.1 | `test_takedown` | 일반 내림 청크 유지·검색 0, 보안 내림 청크 행 0 |
| 016 | research R-18 | `test_takedown` 사유별 | `takedown_reason` 기대값, 불완전 목록에서 `source_missing` 0, 제외 패턴 대소문자·정규화 사례, 제외와 포함 이탈이 겹치면 `config_excluded` |
| 017 | research R-05, data-model 1.1 | `test_takedown` 비율 | 확인 옵션 없이 일반 내림·본문 삭제 0, 대기 목록 기대값 |
| 018 | data-model 3.1 | `test_takedown` 다시 통과 | `status='active'`, 다른 버전 대기 유지 |
| 019·020 | research R-08, contracts/sync.md 1절 4단계, data-model 2.4 | `test_index_version` | 한 실행 한 버전, 불일치 시 교체 0·일반 내림 0·보안 검색 제외 적용 |
| 021 | research R-09·R-06 | `test_index_version`, `test_concurrency` | 조건별 거부 사유, 동기화 중 거부, 동기화가 활성화한 경우 0 |
| 022·023 | research R-07, data-model 2.7 | `test_preview_budget` | 쓰기 0, 대상 집합 일치(옵션 포함) |
| 024·025 | research R-17, data-model 2.4 허용표 | `test_preview_budget` | 예산 초과 교체 0, 합계 초과 둘 다 보류, 할당·예산 소진 뒤 제공자 요청 0과 캐시 완비 문서 반영, 장부 오류(예약 실패 항목, 정산 실패 경고, 묶음 오류) 뒤 제공자 요청 0과 캐시 완비 문서 반영 |
| 026 | data-model 1.3·1.4·2.8, contracts/cli.md 4절 | `test_run_record` | 요약 = 결과 행 수, 수집 요약 있음, 캐시 직접 반영 문서가 임베딩 요약의 요청·캐시 적중 수에 들어감 |
| 027 | research R-02·R-06·R-11, data-model 3.2 | `test_run_record`, `test_concurrency`, `test_run_cli` | 점검 실패 시 기록 0, 끊긴 기록 `unfinished`, 정리가 `running` 남김 |
| 028 | research R-12, contracts/cli.md 4절 | `test_run_record` | 원문·비밀값·토큰·주소 0, `doc_key` 재식별, 규칙 이름·줄 번호만 |
| 029 | research R-06 | `test_concurrency` | 겹친 실행 하나만 쓰기, 끊긴 뒤 다음 실행 가능 |
| 030·031 | contracts/cli.md 1~3절 | `test_run_cli` | 하위 명령·옵션 존재, 종료 코드 0~6, 기존 명령 회귀 |
| 032·033 | research R-13, contracts/cli.md 2절 | `test_run_cli` | 원격 옵션·정책 파일 없으면 원본 요청 0·쓰기 0 |
| 034~037 | research R-14, contracts/cli.md 5절 | `test_schedule_workflow` | 트리거, 켜기 게이트, 비밀값 이름, 정리 단계 `if: always()`, 값 없음 |
