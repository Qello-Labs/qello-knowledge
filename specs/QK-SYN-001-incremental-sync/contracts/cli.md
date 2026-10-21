# Contract: `qk-index` 명령과 주기 실행

**명세**: [../spec.md](../spec.md) FR-029~037 · **결정**: [../research.md](../research.md) R-06·R-09·R-11·R-13·R-14·R-16

기존 하위 명령(`check`, `sources check`, `security check`, `usage`, `usage prune`)은 바꾸지 않는다. 지금의 `qk-index run`은 설정 점검 뒤 자료원 목록만 출력한다
(`indexer/cli.py`). 이 명령을 동기화 실행으로 바꾼다. 점검 단계와 기존 옵션(`--sources`, `--reviews`, `--exceptions`, 설정 점검 옵션)은 그대로 둔다.

## 1. 명령

| 명령 | 하는 일 | 저장소 쓰기 |
| --- | --- | --- |
| `qk-index run` | 동기화 실행 | 점검·잠금 통과 뒤 |
| `qk-index run --preview` | 미리 보기(spec FR-022) | 없음 |
| `qk-index runs list [--limit N]` | 최근 실행 목록(상태, 시각, 자료원별 요약) | 없음 |
| `qk-index runs show <run-id> [--failures]` | 실행 하나의 요약, 실패 목록(`doc_display`, 단계, 유형) | 없음 |
| `qk-index runs prune [--retention-days 90] [--allow-remote]` | 오래된 실행 기록 정리(research R-11). `running` 기록은 남긴다. 기간은 1 이상 | 있음 |
| `qk-index index status` | 활성·준비 인덱스 버전, 현재 설정 버전, 일치 여부 | 없음 |
| `qk-index index activate <version> [--allow-remote]` | 첫 인덱스 버전 활성화(research R-09) | 조건 충족 시 |

## 2. `qk-index run` 옵션

| 옵션 | 기본 | 뜻 |
| --- | --- | --- |
| `--preview` | 꺼짐 | 미리 보기만 |
| `--trigger {manual,schedule}` | `manual` | 실행 기록의 시작 방식 |
| `--allow-remote` | 꺼짐 | 로컬이 아닌 저장소 대상 실행 허용(spec FR-032). 운영 저장소 정책 파일도 있어야 한다(research R-13) |
| `--allow-partial-budget` | 꺼짐 | 예산 초과 때 예산 안 부분 실행(spec FR-024, QK-EMB-001 `allow_partial`) |
| `--confirm-takedown` | 꺼짐 | 내림 비율을 넘는 일반 내림·본문 삭제와 삭제 대기 본문 지우기를 허용(spec FR-017) |
| `--source NAME` | 모든 대상 자료원 | 자료원 하나만(설정에 있거나 저장소에 기록된 이름). 다른 자료원 문서는 건드리지 않는다 |
| `--json` | 꺼짐 | 기계가 읽는 출력 |
| `--env-file PATH` | `.env` | `qk-index usage`와 같은 방식 |

`--preview`는 `--allow-partial-budget`·`--confirm-takedown`·`--source`와 같이 쓸 수 있다. 판단만 그 옵션대로 하고 쓰지 않는다(research R-07). `--preview`와 `--trigger`는
같이 쓸 수 없다(실행 기록이 없으므로. 인자 오류는 argparse 기본 종료 코드 2).

## 3. 종료 코드 (research R-16)

| 코드 | 뜻 |
| --- | --- |
| 0 | 성공 |
| 1 | 실행 전 점검 실패(설정, 자료원, 개인 정보 확인 기록, 자료원 식별, 보안 규칙, 예산 설정, 운영 저장소 정책 파일), 활성화 조건 미충족 |
| 2 | 저장소 사용 불가 |
| 3 | 로컬이 아닌 저장소에 `--allow-remote` 없음 |
| 4 | 일부 실패(문서 실패 ≥ 1) |
| 5 | 멈춤(보류 ≥ 1: 예산 초과, 인덱스 버전 불일치, 내림 비율 초과, 수집 뒤 정체성 불일치·없음, 수집 중단·불완전 목록) |
| 6 | 이미 실행 중 |

4와 5가 함께면 5다. argparse 인자 오류는 argparse 기본 종료 코드(2)를 쓰지만 원본 호출 전이다.

## 4. 출력

사람이 읽는 출력과 `--json` 모두 원문, 비밀값, 토큰, 접속 주소를 담지 않는다(spec FR-028). 대상 저장소는 `target=local|remote`로만 보인다(`target_label`).

`--json` 최상위 키(실행): `run_id`, `status`, `exit_code`, `trigger`, `target`, `rules_version`, `chunking_version`, `index_version`, `index_active`(bool),
`sources[]`(`source_name`, `mode`, `status`, `origin_version`, `listing_complete`, `stop_reason`, `retry_at`, `holds[]`, `counts`{작업별}, `takedowns`{사유별},
`takedown_ratio`{`general`, `purge`, `base`, `threshold`}, `collection`(QK-ING-001 수집 요약, 항목 목록 제외), `filter`(QK-SEC-001 요약), `chunking`(QK-CHK-002 요약),
`embedding`(문서별 QK-EMB-001 `RunSummary` 합계), `failures[]`{`doc_display`, `stage`, `failure`}, `security_takedowns[]`{`doc_display`, `reason`, `rule`, `lines`}).
`runs show`는 저장된 표시값을 그대로 쓰지 않고 출력 직전에 QK-SEC-001 기록 출력 규칙을 다시 적용한다(spec FR-028).

`--json` 최상위 키(미리 보기): `preview: true`와 위 `sources[]`에서 실행 결과 대신 예정 수, 그리고 `embedding_preview`(QK-EMB-001 `EmbedPreview`의 모든 필드), `runnable`.
`run_id`는 없다.

## 5. 주기 실행 정의 `.github/workflows/index-sync.yml` (research R-14)

| 항목 | 값 |
| --- | --- |
| 트리거 | `schedule: cron '30 0 * * *'`, `workflow_dispatch` |
| 켜기 게이트 | `jobs.sync.if: vars.QK_SYNC_ENABLED == 'true'` |
| 권한 | `permissions: contents: read` |
| 동시 실행 | `concurrency: { group: index-sync, cancel-in-progress: false }` |
| 시간 제한 | `timeout-minutes: 30` |
| 비밀값 | `DATABASE_URL`, `QK_GITHUB_API_TOKEN`(→ 환경 변수 `GITHUB_API_TOKEN`), `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`. 정의 파일에 값 없음 |
| 단계 | checkout(`persist-credentials: false`) → setup-uv → `uv sync --locked --extra index --extra postgres` → `uv run qk-index run --allow-remote --trigger schedule --json` → (`if: always()`) `uv run qk-index usage prune --allow-remote` → (`if: always()`) `uv run qk-index runs prune --allow-remote` |
| 결과 | 동기화가 0이 아니면 작업 실패(spec FR-037). 다음 예약 실행은 처음부터 돈다 |

워크플로 파일은 이 작업에서 더하지만 `QK_SYNC_ENABLED` 변수와 Secret은 사람이 FR-033 확인과 첫 실제 색인 뒤 만든다(spec FR-036). 시험은 워크플로 파일을 읽어
위 항목을 검사한다(`tests/unit/indexer/test_schedule_workflow.py`). YAML 해석 의존성이 없으므로 줄 단위 텍스트로 확인한다(새 의존성 없음).
