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

## 5. 주기 실행 정의: 서버 systemd 타이머 (research R-14, ADR-020)

처음 정의는 GitHub Actions 워크플로 `.github/workflows/index-sync.yml`이었다. 저장소가 공개라 ADR-020이 실행 위치를 운영 OCI 인스턴스의 systemd 타이머로 바꿨고,
쓰지 않는 워크플로 파일과 그 파일만 검사하던 시험(`tests/unit/indexer/test_schedule_workflow.py`)은 2026-10-25 지웠다(SCRUM-113). 구성 원본은 `docs/ops/oci-production-store.md` 2절 6~10번이다.

| 항목 | 값 |
| --- | --- |
| 트리거 | `qk-sync.timer`: `OnCalendar=*-*-* 00:30:00 UTC`, `Persistent=true`. 수동 실행은 `systemctl start qk-sync.service` |
| 켜기 게이트 | 사람이 비밀값 파일을 만들고 수동 1회 실행에 성공한 뒤 `systemctl enable --now qk-sync.timer`(spec FR-036) |
| 실행 사용자 | `qksync`(sudo·docker 그룹 없음). `NoNewPrivileges`, `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp` |
| 동시 실행 | 타이머는 앞 실행이 끝나기 전에 다시 시작하지 않는다. 그 밖의 겹침은 세션 잠금이 막는다(종료 6) |
| 시간 제한 | `TimeoutStartSec=30min` |
| 비밀값 | `/etc/qello-knowledge/sync.env`(root:qksync, 0640)의 `DATABASE_URL`, `GITHUB_API_TOKEN`, `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`. 저장소에 값 없음 |
| 단계 | 복제본을 `origin/main`으로 맞춤 → `uv sync --locked --extra index --extra postgres` → `uv run qk-index run --allow-remote --trigger schedule --json` → `usage prune --allow-remote` → `runs prune --allow-remote`(정리는 동기화 결과와 관계없이 돈다) |
| 결과 | 동기화나 정리가 실패하면 서비스가 실패 상태로 끝난다(spec FR-037). 다음 예약 실행은 처음부터 돈다 |
