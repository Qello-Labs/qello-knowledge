# Implementation Plan: QK-GEN-001 답변 생성 프롬프트·출처 표시·확인 불가·충돌 처리·생성 Provider

**Branch**: `feat/SCRUM-107-gh-53-answer-generation` | **Date**: 2026-10-23 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/QK-GEN-001-answer-generation/spec.md`(2026-10-23 승인)

## Summary

QK-RET-001 검색 결과를 받아 판정 표(R-05)대로 생성 호출 없이 끝낼 경우를 먼저 가르고, 남은 경우만 Context를 승인된 후보 1 프롬프트의 자료 블록으로 렌더링한다(제목·한국 시간 수정일 머리줄,
생략·절 줄, 구분자·인용 꼴은 전각 괄호로 무력화). 질문과 묶음을 각각 전송 직전 검사에 넣고(출처 없음), 호출 직전 입력 한도를 다시 잰 뒤 Workers AI REST로 `qwen3-30b-a3b-fp8`을
`/no_think`(승인 템플릿에 들어 있음)·온도 0.2·출력 800으로 부른다. 일시 실패·시간 초과만 마감(45초) 안에서 1회 다시 시도하고 시도마다 새 표 `qk.generation_usage`에 사용량을 기록한다.
받은 글은 결정적 11단계 후처리(R-04)로 추론 블록·출처 줄·발췌문에 없는 URL·없는 ID를 지우고 인용을 정규화한 뒤 확인 불가와 출처 확인 안 됨을 판정하고, 출처 목록은 원본 Context에서 만든다. 흐름은 표준 라이브러리와 경계 타입만 쓰는 새 패키지
`generation/`에 두어 확인 명령(`qk-index ask`)·실측 스크립트·QK-BOT-001이 같은 함수를 부른다. 근거는 [research.md](research.md)에 있다.

## Technical Context

**Language/Version**: Python 3.13 (QK-FND-001 R-01)

**Primary Dependencies**: 새 런타임 의존성 없음. `generation/`은 표준 라이브러리만. HTTP는 생성 전용 표준 라이브러리 전송(호출마다 시간 제한, R-01). `rest.py`는 공개 상수만 가져다 쓴다

**Storage**: PostgreSQL. 마이그레이션 `0006_generation_usage.sql`(테이블 2개·함수 3개 추가만, R-06). 기존 테이블·함수 변경 없음

**Testing**: pytest. 단위(가짜 제공자 `ScriptedProvider`·메모리 장부·가짜 전송 검사) + 로컬 DB(`QK_REQUIRE_LOCALDB=1`, 0006 함수와 `qk-index ask` 조립). 외부 호출 시험 없음(실측은 H01·H02)

**Target Platform**: 생성 흐름은 로컬 CLI·실측 스크립트·Workers 공용. Workers 바인딩 제공자와 진입점 연결은 QK-BOT-001

**Project Type**: 단일 Python 패키지 안의 순수 흐름 모듈 + 제공자 어댑터 + 저장소 함수 + CLI

**Performance Goals**: 생성 단계 기본값 기준 약 42초(시간 제한 20초 × 2 + 대기 2초), 재시도는 마감 45초 안에서만 시작(R-07). 렌더링·후처리 순수 처리는 묶음 8개 기준 수 ms(측정은 H02 지연 기록과 함께)

**Constraints**: 생성 단계 외부 호출 ≤ 4, 질의 전체 ≤ 11(FR-024), 걸린 질문·묶음 전송 0(FR-010), 원문 비기록(FR-012), 기존 사용량 표·합계 불변(FR-021), 원본 쓰기 없음(C-09)

**Scale/Scope**: 하루 질문 50건, Context 묶음 최대 8개. 새 모듈 약 8개, 마이그레이션 1개, CLI 하위 명령 1개, 실측 스크립트 1개

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

`.specify/memory/constitution.md`는 템플릿 상태라 `docs/sdd/constitution.md`와 `AGENTS.md`로 점검한다.

| 원칙 | 이 계획에서 | 결과 |
| --- | --- | --- |
| C-01 근거만 | 프롬프트 규칙 1·3, 확인 불가 판정(R-04 8단계), 출처 목록은 원본 Context에서만(R-04 11단계) | 통과(FR-015 예외는 사람 결정, 아래) |
| C-02 현재 상태는 원본 | 수정일 머리줄, 프롬프트 규칙 6, 출처 목록에 수집 시각. 원본 조회는 범위 밖 | 통과 |
| C-03 자료는 데이터 | 구분자·인용 꼴 무력화(R-03), 프롬프트 규칙 7, 실측의 지시문 주입 문항(R-11) | 통과 |
| C-04 작게 시작 | 새 의존성 0, 환경값 5개, 스트리밍·리랭커·질문 분류 없음, 바인딩 제공자는 후속 | 통과 |
| C-05 비용 상한 | 질의당 약 38 Neurons(하루 50건 약 1,900), 무호출 경로, 실측 약 927(H01 약 7 + H02 상한 약 920, 출력 상한·모두 재시도 시 최대 약 1,900) 사람 확인, 예비분 초과 경고(질의응답 합계 기준) | 통과 |
| C-06 교체 가능한 경계 | `GenerationProvider`·`GenerationLedger`·`OutgoingCheck`만 사용, `generation/` 경계 시험 | 통과 |
| C-07 재현 | 프롬프트 해시 식별자, 결정적 렌더링·후처리(SC-010) | 통과 |
| C-09 원본 읽기 전용 | 생성은 저장소를 읽지도 않는다(받은 Context만). 사용량 표에만 쓴다 | 통과 |
| C-10 민감 정보 | 질문·묶음 전송 직전 검사, 요약·기록·로그에 원문 없음, 실측 원문은 저장소 밖 | 통과 |
| C-11 명세 먼저 | spec 승인 2026-10-23. plan 승인 전 구현하지 않는다 | 보류 — plan 사람 승인 |
| C-12 검증으로 닫기 | SC마다 시험(quickstart 1절), SC-008은 사람 단계 H01~H03 | 통과 |
| C-13 수치 조건 | 요약에 프롬프트 버전·모델·설정, 실측에 질문 세트 `gen-ko-v1`·표본 수·날짜 | 통과 |
| C-14 권한 확인 자료만 | Context는 QK-RET-001이 노출 조건을 거친 것만. 출처 목록도 그 Context에서만 | 통과 |
| AGENTS.md 3.1 | 새 자료원·외부 모델 없음(ADR-009 모델). 외부 전송 전 비밀값 검사 | 통과 |
| AGENTS.md 3.2 | Source ID 표시. FR-015는 충돌을 알고 사람이 유지(spec Assumptions "FR-015와 AGENTS.md 3.2") | 예외 기록됨 |
| AGENTS.md 3.3 인덱스 버전 | 색인·인덱스 변경 없음. 생성 모델 교체는 인덱스와 무관(ADR-009) | 통과 |
| AGENTS.md 3.4 평가 | 이 명세는 평가 수치를 확정하지 않는다(QK-EVL-002). 실측 질문은 합성 | 통과 |
| AGENTS.md 3.5 비용 | 실측 전 예상량 보고·사람 확인 | 통과 |
| AGENTS.md 4절 | 마이그레이션 추가만, 기존 표 불변. 재실행 안전(`qk-migrate` 두 번째 applied=0) | 통과 |

Phase 1 설계 뒤 재점검: data-model이 결과 불변식(확인 불가면 출처 없음, 출처 = 본문 ID)과 요약의 비원문 항목을, contracts가 처리 순서(판정 → 검사 → 한도 → 호출·기록 → 후처리)와 외부 호출 계산을
고정했다. 새 위반 없음. 보류는 C-11(plan 승인), 예외는 AGENTS.md 3.2(사람 결정 기록됨)다.

## Project Structure

### Documentation (this feature)

```text
specs/QK-GEN-001-answer-generation/
├── spec.md
├── plan.md              # 이 파일
├── research.md          # R-01~R-14
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── generation.md    # generate·render·postprocess, 경계, 처리 순서, 다른 경계에 더하는 것
│   └── cli.md           # qk-index ask
├── measurement/
│   └── measure_generation.py   # R-11 실측(H02). 답변 원문은 저장소 밖에만 쓴다
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks 산출물
```

### Source Code (repository root)

```text
src/qello_knowledge/
├── domain/
│   └── generation.py             # GenerationSettings, PromptSpec, GenerationRequest, RenderedBlock/Input, DroppedBlock, ProviderReply,
│                                 # GenerationStatus/Failure, CannotConfirmReason, Citation, GenerationFlags/Summary/Result, GenerationUsage, AnswerUsageToday
├── ports/
│   └── generator.py              # Generator(채움), GenerationProvider, GenerationLedger, GenerationProviderFailure
├── generation/
│   ├── __init__.py               # generate, render, postprocess, check_settings, prompt_spec 공개
│   ├── prompts.py                # gen-p1(후보 1)·gen-base(spike 부록 B), 해시 식별자(R-02)
│   ├── render.py                 # 자료 블록·무력화·토큰 추정(R-03·R-08)
│   ├── postprocess.py            # 11단계 후처리(R-04)
│   ├── service.py                # generate 처리 순서·판정 표(R-05)·재시도·기록(R-07)
│   ├── settings.py               # check_settings(R-08 (1))
│   └── fake.py                   # ScriptedProvider, MemoryLedger(R-13)
├── adapters/
│   ├── workers_ai/generation.py  # WorkersAiGenerationProvider, 전용 전송, 오류 판정, ResponseShape(R-01)
│   └── postgres/
│       ├── generation_usage.py   # PostgresGenerationLedger
│       └── migrations/0006_generation_usage.sql
├── config/
│   ├── registry.py               # QK_GEN_* 5개(R-12)
│   └── check.py                  # 생성 설정 검사 연결
└── indexer/
    ├── cli.py                    # ask 하위 명령 등록
    ├── ask_cli.py                # 조립, 표준 입력, 실행 전 알림, 출력, 종료 코드(contracts/cli.md)
    └── usage.py                  # prune이 생성 사용량도 정리(R-06)
tests/
├── unit/generation/              # test_gen_*.py(이름 충돌을 피하는 접두어, tasks.md 공통 규칙)
├── unit/adapters/test_gen_workers_ai_generation.py   # 응답 두 꼴·오류 판정(저장한 응답 샘플, 합성)
├── unit/indexer/test_gen_ask_cli.py, test_gen_usage_prune_cli.py
├── localdb/generation/           # test_gen_usage_ledger(0006 함수), test_gen_ask_command
└── unit/test_boundaries.py       # generation 경계
```

**Structure Decision**: 판단(렌더링·후처리·판정)은 제공자 없이 시험되는 순수 함수로, 외부 호출과 기록은 `service.py` 한 곳에서만 한다. 생성은 저장소를 읽지 않고 받은 `RetrievalResult`만
쓴다(Edge Cases "생성 중 문서가 내려졌을 때"). Workers 진입점 연결은 하지 않는다. `query/app.py`는 바꾸지 않고 QK-BOT-001이 `retrieve` → `generate`를 부른다.

## Phase 0·1 산출물

- Phase 0: [research.md](research.md) R-01~R-14. `NEEDS CLARIFICATION` 없음. spec이 계획 단계로 넘긴 항목의 결정 위치:
  생성 사용량 저장 구조 → R-06(새 표, 기존 표 불변), 호출 방식(바인딩·HTTP) → R-01(REST, 바인딩은 QK-BOT-001), 생성 전체 시간 상한 → R-07(마감 기본 45초 안에서만 재시도, 42초는 기본값 기준 추정),
  바인딩 경로의 Neurons·종료 사유 → R-01(두 응답 꼴, 대체 규칙, H01에서 확인).
- Phase 1: [data-model.md](data-model.md), [contracts/generation.md](contracts/generation.md), [contracts/cli.md](contracts/cli.md), [quickstart.md](quickstart.md).
- 남는 위험: R-01 응답 꼴 미확인(H01에서 확인, 다르면 어댑터만 고침), R-04 마침표 없는 한국어 문장 경계와 FR-009 (나)가 유효 인용 사실 문장을 확인 불가로 만드는 경우(spec에서 온 위험),
  R-06 `qk-index usage`의 `query_used`와 질의응답 합계의 차이, R-07 소켓 단위 시간 제한, R-11 실측 표본 24회(방향만 봄), 바인딩 경로 사용량 정보(QK-BOT-001).
- 독립 검토 1차(작성에 관여하지 않은 별도 에이전트, 판정 변경 요청: 높음 2, 중간 9, 낮음 14) 반영. 반영 위치는 research.md "검토 반영" 표에 있다. 수치(R-08, 비용)는 검토자가 다시 계산해 맞다고 했다.
  작성 세션 판단 3건: `rest.py`를 바꾸지 않고 생성 어댑터에 같은 규칙의 오류 판정을 두고 표 시험으로 고정(M2 (b)·(c)), 실패 시도 Neurons를 과금 가능성으로 나눔(M8 (c)),
  `qk-index usage prune`에 생성 정리를 붙임(M8 (b), Scope 추가). 2026-10-23 사용자가 셋 다 그대로 진행하기로 했고, gen-base 템플릿을 승인했으며, FR-009 (나)는 spec 그대로 두고 시험으로 고정하기로 했다.
- 같은 검토자의 재검토 판정은 승인 권고다(이전 지적 해소 20·부분 해소 5·미해소 0, 새 지적 중간 4·낮음 5). 새 지적 N1~N9를 반영했다(research.md "재검토 반영" 표). N1(한글 경로 URL),
  N2(과금 분류표와 후처리 결과 기록), N4(마감 기본값을 시간 제한에서 계산)는 작성 세션 판단이다.

## 구현 Scope 승인이 필요한 것

TASK.md Scope는 지금 명세·계획 단계다. tasks 승인 때 Scope를 고쳐 함께 승인받는다.

| 변경 | 걸리는 범위 | 이유 |
| --- | --- | --- |
| `ports/generator.py` 채움 | QK-FND-001이 만든 빈 경계 | 생성 경계 계약(contracts/generation.md 2절) |
| `adapters/workers_ai/generation.py`(새 파일, `rest.py`는 공개 상수만 가져다 씀) | QK-EMB-001 어댑터 패키지 | 생성 제공자(R-01) |
| `indexer/usage.py`의 `prune` | QK-EMB-001 CLI | 생성 사용량 보관 규칙(spec FR-020, R-06). `today` 표시는 바꾸지 않음 |
| `adapters/postgres/generation_usage.py`, `0006_generation_usage.sql` | QK-STO-001 스키마(추가만) | 생성 사용량(R-06). 기존 표·함수 변경 없음 |
| `config/registry.py`, `config/check.py`, 설정 예시 파일 재생성 | QK-FND-001 설정 | `QK_GEN_*`(R-12), 설정 검사(FR-019) |
| `indexer/cli.py`에 `ask` 등록, `indexer/ask_cli.py` | QK-EMB-001·QK-SYN-001·QK-RET-001이 쓰는 CLI 파일 | 확인 명령(R-10). `search_cli.py`는 함수를 가져다 쓰기만 |
| `tests/unit/test_boundaries.py` | 기존 시험(검사 추가만) | `generation` 경계 |
| (변경 없음) `tests/localdb/store/test_migrate.py`, `tests/localdb/sync/test_migration.py` | 기존 시험 | 마이그레이션 수를 앞의 것은 `MIGRATIONS_DIR.glob`으로, 뒤의 것은 `load_migrations()`로 세므로(2026-10-23 확인) 0006을 더해도 기대값을 고치지 않는다 |
| `measurement/measure_generation.py` | 명세 디렉터리 | 실측(R-11) |

## 다른 명세에 넘기는 것

| 대상 | 넘기는 내용 |
| --- | --- |
| QK-BOT-001 | Workers 진입점에서 `retrieve` → `generate` 호출, Workers AI 바인딩 제공자(같은 `GenerationProvider`), 바인딩 응답의 Neurons·종료 사유 확인, 상태별 사용자 안내 문구(검색 실패·전송 차단·생성 실패), "출처 확인 안 됨"·"출력 잘림" 표시 방법, 출처 목록 링크 꼴과 답변 분할, 질의 전체 시간(검색 + 최대 42초)과 Workers 한도 측정 |
| QK-EVL-002 | `gen-p1`·`gen-base` 답변 평가(충실성·인용 정확도·확인 불가), 출처 확인 안 됨 비율, FR-015 재결정 근거 |
| QK-OBS-001 | 질의 로그에 생성 요약(원문 없음) 연결, 질의응답 하루 합계를 운영 화면에 표시(`qk.generation_usage_today`) |
| QK-TRK-001 | 무관 질문 비율이 높으면 생성 전 거르기 검토(spec Assumptions) |
| 첫 비밀값 오탐 예외 등록 시 | FR-010 출처 없는 묶음 검사 재검토, 필요하면 QK-RET-001 Context에 자료원 이름·경로 추가(spec Assumptions) |

## Complexity Tracking

| 항목 | 이유 | 더 단순한 대안을 고르지 않은 이유 |
| --- | --- | --- |
| 새 사용량 표(0006) | 생성은 토큰·시도·프롬프트 버전 열이 필요하고 기존 합계를 바꾸면 안 된다(FR-020·021) | 기존 `qk.embedding_usage`에 용도 추가 — 제약 변경과 열 부재, QK-EMB-001 합계·시험 영향 |
| 11단계 후처리 | 스파이크에서 인용 규칙 준수 2/4, spec·plan 독립 검토가 경계 사례 20여 개를 찾음(spec FR-009·013~015) | 모델 출력 그대로 — 없는 ID·링크가 사용자에게 간다(C-01·C-14) |
| 생성 전용 전송·오류 판정 | `rest.py`의 판정은 성공 경로가 임베딩 전용이고 전송은 시간 제한을 생성자에서만 받는다(R-01) | `rest.py` 공개 함수 추가 — QK-EMB-001 파일 변경, Scope 확대 |
| 두 가지 응답 꼴 해석 | 생성 응답 본문 꼴을 스파이크에서 기록하지 않았다(R-01) | 한 꼴만 — H01 전에 틀리면 모든 호출이 "잘못된 응답"이 된다 |
