# Quickstart: QK-OBS-001 검증·운영 절차

**Spec**: [spec.md](spec.md) | **Contracts**: [discord-components](contracts/discord-components.md), [cli](contracts/cli.md)

## 1. 자동 검증 (외부 호출 0건, 0 Neurons)

```bash
python scripts/preflight.py
git diff --check
uv run ruff check . && uv run ruff format --check .
uv run qk-dev db up
uv run qk-migrate && uv run qk-migrate      # 두 번째는 applied=0
QK_REQUIRE_LOCALDB=1 uv run pytest
node --test workers/relay/relay.test.ts
```

기대: 새 시험(`tests/unit/**/test_obs_*.py`, `tests/localdb/query/test_obs_*.py`)이 spec SC-001~SC-011을 덮고, QK-BOT-001 시험 기대값은 그대로다(기본 설정은 기록 기능 꺼짐).

| SC | 시험 |
| --- | --- |
| SC-001·SC-005 | `test_obs_query_record.py`, `test_obs_record_roundtrip.py`: 상태별 기록, 전달 실패, 넣기 실패·상한 초과 |
| SC-002 | `test_obs_no_raw_logs.py`, `test_obs_query_role.py`, `test_obs_export.py`, `test_obs_adapter.py`: 비노출·허용 키·오류 문구 |
| SC-003 | `test_obs_consent_flow.py`, `test_obs_consent_db.py`, `test_obs_pending.py`: 동의 흐름 표(contracts 2절 5~13행), 결과 불명 뒤 재시도·`skip`·만료·재시작 누름의 안내와 원문 유무 일치, 원문 대기 비노출, 요청 없이 만료 뒤 감시 주기 안 질문 참조 삭제, 동시 `keep`·`skip`·중복 `keep`, 보존 날짜 경계 |
| SC-004 | `test_obs_feedback_flow.py`, `test_obs_feedback_db.py`, `test_obs_recorder.py`: 버튼 흐름 표 1~8행, 문장 지연 주입 시 저장 0건(로컬 DB `statement_timeout`), 커밋 뒤 반환 지연 주입 시 불명 안내 → 다시 누름 → 맞는 안내·행 하나, 앞 길 적체 시 늦은 작업 폐기, 첫 응답 상한 하한(500 ms) 경계, 뒤 길이 막혀도 버튼 응답 |
| SC-006·SC-007·SC-008 | `test_obs_erase.py`, `test_obs_query_role.py`, `test_obs_report.py`: 지우기·권한·만료 경고 |
| SC-009 | `test_obs_report.py`: 고정 기록 집계 기대값 |
| SC-010 | `test_obs_sources.py`, `test_obs_sources_db.py`, `test_bot_register_commands.py`: 조회·렌더링·등록 |
| SC-011 | `test_obs_settings.py`, `test_obs_disabled.py`: 설정·꺼짐 불변, 중계 기존 시험(`relay.test.ts:61`, `:224-241`) 그대로 |

## 2. 로컬 확인

```bash
uv run qk-query check --env-file <로컬 env>                 # 새 설정 검사
uv run qk-query register-commands --env-file <로컬 env> --dry-run   # /ask, /sources 두 명령
uv run qk-index queries report --since 2026-10-01 --until 2026-10-31
printf '%s\n' 123456789012345678 | uv run qk-index queries erase-user   # 건수만
```

## 3. 운영 반영 (사람 단계, 명령마다 승인)

순서를 바꾸지 않는다.

1. ADR-016 승인, Discord 공지와 Confluence 동의 문서 작성. 링크·날짜를 ADR-016 Follow-ups에 적는다(spec FR-024).
2. 운영 저장소에 `0008_query_log.sql` 적용(코드 병합 전, 운영 문서 규칙). 두 번째 적용 `applied=0`. 함수 소유자가 마이그레이션 역할인지, `qk_query`가 네 표 권한이 없는지 확인한다.
3. `qk-query.service`에 `LimitCORE=0`을 더하고 인스턴스 스왑 사용 여부를 확인·기록한다(research R-07).
4. 질의 서비스 새 릴리스 배포(기록 기능 꺼짐 그대로). `/ask`가 지금과 같은지 확인한다.
5. 중계 Worker 재배포(콜백 7, 대체 문구). `node --test` 통과 사본으로.
6. `qk-query register-commands`로 `/sources` 등록.
7. `query.env`에 `QK_QUERY_TEXT_RETAIN_UNTIL`(사람이 정한 날짜)과 `QK_QUERY_LOG_ENABLED=true`를 넣고 재시작한다.

되돌리기: 7을 `false`로 되돌리고 재시작하면 기록·버튼·대기가 멈춘다. 표는 남는다(지우기는 `erase-texts`).

## 4. 운영 확인 (사람 단계, spec SC-012)

- 예상 비용: `/ask` 3~5건 × 약 51 Neurons ≈ 최대 255 Neurons. 실행 전 보고하고 승인받는다(AGENTS.md 3.5).
- M-01: `/ask` 3건 이상(질문자 👎 뒤 저장 동의 1건, "나만 보기" 1건), 다른 팀원 👍 1건, `/sources` 1건.
- M-02: 동의 뒤 동의 버튼이 메시지에서 사라지는지(콜백 7, research R-01 미확인) 화면으로 본다. 사라지지 않으면 두 번째 누름이 "이미 선택했습니다."인지 본다.
- M-03: `qk-index queries report`로 건수·평가·동의 수를 확인하고 날짜·질문 수·인덱스 버전·모델과 함께 기록한다. 질문 원문은 기록에 넣지 않는다.
