# Quickstart: QK-GEN-001 답변 생성 검증

기본 검증은 외부 호출 0건이다. 실제 생성 모델 호출은 사람 단계(H01·H02)에서만 한다.

## 1. 자동 검증

```bash
python scripts/preflight.py
git diff --check
uv run ruff check .
uv run ruff format --check .
uv run qk-dev db up
uv run qk-migrate   # 두 번 실행, 두 번째는 applied=0
uv run qk-migrate
QK_REQUIRE_LOCALDB=1 uv run pytest
```

| 성공 기준 | 시험 위치(예정) | 확인하는 것 |
| --- | --- | --- |
| SC-001 | `tests/unit/generation/test_gen_citations.py`, `test_gen_cleanup.py`, `test_gen_cannot_confirm.py` | 인용 인식·제거·정규화, 인식 못 한 꼴(`[S9,]`·`[S0]`·`[S1/S2]` 등), URL 규칙(조사 붙은 URL·끝 마침표·앞부분만 같은 URL·한글 경로 `…/설계.md`와 가짜 `…/가짜.md`·괄호 경로), 공백 뒤 인용 귀속(`A다. [S1] B다. [S2]`), `[AWS S3 버킷]`은 인식 못 한 꼴로 세지 않음, 출처 줄("참고로" 문장 보존), 코드 안 글 보존, 빈 결과 = 잘못된 응답, 출처 목록 = 본문 ID·무력화 전 제목, 출처 확인 안 됨, FR-009 (나)의 유효 인용 문장 사례 |
| SC-002 | `tests/unit/generation/test_gen_no_call.py` | 결과 없음·빈 Context·모든 묶음 차단·검색 실패에서 제공자 호출 0, 확인 불가 문장 글자 일치 |
| SC-003 | `tests/unit/generation/test_gen_outgoing.py` | 걸린 질문·묶음이 가짜 제공자 기록에 0건, 남은 Source ID 불변 |
| SC-004 | `tests/unit/generation/test_gen_neutralize.py` | 본문·제목·위치·질문에 심은 구분자·인용 꼴(줄바꿈 든 `[S1,\nS2]`·`[\nS7\n]` 포함), 머리줄 말고 FR-013 인식 꼴 0 |
| SC-005 | `tests/unit/generation/test_gen_render.py`, `test_gen_cleanup.py` | 사용자 메시지 끝 ` /no_think`, 추론 블록 제거(닫히지 않은 블록 포함) |
| SC-006 | `tests/unit/generation/test_gen_no_raw_text.py` | 실패 주입 포함, 요약·기록·로그(caplog)·예외 문구에 심은 표식 문자열 0 |
| SC-007 | `tests/unit/generation/test_gen_retry_usage.py`, `tests/localdb/generation/test_gen_usage_ledger.py`, `tests/unit/adapters/test_gen_workers_ai_generation.py`, `tests/unit/indexer/test_gen_usage_prune_cli.py` | 재시도 조건·횟수·마감, 호출 수 ≤ 4, 시도마다 기록, 과금 가능성별 Neurons, 질의응답 합계 = 임베딩 + 생성, 색인 판정·기존 합계 불변, `usage prune`이 생성 표도 정리, 시간 초과·일시 실패 구분 |
| SC-009 | `tests/unit/generation/test_gen_check_settings.py`, `test_gen_settings_domain.py`, `test_gen_input_limit.py` | 설정 검사 (1), 덮어쓰기 최대에서 호출 직전 검사 (2), 시간 제한·마감 교차 검사 |
| SC-010 | `tests/unit/generation/test_gen_render.py`, `test_gen_prompts.py` | 같은 입력 두 번 같은 결과, 프롬프트·템플릿·규칙 하나만 바꿔도 식별자 변경, 고정 Context 3종 렌더링 골든 비교, `gen-p1`이 TASK.md 승인 원문과 글자 일치 |
| US7 | `tests/unit/indexer/test_gen_ask_cli.py`, `tests/localdb/generation/test_gen_ask_command.py` | 표준 입력, 가짜 제공자 기본, 종료 코드, 질문 원문 비출력 |
| 경계 | `tests/unit/test_boundaries.py` | `generation/`이 `domain`·`ports`만 가져옴 |

## 2. 사람 단계

| 단계 | 내용 | 외부 호출·비용 | 승인 |
| --- | --- | --- | --- |
| H01 | 실제 응답 꼴 확인. `measure_generation.py --provider workers-ai --only 1 --prompt gen-p1 --out <저장소 밖 경로>`로 합성 1문항을 후보 1로 실행하고, 응답 꼴(`ResponseShape`: 키 이름·`usage`·헤더·종료 사유 유무)만 기록(research R-01·R-11) | 생성 1회, 보통 약 7 Neurons(출력 상한까지 나오면 약 29, 재시도 시 최대 약 58), 임베딩 0, DB 없음 | 사람 확인 뒤 |
| H02 | SC-008 실측. `uv run python specs/QK-GEN-001-answer-generation/measurement/measure_generation.py --provider workers-ai --prompt both --out <저장소 밖 경로>` (research R-11) | 24회, 상한 약 920 Neurons(모두 재시도 시 최대 약 1,840), 임베딩 0 | 예상량·최대치 보고 뒤 사람 확인 |
| H03 | H02 답변 원문을 사람이 읽고 확인 불가 판정·지시문 무시·충돌·현재 상태 문구를 판정, 결과를 tasks.md 실행 기록에 남김 | 없음 | 사람 |

H01·H02는 하루 질의응답 예비분(3,000) 안이다. 같은 날 다른 질의가 많으면 예비분 초과 경고가 날 수 있고 막지는 않는다(spec FR-021).

## 3. 확인 명령 예

```bash
uv run qk-index ask < question.txt
```

```bash
uv run qk-index ask --json --prompt gen-base < question.txt
```

`question.txt`는 합성 질문만 담는다. 실제 팀 질문을 파일로 남기지 않는다(AGENTS.md 6절).
